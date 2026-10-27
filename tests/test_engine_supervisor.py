"""Native process lifecycle and failure handling; no broker or remote model calls."""
import json
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.engine_runtime.supervisor import Supervisor
import app.engine_runtime.supervisor as module


def wait_state(manager, key, expected, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = manager.snapshot(key)
        if row["state"] in expected:
            return row
        time.sleep(.05)
    raise AssertionError(manager.snapshot(key))


def test_engine_management_is_authenticated(monkeypatch):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "engine-test-only")
    client = TestClient(app)
    for method, path in [("GET", ""), ("POST", "/nautilus/start"),
                         ("POST", "/nautilus/stop"), ("POST", "/nautilus/verify")]:
        assert client.request(method, "/api/v1/ops/engines" + path).status_code == 401
    response = client.get("/api/v1/ops/engines", headers={"Authorization": "Bearer engine-test-only"})
    assert response.status_code == 200
    assert response.json()["count"] == 12
    assert response.json()["live_trading_enabled"] is False
    assert client.post("/api/v1/ops/engines/not-an-engine/start", headers={"Authorization": "Bearer engine-test-only"}).status_code == 404


def test_real_nautilus_worker_start_demo_stop_and_restart():
    manager = Supervisor()
    try:
        assert manager.start("nautilus")["state"] in {"starting", "ready"}
        row = wait_state(manager, "nautilus", {"ready", "failed"})
        assert row["state"] == "ready", row
        assert row["import_ok"] is True
        first = manager.rows["nautilus"]["_process"]
        assert manager.start("nautilus")["pid"] == first.pid
        checked = manager.demo("nautilus")
        assert checked["demo_state"] == "passed", checked
        assert checked["last_result"]["native_call"].startswith("Nautilus")
        assert checked["live_trading_enabled"] is False
        assert manager.stop("nautilus")["state"] == "stopped"
        assert first.poll() is not None
        assert manager.start("nautilus")["pid"] != first.pid
        assert wait_state(manager, "nautilus", {"ready", "failed"})["state"] == "ready"
    finally:
        manager.close()


def test_native_start_timeout_terminates_only_its_worker(monkeypatch):
    original = subprocess.Popen
    def stuck(*args, **kwargs):
        return original([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
    monkeypatch.setattr(module.subprocess, "Popen", stuck)
    manager = Supervisor(startup_timeout=.15)
    try:
        manager.start("nautilus")
        row = wait_state(manager, "nautilus", {"timed_out"}, timeout=5)
        assert row["error"]["type"] == "StartupTimeout"
        assert manager.rows["nautilus"]["_process"].poll() is not None
    finally:
        manager.close()


def test_demo_timeout_and_absent_credentials_in_worker(monkeypatch):
    original = subprocess.Popen
    monkeypatch.setenv("PRIVATE_BROKER_TOKEN", "must-not-reach-worker")
    captured = {}
    ready = json.dumps({"type": "ready", "probe": {"import_ok": True, "error": None}})
    code = f"import time; print('@investor-engine:'+{ready!r},flush=True); input(); time.sleep(30)"
    def stuck_demo(*args, **kwargs):
        captured.update(kwargs["env"])
        return original([sys.executable, "-c", code], **kwargs)
    monkeypatch.setattr(module.subprocess, "Popen", stuck_demo)
    manager = Supervisor(demo_timeout=.15)
    try:
        manager.start("nautilus")
        assert wait_state(manager, "nautilus", {"ready"})["state"] == "ready"
        row = manager.demo("nautilus")
        assert row["state"] == "timed_out" and row["demo_state"] == "failed"
        assert row["error"]["type"] == "DemoTimeout"
        assert "PRIVATE_BROKER_TOKEN" not in captured
        assert manager.rows["nautilus"]["_process"].poll() is not None
    finally:
        manager.close()
