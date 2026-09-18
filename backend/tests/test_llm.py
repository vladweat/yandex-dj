from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.api.deps import get_current_session, get_llm_service
from app.core.config import Settings
from app.core.exceptions import LLMError
from app.core.llm_config import (
    DEFAULT_KODIK_BASE_URL,
    DEFAULT_KODIK_IMAGE_MODEL,
    DEFAULT_KODIK_MODEL,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    resolve_openai_base_url,
    resolve_openai_image_model,
    resolve_openai_model,
    uses_kodik,
)
from app.db.models.session import Session
from app.db.models.user import User
from app.main import app
from app.schemas.llm import MusicProfile
from app.services.llm_prompts import FEW_SHOT_EXAMPLES, SYSTEM_PROMPT, build_messages
from app.services.llm_service import LLMService, apply_request_hints, enrich_search_queries
from httpx import ASGITransport, AsyncClient

SAMPLE_PROFILE = MusicProfile(
    playlist_title="Ночной неон",
    playlist_description="Синтвейв для ночной поездки",
    primary_genres=["synthwave", "retrowave"],
    mood_tags=["nocturnal", "atmospheric"],
    vocal_type="any",
    reference_artists=["Kavinsky", "Perturbator", "Gunship", "Timecop1983"],
    search_queries=["synthwave night drive", "retrowave neon", "dark synth instrumental"],
    target_track_count=25,
)

DIVERSE_PROMPTS = [
    "спокойная музыка для кодинга поздней ночью, эмбиент и лоу-фай без слов",
    "музыка для тренировки с разгоном темпа",
    "Саундтрек для ночной поездки по пустому шоссе в стиле нео-нуар и синтвейв",
    "что-то грустное под дождь, пост-панк и дарквейв",
    "весёлая музыка для вечеринки, только хиты 2000-х",
    "джаз для ужина при свечах, без вокала",
    "русский рок 90-х для ностальгии",
    "classical piano for reading, calm and minimal",
    "phonk и drift beats для ночной трассы",
    "indie folk для похода в горы",
    "deep house для утренней пробежки, 40 треков",
    "lullabies and soft vocals for baby sleep",
]


def test_uses_kodik_by_base_url() -> None:
    cfg = Settings(openai_base_url="https://api.kodikrouter.ru/v1")
    assert uses_kodik(cfg) is True


def test_uses_kodik_by_key_prefix() -> None:
    cfg = Settings(openai_api_key="sk-kr_live_test")
    assert uses_kodik(cfg) is True


def test_resolve_openai_base_url_kodik_explicit() -> None:
    cfg = Settings(openai_base_url="https://api.kodikrouter.ru/v1")
    assert resolve_openai_base_url(cfg) == "https://api.kodikrouter.ru/v1"


def test_resolve_openai_base_url_kodik_from_key() -> None:
    cfg = Settings(openai_api_key="kdk_live_test")
    assert resolve_openai_base_url(cfg) == DEFAULT_KODIK_BASE_URL


def test_resolve_openai_base_url_openai_default() -> None:
    cfg = Settings(openai_api_key="sk-openai-test", openai_base_url="")
    assert resolve_openai_base_url(cfg) == DEFAULT_OPENAI_BASE_URL


def test_resolve_openai_model_kodik_default() -> None:
    cfg = Settings(openai_base_url="https://api.kodikrouter.ru/v1")
    assert resolve_openai_model(cfg) == DEFAULT_KODIK_MODEL


def test_resolve_openai_model_explicit_override() -> None:
    cfg = Settings(
        openai_base_url="https://api.kodikrouter.ru/v1",
        openai_model="anthropic/claude-sonnet-4.6",
    )
    assert resolve_openai_model(cfg) == "anthropic/claude-sonnet-4.6"


def test_resolve_openai_model_openai_default() -> None:
    cfg = Settings(openai_api_key="sk-openai-test", openai_base_url="", openai_model="")
    assert resolve_openai_model(cfg) == DEFAULT_OPENAI_MODEL


