from __future__ import annotations

import json
from typing import Any
from urllib import error, request


def internal_json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {
        "Accept": "application/json",
        "User-Agent": "AUTONOMOUS-INVESTOR/InternalService/1.0",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=body, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"internal upstream HTTP {exc.code}: {detail[:500]}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"internal upstream returned {type(result).__name__}")
    return result
