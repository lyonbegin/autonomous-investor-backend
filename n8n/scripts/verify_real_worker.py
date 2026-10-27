#!/usr/bin/env python3
"""Actual n8n webhook -> Redis Worker -> FastAPI scenario integration proof."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

BACKEND = "http://127.0.0.1:8000"
TOKEN = os.environ["CI_SCENARIO_TOKEN"]
IDS = [
    "01-new-strategy","02-version-update","03-capital-race","04-partial-fill",
    "05-long-backtest","06-strategy-drift","07-broker-timeout","08-agent-crash",
    "09-unsupported-pine","10-strategy-retire",
]


def call(path: str, method: str = "GET"):
    req = urllib.request.Request(
        BACKEND + path, method=method,
        headers={"Authorization": "Bearer " + TOKEN},
        data=b"{}" if method == "POST" else None,
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read())


def main():
    infra = call("/api/v1/alpha/scenarios/infra")
    assert infra["configured"] is True, infra
    runs = []
    for scenario in IDS:
        result = call(f"/api/v1/alpha/scenarios/{scenario}/dispatch", "POST")
        assert result["scenario_id"] == scenario, result
        assert result["started_via"] == "real_n8n_webhook", result
        assert result["run_id"], result
        runs.append(result)
        print(f"N8N_WEBHOOK_DISPATCH_OK {scenario} {result['run_id'][:12]}", flush=True)
    deadline = time.monotonic() + 135
    pending = {r["run_id"]: r["scenario_id"] for r in runs}
    done = []
    while pending and time.monotonic() < deadline:
        for run_id, scenario in list(pending.items()):
            record = call("/api/v1/alpha/scenarios/runs/" + run_id)
            if record["status"] in ("completed", "failed", "interrupted"):
                assert record["status"] == "completed", record
                assert record["progress_pct"] == 100
                assert record["completed_steps"] == record["total_steps"]
                assert len(record["events"]) == 2 * record["total_steps"]
                assert all(e["status"] in ("running", "success") for e in record["events"])
                done.append({"scenario": scenario, "run_id": run_id,
                             "events": len(record["events"]), "state": record["status"]})
                del pending[run_id]
        time.sleep(0.25)
    assert not pending, f"Timed out waiting for n8n-driven backend jobs: {pending}"
    with open("/tmp/n8n-e2e-evidence.json", "w") as f:
        json.dump({"executor": "real_n8n_webhook", "scenarios": done,
                   "total": len(done)}, f, indent=2)
    print("REAL_N8N_WEBHOOK_TO_PYTHON_SCENARIOS_COMPLETED", len(done), flush=True)


if __name__ == "__main__":
    main()
