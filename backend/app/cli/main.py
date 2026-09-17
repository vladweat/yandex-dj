import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

import click
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError, OperationalError
from yandex_music import DeviceCode
from yandex_music.exceptions import DeviceAuthError, NetworkError, TimedOutError

from app.core.proxy import apply_internal_no_proxy

apply_internal_no_proxy()

from app import __version__
from app.cli.auth_flow import (
    clear_pending,
    has_offline_session,
    load_pending,
    merge_pending,
    save_pending,
)
from app.core.config import settings
from app.core.exceptions import (
    ExportError,
    LLMError,
    NotFoundError,
    QuotaExceededError,
    RetrievalError,
    ScoringError,
    SecurityError,
    YandexMusicError,
)
from app.core.proxy import get_outbound_proxy_url
from app.core.security import decrypt_token
from app.db.session import AsyncSessionLocal
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import DeviceFlowPollResponse
from app.schemas.llm import MusicProfile
from app.services.auth_service import AuthService
from app.services.service_factory import (
    build_llm_service,
    build_playlist_service,
    build_retrieval_service,
    build_scoring_service,
    build_yandex_music_service,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]

_DB_HINT = (
    "PostgreSQL недоступен ({detail}).\n"
    "Профиль и токен в .auth/pending.json — запись в БД: make auth-poll"
)


def _format_db_error(exc: BaseException) -> str:
    text = str(exc).strip()
    return text or type(exc).__name__


def _yandex_error(exc: BaseException) -> click.ClickException:
    return click.ClickException(str(exc))


@click.group()
@click.version_option(__version__, prog_name="prompt-dj")
def cli() -> None:
    """Prompt DJ — CLI для отладки."""


@cli.command("db")
def db_init() -> None:
    """Применить миграции Alembic (upgrade head)."""
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    click.echo("Database schema is up to date.")


@cli.group("auth")
def auth() -> None:
    """Команды авторизации."""


def _warn_if_no_proxy() -> None:
    if get_outbound_proxy_url() is None:
        click.echo(
            "Подсказка: задайте HTTPS_PROXY (корпоративный прокси), см. .env.example.",
            err=True,
        )


def _db_unavailable(exc: BaseException) -> click.ClickException:
    return click.ClickException(_DB_HINT.format(detail=_format_db_error(exc)))


async def _with_auth_service[T](fn: Callable[[AuthService], Awaitable[T]]) -> T:
    try:
        async with AsyncSessionLocal() as db:
            service = AuthService(
                db=db,
                yandex=build_yandex_music_service(),
                user_repo=UserRepository(db),
                session_repo=SessionRepository(db),
            )
            return await fn(service)
    except SecurityError as exc:
        raise click.ClickException(str(exc)) from exc
    except (TimeoutError, OSError, OperationalError, DBAPIError) as exc:
        raise _db_unavailable(exc) from exc


async def _save_session(
    access_token: str,
    *,
    yandex_uid: int | None = None,
    login: str | None = None,
) -> DeviceFlowPollResponse:
    return await _with_auth_service(
        lambda service: service.create_session_from_token(
            access_token,
            yandex_uid=yandex_uid,
            login=login,
        )
    )


def _print_device_code(user_code: str, verification_url: str) -> None:
    click.echo("")
    click.echo("Подтвердите вход (браузер или телефон с мобильным интернетом):")
    click.echo(f"  URL:  {verification_url}")
    click.echo(f"  Код:  {user_code}")
    click.echo("")


@auth.command("start")
def auth_start() -> None:
    """Шаг 1: запросить код (БД не нужна). Сохраняет device_code в .auth/pending.json."""
    _warn_if_no_proxy()
    asyncio.run(_auth_start())


async def _auth_start() -> None:
    yandex = build_yandex_music_service()
    try:
        code = await yandex.request_device_code()
    except (TimedOutError, NetworkError, YandexMusicError) as exc:
        raise _yandex_error(exc) from exc

    path = save_pending(
        {
            "device_code": code.device_code,
            "user_code": code.user_code,
            "verification_url": code.verification_url,
            "expires_in": code.expires_in,
            "interval": code.interval,
        }
    )
    _print_device_code(code.user_code, code.verification_url)
    click.echo(f"device_code сохранён: {path}")
    click.echo("Дальше: подтвердите код, затем `prompt-dj auth poll`")


@auth.command("poll")
@click.option("--device-code", default=None, help="Иначе читается из .auth/pending.json")
@click.option("--wait", is_flag=True, help="Опрашивать Яндекс до подтверждения (нужен интернет)")
def auth_poll(device_code: str | None, wait: bool) -> None:
    """Шаг 2: опрос Яндекса + сохранение сессии в PostgreSQL."""
    pending = load_pending() or {}
    if not has_offline_session(pending):
        _warn_if_no_proxy()
    asyncio.run(_auth_poll(pending, device_code, wait))


