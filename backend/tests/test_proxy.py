import os

from app.core.proxy import apply_internal_no_proxy, get_outbound_proxy_url


def test_apply_internal_no_proxy_keeps_db(monkeypatch) -> None:
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1")
    monkeypatch.setenv("NO_PROXY", "localhost")
    apply_internal_no_proxy()
    assert "db" in os.environ["NO_PROXY"].split(",")
    assert "postgres" in os.environ["no_proxy"].split(",")
    assert "redis" in os.environ["no_proxy"].split(",")


def test_get_outbound_proxy_url_prefers_https(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy-http:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy-https:8080")
    assert get_outbound_proxy_url() == "http://proxy-https:8080"
