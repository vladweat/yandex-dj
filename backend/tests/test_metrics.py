"""Tests for GET /api/v1/metrics/product."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.api.deps import get_metrics_service, require_metrics_token
from app.core.config import settings
from app.main import app
from app.schemas.metrics import ProductMetricsResponse
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def metrics_token(monkeypatch: pytest.MonkeyPatch) -> str:
    token = "test-metrics-token"
    monkeypatch.setattr(settings, "metrics_token", token)
    return token


@pytest.mark.asyncio
async def test_product_metrics_requires_token() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/metrics/product")
    assert response.status_code in {401, 503}


@pytest.mark.asyncio
async def test_product_metrics_rejects_bad_token(metrics_token: str) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/metrics/product",
            headers={"X-Metrics-Token": "wrong"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_product_metrics_ok(metrics_token: str) -> None:
    mock = AsyncMock()
    mock.product_metrics.return_value = ProductMetricsResponse(
        window_days=7,
        total_generations=10,
        latency_p50_ms=8000.0,
        latency_p95_ms=12000.0,
        latency_avg_ms=8500.0,
        full_n_rate=0.9,
        warnings_rate=0.2,
        regen_rate=0.3,
        return_7d=0.4,
        like_rate=0.75,
        dislike_rate=0.25,
        avg_clean=55.0,
        with_latency=10,
        with_feedback=4,
        regen_count=3,
        returning_users=2,
        active_users=5,
    )
    app.dependency_overrides[require_metrics_token] = lambda: None
    app.dependency_overrides[get_metrics_service] = lambda: mock
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/metrics/product?days=7",
                headers={"X-Metrics-Token": metrics_token},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["latency_p50_ms"] == 8000.0
    assert data["latency_p95_ms"] == 12000.0
    assert data["full_n_rate"] == 0.9
    assert data["warnings_rate"] == 0.2
    assert data["regen_rate"] == 0.3
    assert data["return_7d"] == 0.4
    mock.product_metrics.assert_awaited_once_with(days=7)