async def _auth_poll(
    pending: dict[str, object],
    device_code: str | None,
    wait: bool,
) -> None:
    saved_token = pending.get("access_token")

    if saved_token:
        uid = pending.get("yandex_uid")
        login = pending.get("login")
        if uid is None or login is None:
            try:
                uid, login = await build_yandex_music_service().resolve_account(str(saved_token))
            except (TimedOutError, NetworkError, YandexMusicError) as exc:
                raise click.ClickException(
                    f"Нет профиля в pending.json, Яндекс недоступен ({exc}). "
                    "На хосте с HTTPS_PROXY: prompt-dj auth poll"
                ) from exc
            merge_pending({"yandex_uid": uid, "login": login})
            click.echo("Профиль Яндекса сохранён в pending.json.")
        else:
            click.echo("Сохраняю сессию в PostgreSQL (без запросов к Яндексу)...")
        result = await _save_session(
            str(saved_token),
            yandex_uid=int(uid),
            login=str(login),
        )
        clear_pending()
        click.echo("Авторизация успешна.")
        click.echo(f"session_id: {result.session_id}")
        return

    code = device_code or pending.get("device_code")
    if not code:
        raise click.ClickException(
            "Нет device_code. Сначала `prompt-dj auth start` или передайте --device-code."
        )

    interval = int(pending.get("interval", 5))
    timeout = int(pending.get("expires_in", settings.yandex.device_flow_timeout_sec))
    deadline = time.monotonic() + timeout
    yandex = build_yandex_music_service()

    while True:
        try:
            token = await yandex.poll_device_token(str(code))
        except DeviceAuthError as exc:
            clear_pending()
            raise click.ClickException(str(exc)) from exc
        except (TimedOutError, NetworkError, YandexMusicError) as exc:
            raise _yandex_error(exc) from exc

        if token is None:
            if not wait:
                click.echo("status: pending (повторите позже: prompt-dj auth poll)")
                return
            if time.monotonic() >= deadline:
                raise click.ClickException(f"Таймаут {timeout} сек — код не подтверждён")
            click.echo("ожидание подтверждения на Яндексе...")
            await asyncio.sleep(interval)
            continue

        try:
            uid, login = await yandex.resolve_account(token.access_token)
        except (TimedOutError, NetworkError, YandexMusicError) as exc:
            raise _yandex_error(exc) from exc

        merge_pending(
            {
                "access_token": token.access_token,
                "yandex_uid": uid,
                "login": login,
            }
        )
        click.echo("Яндекс: вход подтверждён. Подключаюсь к PostgreSQL...")
        result = await _save_session(
            token.access_token,
            yandex_uid=uid,
            login=login,
        )
        clear_pending()
        click.echo("Авторизация успешна.")
        click.echo(f"session_id: {result.session_id}")
        return


@auth.command("import-token")
@click.argument("access_token")
def auth_import_token(access_token: str) -> None:
    """Импорт OAuth-токена с другой машины (где прошли Device Flow)."""
    _warn_if_no_proxy()
    asyncio.run(_auth_import_token(access_token))


async def _auth_import_token(access_token: str) -> None:
    try:
        result = await _save_session(access_token)
    except (TimedOutError, NetworkError, YandexMusicError) as exc:
        raise _yandex_error(exc) from exc

    click.echo("Сессия создана.")
    click.echo(f"session_id: {result.session_id}")


@auth.command("test")
def auth_test() -> None:
    """Device Flow за один запуск (нужен непрерывный интернет на время ожидания)."""
    asyncio.run(_run_auth_test())


async def _run_auth_test() -> None:
    yandex = build_yandex_music_service()

    def _on_code(code: DeviceCode) -> None:
        _print_device_code(code.user_code, code.verification_url)

    _warn_if_no_proxy()

    try:
        access_token = await yandex.device_auth(
            on_code=_on_code,
            timeout=settings.yandex.device_flow_timeout_sec,
        )
    except DeviceAuthError as exc:
        raise click.ClickException(str(exc)) from exc
    except (TimedOutError, NetworkError, YandexMusicError) as exc:
        raise _yandex_error(exc) from exc

    click.echo("Яндекс: вход подтверждён. Подключаюсь к PostgreSQL...")
    result = await _save_session(access_token)
    click.echo("Авторизация успешна.")
    click.echo(f"session_id: {result.session_id}")


