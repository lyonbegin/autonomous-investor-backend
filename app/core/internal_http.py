from __future__ import annotations

import json
from typing import Any
from urllib import error, request
from urllib.parse import urlsplit


class _ServiceRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.has_header("Authorization"):
            before, after = urlsplit(req.full_url), urlsplit(newurl)
            if (before.scheme, before.netloc) != (after.scheme, after.netloc):
                raise error.HTTPError(req.full_url, 502, "authenticated cross-origin redirect blocked", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def internal_json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 20,
    headers: dict[str, str] | None = None,
    max_response_bytes: int = 3_000_000,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "AUTONOMOUS-INVESTOR/InternalService/1.0",
    }
    request_headers.update(headers or {})
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    req = request.Request(url, data=body, method=method, headers=request_headers)
    try:
        open_request = request.build_opener(_ServiceRedirect()).open if req.has_header("Authorization") else request.urlopen
        with open_request(req, timeout=timeout) as response:
            raw = response.read(max_response_bytes + 1)
            if len(raw) > max_response_bytes:
                raise ValueError("internal response exceeds size limit")
            result = json.loads(raw.decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"internal upstream HTTP {exc.code}: {detail[:500]}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"internal upstream returned {type(result).__name__}")
    return result
