"""Run the existing Chromium suites against isolated local API/SQLite fixtures.

Requires dev dependencies, npm dependencies in investment_studio and Chromium.
No production API, external messages, credentials or broker orders are used.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def ready(url: str, processes: list[subprocess.Popen]) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("local service exited; inspect test service logs")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.2)
    raise TimeoutError("local service readiness timed out")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="investor-ui-") as temporary:
        directory = Path(temporary)
        token = secrets.token_hex(32)
        env = os.environ.copy()
        env.update(
            ALPHA_NODE_API_KEY=token,
            INVESTMENT_STUDIO_API_TOKEN=token,
            INVESTMENT_STUDIO_BACKEND_URL="http://127.0.0.1:8002",
            ALPHA_TRADINGVIEW_BASE="http://127.0.0.1:8003",
            ALPHA_QUANT_BASE="http://127.0.0.1:8002",
            TRADINGVIEW_SERVICE_URL="http://127.0.0.1:8003",
            INTEGRATED_SERVICE_URL="http://127.0.0.1:8002",
            TRADINGVIEW_API="http://127.0.0.1:8003",
            AUTONOMOUS_DB_PATH=str(directory / "sources.sqlite"),
            QUANT_DB_PATH=str(directory / "quant.sqlite"),
            SCENARIO_DB_PATH=str(directory / "scenarios.sqlite"),
            INVESTMENT_SCENARIO_DB_PATH=str(directory / "control.sqlite"),
            STRATEGY_OPERATIONS_DB_PATH=str(directory / "operations.sqlite"),
            INVESTMENT_FLOW_DB_PATH=str(directory / "dag.sqlite"),
            VITE_PUBLIC_DEMO="false",
            PYTHONDONTWRITEBYTECODE="1",
        )
        commands = [
            [sys.executable, "-c", "from n8n.scripts.mock_tradingview_service import Handler; "
             "from http.server import ThreadingHTTPServer; "
             "ThreadingHTTPServer(('127.0.0.1',8003),Handler).serve_forever()"],
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8002"],
            ["npm", "--prefix", "investment_studio", "run", "dev", "--", "--strictPort"],
        ]
        processes = []
        logs = []
        try:
            for index, command in enumerate(commands):
                log = (directory / f"service-{index}.log").open("w+")
                logs.append(log)
                processes.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
            ready("http://127.0.0.1:8002/health", processes)
            ready("http://127.0.0.1:5177", processes)
            return subprocess.run(
                ["npx", "playwright", "test", "--config", "playwright.local.config.ts"],
                cwd=ROOT / "investment_studio", env=env, check=False,
            ).returncode
        except Exception:
            for log in logs:
                log.seek(0)
                print(log.read().replace(token, "[REDACTED]"), file=sys.stderr)
            raise
        finally:
            for process in reversed(processes):
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for log in logs:
                log.close()


if __name__ == "__main__":
    raise SystemExit(main())
