"""Real n8n gateway does not silently invoke direct synthetic runner."""
from __future__ import annotations

import io
import json
from urllib import error

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.alpha_nodes import n8n_gateway

client = TestClient(app)
HEADERS = {"Authorization": "Bearer n8n-gateway-test-token"}


@pytest.fixture(autouse=True)
def config(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "n8n-gateway-test-token")
    monkeypatch.setenv("SCENARIO_DB_PATH", str(tmp_path / "gateway.sqlite3"))
    monkeypatch.delenv("N8N_INTERNAL_WEBHOOK_BASE", raising=False)
    monkeypatch.delenv("N8N_WEBHOOK_AUTH_TOKEN", raising=False)


def test_n8n_unconfigured_rejects_dispatch_without_creating_synthetic_run():
    before = client.get("/api/v1/alpha/scenarios/infra", headers=HEADERS).json()
    assert before["configured"] is False
    out = client.post("/api/v1/alpha/scenarios/01-new-strategy/dispatch", headers=HEADERS)
    assert out.status_code == 503
    assert "not configured" in out.text


def test_real_webhook_dispatch_via_mocked_urllib(monkeypatch):
    monkeypatch.setenv("N8N_INTERNAL_WEBHOOK_BASE", "http://127.0.0.1:5678")
    monkeypatch.setenv("N8N_WEBHOOK_AUTH_TOKEN", "test-secret-for-internal-only")
    called = {}

    class FakeResponse:
        status = 202
        def read(self, size):
            return json.dumps({
                "run_id": "from-real-n8n-operator-id",
                "scenario_id": "04-partial-fill", "state": "queued",
            }).encode()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_open(req, timeout):
        called["url"] = req.full_url
        called["body"] = json.loads(req.data.decode())
        called["auth"] = req.get_header("X-autonomous-webhook-token")
        assert timeout == 14
        return FakeResponse()

    monkeypatch.setattr(n8n_gateway.request, "urlopen", fake_open)
    resp=client.post("/api/v1/alpha/scenarios/04-partial-fill/dispatch?interval_ms=300",headers=HEADERS)
    assert resp.status_code == 202, resp.text
    assert resp.json()["started_via"] == "real_n8n_webhook"
    assert resp.json()["run_id"] == "from-real-n8n-operator-id"
    assert called["url"].endswith("/webhook/ai-scenario-04-partial-fill")
    assert called["body"]["interval_ms"] == 300
    assert called["auth"] == "test-secret-for-internal-only"


def test_fail_closed_on_n8n_errors(monkeypatch):
    monkeypatch.setenv("N8N_INTERNAL_WEBHOOK_BASE", "http://127.0.0.1:5678")
    def unreachable(req, timeout):
        raise error.URLError("connection refused")
    monkeypatch.setattr(n8n_gateway.request, "urlopen", unreachable)
    response = client.post("/api/v1/alpha/scenarios/02-version-update/dispatch",headers=HEADERS)
    assert response.status_code == 502
    assert "n8n" in response.text


def test_n8n_gateway_rejects_untrusted_http_hosts(monkeypatch):
    monkeypatch.setenv("N8N_INTERNAL_WEBHOOK_BASE", "http://public.example.com")
    assert client.post("/api/v1/alpha/scenarios/01-new-strategy/dispatch",headers=HEADERS).status_code == 503
    assert client.get("/api/v1/alpha/scenarios/infra").status_code == 401
