"""Own native engine processes without changing the existing DAG object handles.

These workers supervise native imports and the already implemented small demos.
Research DAG execution remains on its established API; no broker is connected.
"""
from __future__ import annotations

import atexit
from dataclasses import asdict
from datetime import UTC, datetime
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import uuid

from fastapi import HTTPException

from app.core.integrations import SPECS

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "@investor-engine:"


def now() -> str:
    return datetime.now(UTC).isoformat()


class Supervisor:
    def __init__(self, *, startup_timeout: float = 90, demo_timeout: float = 90):
        self.lock = threading.RLock()
        self.startup_timeout = startup_timeout
        self.demo_timeout = demo_timeout
        self.rows: dict[str, dict] = {}

    def _row(self, key: str) -> dict:
        spec = next((spec for spec in SPECS if spec.key == key), None)
        if spec is None:
            raise HTTPException(404, "unknown engine")
        if key not in self.rows:
            self.rows[key] = {
                **asdict(spec), "state": "stopped", "pid": None, "import_ok": None,
                "installed": importlib.util.find_spec(spec.python_module.split(".")[0]) is not None,
                "demo_state": "unrun", "last_result": None, "error": None,
                "started_at": None, "checked_at": None, "events": [],
                "_process": None, "_event": threading.Event(), "_busy": False,
            }
        return self.rows[key]

    def _event(self, row: dict, kind: str) -> None:
        row["events"].append({"at": now(), "kind": kind})
        row["events"] = row["events"][-30:]

    def snapshot(self, key: str) -> dict:
        with self.lock:
            row = self._row(key)
            proc = row["_process"]
            if proc and proc.poll() is not None and row["state"] in {"starting", "ready"}:
                row.update(state="failed", error={"type": "WorkerExited", "message": f"worker exit {proc.returncode}"})
                self._event(row, "worker_exited")
            result = {key: value for key, value in row.items() if not key.startswith("_")}
            result["execution_scope"] = "native_import_and_bounded_demo"
            result["live_trading_enabled"] = False
            result["limits"] = {"address_space_mib": 12288, "cpu_seconds": 180,
                                "startup_timeout_seconds": self.startup_timeout, "demo_timeout_seconds": self.demo_timeout}
            result["rss_mib"] = None
            if proc and proc.poll() is None:
                try:
                    for line in Path(f"/proc/{proc.pid}/status").read_text().splitlines():
                        if line.startswith("VmRSS:"):
                            result["rss_mib"] = round(int(line.split()[1]) / 1024, 1)
                except OSError:
                    pass
            return result

    def inventory(self) -> dict:
        return {"count": len(SPECS), "engines": [self.snapshot(spec.key) for spec in SPECS],
                "scope": "native_import_and_bounded_demo", "live_trading_enabled": False}

    def start(self, key: str) -> dict:
        with self.lock:
            row = self._row(key)
            if row["_process"] and row["_process"].poll() is None:
                return self.snapshot(key)
            if not row["installed"]:
                raise HTTPException(503, "engine dependency is not installed")
            # Native smoke workers have no need for cloud/broker/LLM credentials.
            keep = {"PATH", "HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE",
                    "XDG_CACHE_HOME", "MPLCONFIGDIR", "ARTIFACT_SIGNING_KEY_PATH",
                    "PICKLE_CACHE_FOLDER_PATH_STR", "WORKSPACE_PATH", "LOG_TRACE_PATH"}
            env = {name: value for name, value in os.environ.items() if name in keep}
            env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
                       OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", TOKENIZERS_PARALLELISM="false")
            proc = subprocess.Popen(
                [sys.executable, "-m", "app.engine_runtime.worker", key], cwd=ROOT, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1, start_new_session=True,
            )
            row.update(_process=proc, state="starting", pid=proc.pid, error=None,
                       import_ok=None, started_at=now(), _busy=False)
            row["_event"].clear()
            self._event(row, "starting")
            threading.Thread(target=self._read, args=(key, proc), daemon=True).start()
            threading.Thread(target=self._watch_start, args=(key, proc), daemon=True).start()
            return self.snapshot(key)

    def _read(self, key: str, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            if not line.startswith(PREFIX):
                continue
            try:
                data = json.loads(line[len(PREFIX):])
            except ValueError:
                continue
            with self.lock:
                row = self._row(key)
                if row["_process"] is not proc:
                    return
                if data.get("type") == "ready":
                    probe = data["probe"]
                    error = {"type": "NativeImportError", "message": probe["error"]} if probe.get("error") else None
                    row.update(state="ready" if probe["import_ok"] else "failed",
                               import_ok=probe["import_ok"], error=error, checked_at=now())
                    self._event(row, row["state"])
                elif data.get("request_id") == row.get("_request_id"):
                    row.update(demo_state="passed" if data["ok"] else "failed",
                               last_result=data.get("result"), error=data.get("error"), checked_at=now())
                    self._event(row, "demo_" + row["demo_state"])
                    row["_event"].set()
        with self.lock:
            row = self._row(key)
            if row["_process"] is proc and row["state"] not in {"stopped", "failed", "timed_out"}:
                row.update(state="failed", error={"type": "WorkerExited", "message": "native worker exited unexpectedly"})
                row["_event"].set()

    def _watch_start(self, key: str, proc: subprocess.Popen) -> None:
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            with self.lock:
                row = self._row(key)
                if row["_process"] is not proc or row["state"] != "starting":
                    return
            time.sleep(0.1)
        with self.lock:
            row = self._row(key)
            if row["_process"] is proc and row["state"] == "starting":
                self._terminate(row, "timed_out")
                row["error"] = {"type": "StartupTimeout", "message": "native import exceeded the configured timeout"}

    def _terminate(self, row: dict, state: str) -> None:
        row["state"] = state
        proc = row["_process"]
        if proc and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=3)
        row["pid"] = None
        if row["demo_state"] == "running":
            row["demo_state"] = "cancelled"
        row["_busy"] = False
        row["_event"].set()
        self._event(row, state)

    def stop(self, key: str) -> dict:
        with self.lock:
            self._terminate(self._row(key), "stopped")
            return self.snapshot(key)

    def demo(self, key: str) -> dict:
        with self.lock:
            row = self._row(key)
            if self.snapshot(key)["state"] != "ready":
                raise HTTPException(409, "start the engine and wait for ready before verifying it")
            if row["_busy"]:
                raise HTTPException(409, "an engine verification is already running")
            row.update(_busy=True, demo_state="running", _request_id=uuid.uuid4().hex)
            request_id = row["_request_id"]
            row["_event"].clear()
            self._event(row, "demo_running")
            proc = row["_process"]
            try:
                proc.stdin.write(json.dumps({"action": "demo", "request_id": row["_request_id"]}) + "\n")
                proc.stdin.flush()
            except (OSError, ValueError):
                row["_busy"] = False
                raise HTTPException(503, "native worker is unavailable") from None
            done = row["_event"]
        completed = done.wait(self.demo_timeout)
        with self.lock:
            if row["_process"] is not proc or row.get("_request_id") != request_id:
                return self.snapshot(key)
            row["_busy"] = False
            if not completed:
                self._terminate(row, "timed_out")
                row.update(demo_state="failed", error={"type": "DemoTimeout", "message": "bounded demo exceeded the configured timeout"})
            return self.snapshot(key)

    def close(self) -> None:
        with self.lock:
            for row in self.rows.values():
                self._terminate(row, "stopped")


supervisor = Supervisor()
atexit.register(supervisor.close)
