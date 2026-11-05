from app.core.llm_config import (
    DEFAULT_KODIK_IMAGE_MODEL,
    DEFAULT_OPENAI_IMAGE_MODEL,
    resolve_openai_image_model,
    uses_qwen_image_model,
)
from app.schemas.llm import MusicProfile
from app.services.cover_art_service import build_cover_image_prompt, image_generate_kwargs

SAMPLE_PROFILE = MusicProfile(
    playlist_title="Ночной неон",
    playlist_description="Синтвейв для ночной поездки",
    primary_genres=["synthwave", "retrowave"],
    mood_tags=["nocturnal", "atmospheric"],
    vocal_type="any",
    reference_artists=["Kavinsky", "Perturbator", "Gunship", "Timecop1983"],
    search_queries=["synthwave night", "retrowave neon", "dark synth"],
    target_track_count=25,
)


def test_build_cover_image_prompt_includes_mood_and_no_text_rule() -> None:
    prompt = build_cover_image_prompt(SAMPLE_PROFILE, "dark synthwave for coding")
    assert "Ночной неон" in prompt
    assert "nocturnal" in prompt
    assert "synthwave" in prompt
    assert "No text" in prompt
    assert "dark synthwave" in prompt


def test_build_cover_image_prompt_truncates_long_user_prompt() -> None:
    long_prompt = "x" * 500
    built = build_cover_image_prompt(SAMPLE_PROFILE, long_prompt)
    assert len(built) <= 900


def test_resolve_openai_image_model_kodik_default() -> None:
    from app.core.config import Settings

    cfg = Settings(openai_base_url="https://api.kodikrouter.ru/v1")
    assert resolve_openai_image_model(cfg) == DEFAULT_KODIK_IMAGE_MODEL


def test_resolve_openai_image_model_openai_default() -> None:
    from app.core.config import Settings

    cfg = Settings(openai_api_key="sk-openai-test", openai_base_url="")
    assert resolve_openai_image_model(cfg) == DEFAULT_OPENAI_IMAGE_MODEL


def test_image_generate_kwargs_qwen_uses_aspect_ratio_and_resolution() -> None:
    kwargs = image_generate_kwargs("qwen/qwen-image-3-pro", "test prompt")
    assert kwargs["model"] == "qwen/qwen-image-3-pro"
    assert kwargs["extra_body"] == {"aspect_ratio": "1:1", "resolution": "1K"}
    assert "size" not in kwargs


def test_image_generate_kwargs_dalle_uses_size() -> None:
    kwargs = image_generate_kwargs("dall-e-2", "test prompt")
    assert kwargs["size"] == "512x512"
    assert "extra_body" not in kwargs


def test_uses_qwen_image_model() -> None:
    assert uses_qwen_image_model("qwen/qwen-image-3-pro") is True
    assert uses_qwen_image_model("dall-e-2") is False