@cli.group("llm")
def llm() -> None:
    """LLM Engine — парсинг промпта в MusicProfile."""


@llm.command("parse")
@click.argument("prompt")
@click.option("--track-count", type=int, default=None, help="Переопределить target_track_count")
@click.option("--instrumental-only", is_flag=True, help="Принудительно instrumental_only")
def llm_parse(prompt: str, track_count: int | None, instrumental_only: bool) -> None:
    """Разложить текстовый промпт в MusicProfile (нужен OPENAI_API_KEY)."""
    asyncio.run(_llm_parse(prompt, track_count, instrumental_only))


async def _llm_parse(
    prompt: str,
    track_count: int | None,
    instrumental_only: bool,
) -> None:
    service = build_llm_service()
    try:
        profile = await service.parse_prompt(
            prompt,
            track_count=track_count,
            instrumental_only=instrumental_only,
        )
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(profile.model_dump_json(indent=2, ensure_ascii=False))


@cli.group("retrieval")
def retrieval() -> None:
    """Retrieval Engine — сбор кандидатов из каталога Яндекс Музыки."""


@retrieval.command("fetch")
@click.option("--prompt", default=None, help="Промпт → LLM → retrieval (нужен OPENAI_API_KEY)")
@click.option(
    "--profile-json",
    type=click.Path(exists=True),
    default=None,
    help="MusicProfile JSON",
)
@click.option("--token", envvar="YANDEX_OAUTH_TOKEN", default=None, help="OAuth-токен Яндекса")
@click.option(
    "--reference-track-id",
    default=None,
    help="ID трека-референса для tracks_similar",
)
def retrieval_fetch(
    prompt: str | None,
    profile_json: str | None,
    token: str | None,
    reference_track_id: str | None,
) -> None:
    """Собрать пул кандидатов (нужен OAuth-токен и OPENAI_API_KEY при --prompt)."""
    if profile_json is None and prompt is None:
        raise click.UsageError("Укажите --prompt или --profile-json")
    if token is None:
        raise click.UsageError("Укажите --token или YANDEX_OAUTH_TOKEN")
    asyncio.run(_retrieval_fetch(prompt, profile_json, token, reference_track_id))


async def _retrieval_fetch(
    prompt: str | None,
    profile_json: str | None,
    token: str,
    reference_track_id: str | None,
) -> None:
    if profile_json is not None:
        profile = MusicProfile.model_validate_json(Path(profile_json).read_text(encoding="utf-8"))
    else:
        llm = build_llm_service()
        try:
            profile = await llm.parse_prompt(prompt or "")
        except LLMError as exc:
            raise click.ClickException(str(exc)) from exc

    service = build_retrieval_service()
    started = time.perf_counter()
    try:
        tracks = await service.collect_candidates(
            profile,
            token,
            reference_track_id=reference_track_id,
        )
    except YandexMusicError as exc:
        raise _yandex_error(exc) from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    click.echo(f"candidates: {len(tracks)}")
    click.echo(f"elapsed_ms: {elapsed_ms}")
    for track in tracks[:5]:
        artists = ", ".join(track.artists)
        click.echo(f"  - {artists} — {track.title} ({track.id})")


@cli.group("playlist")
def playlist() -> None:
    """Полный пайплайн generate (как POST /playlists/generate)."""


@playlist.command("generate")
@click.argument("prompt")
@click.option("--session-id", type=click.UUID, required=True, help="session_id из auth poll")
@click.option("--track-count", type=int, default=25, show_default=True)
@click.option("--instrumental-only", is_flag=True, default=False)
@click.option("--use-library", is_flag=True, default=False)
@click.option(
    "--diversity",
    type=click.Choice(["normal", "high"], case_sensitive=False),
    default="normal",
    show_default=True,
)
def playlist_generate(
    prompt: str,
    session_id: uuid.UUID,
    track_count: int,
    instrumental_only: bool,
    use_library: bool,
    diversity: str,
) -> None:
    """LLM → retrieval → scoring → export → PostgreSQL."""
    asyncio.run(
        _playlist_generate(
            prompt,
            session_id,
            track_count=track_count,
            instrumental_only=instrumental_only,
            use_library=use_library,
            diversity=diversity,
        )
    )


