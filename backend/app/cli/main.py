import asyncio
import time
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
from app.core.exceptions import SecurityError, YandexMusicError
from app.core.proxy import get_outbound_proxy_url
from app.db.session import AsyncSessionLocal
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import DeviceFlowPollResponse
from app.services.auth_service import AuthService
from app.services.yandex_music_service import YandexMusicService

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
                yandex=YandexMusicService(),
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
    yandex = YandexMusicService()
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
                uid, login = await YandexMusicService().resolve_account(str(saved_token))
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
    timeout = int(pending.get("expires_in", settings.device_flow_timeout_sec))
    deadline = time.monotonic() + timeout
    yandex = YandexMusicService()

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
    yandex = YandexMusicService()

    def _on_code(code: DeviceCode) -> None:
        _print_device_code(code.user_code, code.verification_url)

    _warn_if_no_proxy()

    try:
        access_token = await yandex.device_auth(
            on_code=_on_code,
            timeout=settings.device_flow_timeout_sec,
        )
    except DeviceAuthError as exc:
        raise click.ClickException(str(exc)) from exc
    except (TimedOutError, NetworkError, YandexMusicError) as exc:
        raise _yandex_error(exc) from exc

    click.echo("Яндекс: вход подтверждён. Подключаюсь к PostgreSQL...")
    result = await _save_session(access_token)
    click.echo("Авторизация успешна.")
    click.echo(f"session_id: {result.session_id}")


if __name__ == "__main__":
    cli()