def test_resolve_openai_image_model_kodik_default() -> None:
    cfg = Settings(openai_base_url="https://api.kodikrouter.ru/v1")
    assert resolve_openai_image_model(cfg) == DEFAULT_KODIK_IMAGE_MODEL


def test_build_messages_contains_system_and_few_shots() -> None:
    messages = build_messages("тестовый промпт")
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert messages[-1] == {"role": "user", "content": "тестовый промпт"}
    assert len(messages) == 1 + len(FEW_SHOT_EXAMPLES) * 2 + 1


def test_enrich_search_queries_from_genres() -> None:
    profile = MusicProfile.model_construct(
        playlist_title="Test",
        playlist_description="Desc",
        primary_genres=["ambient", "lo-fi", "downtempo"],
        mood_tags=["calm"],
        vocal_type="any",
        reference_artists=["A", "B", "C", "D"],
        search_queries=["one"],
        target_track_count=25,
    )
    enriched = enrich_search_queries(profile)
    assert len(enriched.search_queries) >= 3


def test_apply_request_hints_track_count_and_instrumental() -> None:
    profile = apply_request_hints(
        SAMPLE_PROFILE,
        track_count=30,
        instrumental_only=True,
    )
    assert profile.target_track_count == 30
    assert profile.vocal_type == "instrumental_only"


@pytest.mark.asyncio
async def test_parse_prompt_raises_without_api_key() -> None:
    service = LLMService()
    with patch("app.services.llm_service.openai_is_configured", return_value=False):
        with pytest.raises(LLMError, match="OPENAI_API_KEY"):
            await service.parse_prompt("test")


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", DIVERSE_PROMPTS)
async def test_parse_prompt_diverse_prompts(prompt: str) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create_with_completion = AsyncMock(
        return_value=(SAMPLE_PROFILE, type("Usage", (), {"usage": None})()),
    )
    service = LLMService(client=mock_client)

    profile = await service.parse_prompt(prompt)

    assert isinstance(profile, MusicProfile)
    assert len(profile.reference_artists) >= 4
    assert len(profile.search_queries) >= 3
    call_kwargs = mock_client.chat.completions.create_with_completion.await_args.kwargs
    assert call_kwargs["messages"][-1]["content"] == prompt.strip()


@pytest.mark.asyncio
async def test_parse_prompt_wraps_upstream_errors() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create_with_completion = AsyncMock(
        side_effect=RuntimeError("upstream down"),
    )
    service = LLMService(client=mock_client)

    with pytest.raises(LLMError, match="LLM request failed"):
        await service.parse_prompt("test")


@pytest.fixture
def auth_session() -> Session:
    user = User(id=uuid4(), yandex_uid=42, login="testuser")
    session = Session(
        id=uuid4(),
        user_id=user.id,
        encrypted_token="encrypted",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.user = user
    return session


@pytest.mark.asyncio
async def test_llm_parse_endpoint_success(auth_session: Session) -> None:
    mock_llm = AsyncMock(spec=LLMService)
    mock_llm.parse_prompt.return_value = SAMPLE_PROFILE
    app.dependency_overrides[get_llm_service] = lambda: mock_llm
    app.dependency_overrides[get_current_session] = lambda: auth_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/llm/parse",
            headers={"Authorization": f"Bearer {auth_session.id}"},
            json={"prompt": "синтвейв для ночной поездки"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["profile"]["playlist_title"] == SAMPLE_PROFILE.playlist_title


@pytest.mark.asyncio
async def test_llm_parse_endpoint_unauthorized() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/llm/parse",
            json={"prompt": "test"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_llm_parse_endpoint_llm_error(auth_session: Session) -> None:
    mock_llm = AsyncMock(spec=LLMService)
    mock_llm.parse_prompt.side_effect = LLMError("OPENAI_API_KEY is not configured")
    app.dependency_overrides[get_llm_service] = lambda: mock_llm
    app.dependency_overrides[get_current_session] = lambda: auth_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/llm/parse",
            headers={"Authorization": f"Bearer {auth_session.id}"},
            json={"prompt": "test"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 503
