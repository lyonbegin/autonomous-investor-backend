"""Keep the existing operator and public UIs running on isolated review data.

The n8n verification script must have created this session's private credentials.
No credential values are printed or placed in a frontend bundle.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    directory = Path(args.state_dir).resolve()
    if not directory.is_relative_to(Path('/workspace/.onboarding')):
        raise SystemExit("review state must stay outside the source checkout in /workspace/.onboarding")
    key = json.loads((directory / "credentials.json").read_text())["ALPHA_NODE_API_KEY"]
    manifest = directory / "ui-processes.json"
    if manifest.exists():
        raise SystemExit("review UI manifest already exists; refusing to overwrite running session metadata")
    env = os.environ.copy()
    env.update(ALPHA_NODE_API_KEY=key, INVESTMENT_STUDIO_API_TOKEN=key,
        INVESTMENT_STUDIO_BACKEND_URL="http://127.0.0.1:8000", VITE_PUBLIC_DEMO="false", VITE_REVIEW_MODE="true",
        VITE_PUBLIC_API_URL="", PUBLIC_FRONTEND_BACKEND_URL="http://127.0.0.1:8006", PUBLIC_SOURCE_MODE="stored",
        TRADINGVIEW_API="http://127.0.0.1:8002", QUANT_API="http://127.0.0.1:8002",
        PUBLIC_TRADINGVIEW_TOKEN=key, PUBLIC_QUANT_TOKEN=key,
        TRADINGVIEW_SERVICE_URL="http://127.0.0.1:8002", INTEGRATED_SERVICE_URL="http://127.0.0.1:8002",
        TRADINGVIEW_SERVICE_TOKEN=key, INTEGRATED_SERVICE_TOKEN=key,
        ALPHA_TRADINGVIEW_BASE="http://127.0.0.1:8001", ALPHA_QUANT_BASE="http://127.0.0.1:8002",
        AUTONOMOUS_DB_PATH=str(directory / "sources.sqlite3"), QUANT_DB_PATH=str(directory / "quant.sqlite3"),
        INVESTOR_LOCAL_REVIEW="1", PYTHONDONTWRITEBYTECODE="1")
    # Set the config before importing modules that read their database paths.
    os.environ.update(env)
    from seed_review_data import seed
    seed(directory)
    commands = [
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8002"],
        [sys.executable, "-m", "uvicorn", "public_api.main:app", "--host", "127.0.0.1", "--port", "8006"],
        ["npm", "--prefix", "investment_studio", "run", "dev", "--", "--strictPort"],
        ["npm", "--prefix", "public_frontend", "run", "dev", "--", "--strictPort"],
    ]
    processes = []
    for index, command in enumerate(commands):
        with (directory / f"ui-{index}.log").open("a") as log:
            processes.append(subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
    manifest.write_text(json.dumps([{"pid": p.pid, "command": command} for p, command in zip(processes, commands)], indent=2))
    for port in [8002, 8006, 5177, 5178]:
        deadline = time.monotonic() + 45
        path = "/health" if port < 5000 or port in {8002, 8006} else "/"
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in processes):
                raise SystemExit("review service exited; inspect its local log")
            try:
                with urlopen(f"http://127.0.0.1:{port}{path}", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                pass
            time.sleep(.2)
        else:
            raise SystemExit(f"review service on port {port} did not become ready")
    print("REVIEW_OPERATOR_AND_PUBLIC_UI_READY; private credentials retained outside checkout")


if __name__ == "__main__":
    main()