async def _playlist_generate(
    prompt: str,
    session_id: uuid.UUID,
    *,
    track_count: int,
    instrumental_only: bool,
    use_library: bool,
    diversity: str,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            session = await SessionRepository(db).get_valid(session_id)
            if session is None:
                raise click.ClickException("Invalid or expired session_id")
            service = build_playlist_service(db)
            access_token = decrypt_token(session.encrypted_token)
            result = await service.generate(
                prompt=prompt,
                track_count=track_count,
                instrumental_only=instrumental_only,
                access_token=access_token,
                login=session.user.login,
                user_id=session.user_id,
                diversity=diversity,
                use_library=use_library,
            )
    except QuotaExceededError as exc:
        raise click.ClickException(str(exc)) from exc
    except NotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc
    except YandexMusicError as exc:
        raise click.ClickException(str(exc)) from exc
    except ExportError as exc:
        raise click.ClickException(str(exc)) from exc
    except RetrievalError as exc:
        raise click.ClickException(str(exc)) from exc
    except ScoringError as exc:
        raise click.ClickException(str(exc)) from exc
    except (TimeoutError, OSError, OperationalError, DBAPIError) as exc:
        raise _db_unavailable(exc) from exc

    click.echo(result.model_dump_json(indent=2, ensure_ascii=False))


@cli.group("scoring")
def scoring() -> None:
    """Scoring Module — ранжирование кандидатов по embeddings."""


@scoring.command("rank")
@click.option("--prompt", default=None, help="Промпт → LLM → retrieval → scoring")
@click.option(
    "--profile-json",
    type=click.Path(exists=True),
    default=None,
    help="MusicProfile JSON",
)
@click.option(
    "--candidates-json",
    type=click.Path(exists=True),
    default=None,
    help="JSON-массив TrackCandidate (без retrieval)",
)
@click.option("--token", envvar="YANDEX_OAUTH_TOKEN", default=None, help="OAuth-токен Яндекса")
@click.option(
    "--reference-track-id",
    default=None,
    help="ID трека-референса для tracks_similar",
)
def scoring_rank(
    prompt: str | None,
    profile_json: str | None,
    candidates_json: str | None,
    token: str | None,
    reference_track_id: str | None,
) -> None:
    """Отранжировать кандидатов (нужен OAuth при retrieval из промпта)."""
    if profile_json is None and prompt is None:
        raise click.UsageError("Укажите --prompt или --profile-json")
    if candidates_json is None and token is None and prompt is None:
        raise click.UsageError("Укажите --candidates-json или --token/--prompt для retrieval")
    asyncio.run(_scoring_rank(prompt, profile_json, candidates_json, token, reference_track_id))


async def _scoring_rank(
    prompt: str | None,
    profile_json: str | None,
    candidates_json: str | None,
    token: str | None,
    reference_track_id: str | None,
) -> None:
    from app.core.embedding import warmup_embedding_model
    from app.schemas.track import TrackCandidate

    user_prompt = prompt
    if profile_json is not None:
        profile = MusicProfile.model_validate_json(Path(profile_json).read_text(encoding="utf-8"))
    else:
        llm = build_llm_service()
        llm_started = time.perf_counter()
        try:
            profile = await llm.parse_prompt(prompt or "")
        except LLMError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"llm_ms: {int((time.perf_counter() - llm_started) * 1000)}")

    if candidates_json is not None:
        candidates = [
            TrackCandidate.model_validate(item)
            for item in json.loads(Path(candidates_json).read_text(encoding="utf-8"))
        ]
    else:
        if token is None:
            raise click.UsageError("Укажите --token или YANDEX_OAUTH_TOKEN")
        retrieval = build_retrieval_service()
        retrieval_started = time.perf_counter()
        try:
            candidates = await retrieval.collect_candidates(
                profile,
                token,
                reference_track_id=reference_track_id,
            )
        except YandexMusicError as exc:
            raise _yandex_error(exc) from exc
        click.echo(f"retrieval_ms: {int((time.perf_counter() - retrieval_started) * 1000)}")

    embed_pool = min(len(candidates), settings.scoring.embed_limit)
    click.echo(f"candidates: {len(candidates)}")
    click.echo(f"embed_pool: {embed_pool}")

    warmup_started = time.perf_counter()
    warmup_embedding_model()
    click.echo(f"model_warmup_ms: {int((time.perf_counter() - warmup_started) * 1000)}")

    scoring_service = build_scoring_service()
    scoring_started = time.perf_counter()
    tracks, method = await scoring_service.rank(profile, candidates, user_prompt=user_prompt)
    scoring_ms = int((time.perf_counter() - scoring_started) * 1000)
    click.echo(f"method: {method}")
    click.echo(f"ranked: {len(tracks)}")
    click.echo(f"scoring_ms: {scoring_ms}")
    for track in tracks[:10]:
        artists = ", ".join(track.artists)
        click.echo(f"  - {track.score:.3f} {artists} — {track.title} ({track.id})")


if __name__ == "__main__":
    cli()
