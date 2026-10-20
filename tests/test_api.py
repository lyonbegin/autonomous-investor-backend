from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "autonomous-investor-backend"


def test_architecture_has_runtime():
    r = client.get("/api/v1/architecture")
    assert r.status_code == 200
    layers = r.json()["layers"]
    assert any(x["id"] == "runtime" and "NautilusTrader" in x["engines"] for x in layers)


def test_integration_catalog_contains_core_projects():
    r = client.get("/api/v1/integrations?probe_runtime=false")
    assert r.status_code == 200
    keys = {x["key"] for x in r.json()["integrations"]}
    assert {"tradingagents", "finrobot", "rdagent", "qlib", "finrlx", "nautilus"} <= keys


def test_contract_schema():
    r = client.get("/api/v1/contracts")
    assert r.status_code == 200
    body = r.json()
    assert "ResearchBundle" in body
    assert "TargetPortfolio" in body
    assert "ExecutionReport" in body
