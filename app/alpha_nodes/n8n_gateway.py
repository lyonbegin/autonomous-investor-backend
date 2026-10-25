"""Internal-only gateway to trigger a *real* n8n webhook, not a Python fallback.

The operator must provision and publish the actual n8n workflows. There is no
silent fallback to the synthetic direct scenario executor when n8n is absent.
"""
from __future__ import annotations

import json
import os
from urllib import error, parse, request

from fastapi import HTTPException

from app.alpha_nodes.scenario_simulator import SCENARIOS


def state() -> dict:
    base = os.getenv("N8N_INTERNAL_WEBHOOK_BASE", "").strip()
    return {
        "configured": bool(base),
        "mode": "real_n8n_webhook_worker" if base else "not_configured",
        "n8n_url_disclosed": False,
        "supported_scenarios": len(SCENARIOS),
        "live_broker_orders": False,
    }


def dispatch(scenario_id: str, interval_ms: int = 160) -> dict:
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Unknown scenario")
    if not 0 <= interval_ms <= 1500:
        raise HTTPException(status_code=422, detail="interval_ms must be 0..1500")
    base = os.getenv("N8N_INTERNAL_WEBHOOK_BASE", "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="n8n is not configured; set N8N_INTERNAL_WEBHOOK_BASE")
    parsed = parse.urlparse(base)
    allowed_internal = parsed.hostname in {"n8n", "localhost", "127.0.0.1", "::1", "host.docker.internal", "investment-n8n-main.railway.internal"}
    if parsed.username or parsed.password or not parsed.netloc or (
        parsed.scheme != "https" and not (parsed.scheme == "http" and allowed_internal)
    ):
        raise HTTPException(status_code=503, detail="n8n base URL must be HTTPS or loopback/internal n8n host")
    # A fixed path per already defined scenario, not arbitrary SSRF input.
    target = base + "/webhook/ai-scenario-" + scenario_id
    body = json.dumps({"scenario_id": scenario_id, "interval_ms": interval_ms}).encode()
    extra_token = os.getenv("N8N_WEBHOOK_AUTH_TOKEN", "").strip()
    headers = {"Content-Type": "application/json"}
    if extra_token:
        headers["X-Autonomous-Webhook-Token"] = extra_token
    http_request = request.Request(target, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(http_request, timeout=14) as response:
            if response.status not in (200, 201, 202):
                raise HTTPException(status_code=502, detail="n8n webhook returned unsuccessful status")
            raw = response.read(131073)
            if len(raw) > 131072:
                raise HTTPException(status_code=502, detail="n8n webhook response too large")
            result = json.loads(raw.decode())
    except (error.URLError, OSError, ValueError, UnicodeError) as exc:
        raise HTTPException(status_code=502, detail="n8n webhook unavailable or returned invalid JSON") from exc
    if not isinstance(result, dict) or not isinstance(result.get("run_id"), str):
        raise HTTPException(status_code=502, detail="n8n did not return a scenario run_id")
    if result.get("scenario_id") != scenario_id:
        raise HTTPException(status_code=502, detail="n8n returned wrong scenario_id")
    return {
        "run_id": result["run_id"], "scenario_id": scenario_id,
        "state": result.get("state", "queued"), "started_via": "real_n8n_webhook",
        "poll": f"/api/v1/alpha/scenarios/runs/{result['run_id']}",
    }
