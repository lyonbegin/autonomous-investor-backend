"""Cross-branch contracts and authentication, using only temporary local data."""
import asyncio
from urllib import error, request
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core import tradingview, quant_lab
from app.core.internal_http import _ServiceRedirect


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "local-integration-test-only")
    monkeypatch.setattr(tradingview, "DB_PATH", str(tmp_path / "sources.sqlite"))
    monkeypatch.setattr(quant_lab, "DB_PATH", str(tmp_path / "quant.sqlite"))
    return {"Authorization": "Bearer local-integration-test-only"}


def test_restored_service_routes_require_operator_auth(configured):
    client = TestClient(app)
    for method, path in [
        ("GET", "/api/v1/tradingview/ideas"),
        ("POST", "/api/v1/tradingview/backfill/ideas"),
        ("POST", "/api/v1/tradingview/candidates/example/agent-plans"),
        ("POST", "/api/v1/quant/macro/refresh"),
    ]:
        response = client.request(method, path)
        # Unknown paths are not evidence of a working authorization gate.
        assert response.status_code == 401, (path, response.text)
    assert client.get("/api/v1/tradingview/ideas", headers=configured).status_code == 200
    assert client.get("/health").status_code == 200


def test_both_scenario_contracts_and_legacy_engine_palette_survive(configured):
    client = TestClient(app)
    synthetic = client.get("/api/v1/alpha/scenarios", headers=configured)
    callbacks = client.get("/api/v1/alpha/scenario-control/catalog", headers=configured)
    assert synthetic.status_code == callbacks.status_code == 200
    assert synthetic.json()["count"] == callbacks.json()["count"] == 10
    paths = app.openapi()["paths"]
    assert "/api/v1/alpha/scenarios/{scenario_id}/dispatch" in paths
    assert "/api/v1/alpha/scenario-control/internal/runs/{run_id}/steps/{step_id}" in paths
    assert "/api/v1/quant/experiments" in paths


def test_public_api_forwards_upstream_token_only_on_server(monkeypatch):
    from public_api import main as public

    token = "test-only-upstream-token"
    monkeypatch.setenv("PUBLIC_TRADINGVIEW_TOKEN", token)
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(200, json={"count": 0, "items": []})

    original = httpx.AsyncClient
    monkeypatch.setattr(public.httpx, "AsyncClient", lambda **kw: original(
        transport=httpx.MockTransport(respond), **kw))
    result = asyncio.run(public._get(public.TV_API, "/api/v1/tradingview/ideas"))
    assert seen[0].headers["Authorization"] == "Bearer " + token
    assert token not in str(result)


def test_quant_service_token_is_not_sent_to_other_origins(monkeypatch):
    monkeypatch.setenv("TRADINGVIEW_SERVICE_TOKEN", "test-only-service-token")
    calls = []
    monkeypatch.setattr(quant_lab, "internal_json_request", lambda url, **kw: calls.append((url, kw)) or {})
    quant_lab._json_request(quant_lab.TRADINGVIEW_SERVICE_URL + "/health")
    quant_lab._json_request("https://unrelated.example/health")
    assert "Authorization" in calls[0][1]["headers"]
    assert "Authorization" not in calls[1][1]["headers"]


def test_internal_service_redirect_does_not_forward_auth_to_other_origin():
    original = request.Request("http://127.0.0.1:8001/source", headers={"Authorization": "Bearer test-only"})
    handler = _ServiceRedirect()
    with pytest.raises(error.HTTPError, match="cross-origin redirect blocked"):
        handler.redirect_request(original, None, 302, "Found", {}, "http://127.0.0.1:8002/other")
    same = handler.redirect_request(original, None, 302, "Found", {}, "http://127.0.0.1:8001/other")
    assert same.get_header("Authorization") == "Bearer test-only"
