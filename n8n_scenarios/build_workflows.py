#!/usr/bin/env python3
"""Generate ten importable n8n 2.x workflows from the *same* scenario catalog.

No credentials/API tokens embedded. Every Webhook -> HTTP Request chain invokes
the authenticated backend step endpoint once; backend owns all invariant checks.
Run from project root: python n8n_scenarios/build_workflows.py
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.alpha_nodes.scenario_catalog import SCENARIOS

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "workflows"
API_BASE = "http://api:8000/api/v1/alpha/scenarios/internal"
CALLBACK_EXPRESSION = "={{ $env.INVESTMENT_SCENARIO_CALLBACK_KEY }}"
RUN_ID_EXPRESSION = "{{ $('Scenario Webhook').first().json.body.run_id }}"


def node_id(scenario_id: int, key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"autonomous-investor-scenario-{scenario_id}-{key}"))


def workflow(scenario_id: int) -> dict:
    spec = SCENARIOS[scenario_id]
    webhook_name = "Scenario Webhook"
    nodes = [{
        "id": node_id(scenario_id, "webhook"),
        "name": webhook_name,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2.1,
        "position": [240, 300],
        "webhookId": node_id(scenario_id, "webhook-public-id"),
        "parameters": {
            "httpMethod": "POST",
            "path": f"ai-investment-scenario-{scenario_id:02d}",
            "responseMode": "onReceived",
            "options": {},
        },
    }]
    connections: dict = {}
    previous = webhook_name
    for i, step in enumerate(spec["steps"]):
        name = f'{i + 1:02d} {step["flow"]} · {step["label"]}'
        # n8n uses expression syntax for node parameters; workflow JSON is not code execution.
        url = (f"{API_BASE}/runs/{RUN_ID_EXPRESSION}/steps/{step['id']}")
        nodes.append({
            "id": node_id(scenario_id, step["id"]),
            "name": name,
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [520 + (i % 5) * 270, 180 + (i // 5) * 200],
            "notesInFlow": True,
            "notes": f"{step['flow']} · {step['label']}\n합성 시나리오 검사: {step['action']}({step['params']})\n실거래 주문 없음",
            "parameters": {
                "method": "POST",
                "url": url,
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [{
                        "name": "X-Scenario-Callback-Key",
                        "value": CALLBACK_EXPRESSION,
                    }]
                },
                "options": {"timeout": 30000},
            },
        })
        connections[previous] = {"main": [[{"node": name, "type": "main", "index": 0}]]}
        previous = name

    return {
        "id": f"INVESTSCENARIO{scenario_id:02d}",
        "name": f"Investment QA {scenario_id:02d} · {spec['title']}",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "all",
                     "saveDataErrorExecution": "all"},
        "staticData": None,
        "pinData": {},
        "active": False,
        "tags": [],
    }


def generate() -> list[Path]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = []
    for scenario_id in sorted(SCENARIOS):
        path = OUTPUT / f"investment-scenario-{scenario_id:02d}.json"
        path.write_text(json.dumps(workflow(scenario_id), ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        files.append(path)
    return files


if __name__ == "__main__":
    results = generate()
    print(f"Generated {len(results)} n8n workflows; "
          f"{sum(len(workflow(s)['nodes']) for s in SCENARIOS)} nodes total")
    for result in results:
        print(result)
