#!/usr/bin/env python3
"""API-level smoke tester. Set SCENARIO_SMOKE_BASE and ALPHA_NODE_API_KEY.

Real n8n mode: validates the published n8n webhook + individual HTTP nodes
through backend callback logs. No broker/native engine calls are made.
"""
from __future__ import annotations

import json
import os
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = os.getenv("SCENARIO_SMOKE_BASE", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("ALPHA_NODE_API_KEY", "")
MODE = os.getenv("SCENARIO_SMOKE_MODE", "n8n")
TIMEOUT = int(os.getenv("SCENARIO_SMOKE_TIMEOUT", "180"))


def api(method: str, path: str, payload: object | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Authorization": "Bearer " + TOKEN}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(BASE + "/api/v1/alpha/scenarios" + path,
                  data=body, method=method, headers=headers)
    try:
        with urlopen(req, timeout=20) as res:
            return json.load(res)
    except HTTPError as e:
        raise RuntimeError(f"{method} {path}: {e.code} {e.read()[:600]!r}") from e


def run_one(scenario_id: int) -> tuple[int, str, int]:
    initial = api("POST", "/runs", {"scenario_id": scenario_id, "engine": MODE})
    run_id = initial["run_id"]
    expires = time.monotonic() + TIMEOUT
    print(f"[{scenario_id:02d}] START {run_id} via {MODE}", flush=True)
    while time.monotonic() < expires:
        result = api("GET", f"/runs/{run_id}")
        print(f"[{scenario_id:02d}] {result['status']} "
              f"{result['progress']}/{result['total']}", flush=True)
        if result["status"] in ("passed", "failed", "cancelled"):
            if result["status"] != "passed":
                raise AssertionError(f"{scenario_id}: {result['error']}, "
                                     f"events={result['events']}")
            assert len(result["events"]) == result["total"]
            assert all(e["origin"] == MODE for e in result["events"])
            assert all(c["passed"] for c in result["verification"])
            assert result["state"]["live_orders_sent"] == 0
            verified = api("GET", f"/runs/{run_id}/verify")
            assert verified["passed"]
            print(f"[{scenario_id:02d}] PASS: {result['total']} callback events", flush=True)
            return scenario_id, run_id, result["total"]
        time.sleep(.5)
    raise TimeoutError(f"scenario {scenario_id} timed out, run {run_id}")


if __name__ == "__main__":
    if not TOKEN:
        sys.exit("ALPHA_NODE_API_KEY is required, will not run unauthenticated")
    scenarios = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else list(range(1, 11))
    total = 0
    for scenario_id in scenarios:
        _, _, events = run_one(scenario_id)
        total += events
    print(f"PASS {len(scenarios)} scenarios; {total} actual callbacks in mode {MODE}", flush=True)
