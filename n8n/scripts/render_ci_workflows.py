#!/usr/bin/env python3
"""Render temporary n8n test imports with CI-only HTTP auth. NEVER commit output.

n8n's production workflow JSON uses a proper httpHeaderAuth credential.
CI injects its short-lived Python API token into a temp directory, not Git.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="n8n/workflows/scenarios")
    p.add_argument("--output", required=True)
    p.add_argument("--expected",type=int,default=10)
    p.add_argument("--backend", default="http://host.docker.internal:8000")
    args = p.parse_args()
    token = os.environ.get("CI_SCENARIO_TOKEN", "")
    if len(token) < 16:
        raise SystemExit("CI_SCENARIO_TOKEN must be set to a long temporary secret")
    dest = Path(args.output).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    files = sorted(Path(args.source).glob("*.json"))
    if len(files) != args.expected:
        raise SystemExit(f"expected {args.expected} workflows, got {len(files)}")
    for file in files:
        data = json.loads(file.read_text(encoding="utf-8"))
        if not data.get("id"):
            raise SystemExit(f"missing deterministic workflow ID: {file}")
        for node in data["nodes"]:
            if node["type"] != "n8n-nodes-base.httpRequest":
                continue
            params = node["parameters"]
            params["url"] = params["url"].replace(
                "http://invest-backend:8000", args.backend.rstrip("/")
            )
            if "authentication" in params:
                params["authentication"] = "none"
                params.pop("genericAuthType", None)
            params["sendHeaders"] = True
            params["headerParameters"] = {
                "parameters": [{"name": "Authorization", "value": "Bearer " + token}]
            }
        rendered = dest / file.name
        rendered.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        rendered.chmod(0o644)  # n8n container runs as uid 1000; temp CI files only
    print(f"RENDERED_TEST_WORKFLOWS={len(files)}")
    print("Temporary secret not printed. Rendered files must not be committed.")


if __name__ == "__main__":
    main()
