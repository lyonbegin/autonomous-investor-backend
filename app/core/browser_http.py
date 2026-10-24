from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

DEFAULT_BROWSER_URL = "https://autonomous-investor-tradingview-browser-production.up.railway.app"


def browser_base_url() -> str:
    return (
        os.getenv("DATA_BROWSER_URL")
        or os.getenv("TRADINGVIEW_BROWSER_URL")
        or DEFAULT_BROWSER_URL
    ).rstrip("/")


def _strict() -> bool:
    return os.getenv("DATA_BROWSER_STRICT", "1").strip().lower() not in {"0", "false", "no", "off"}


def _gateway_fetch(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: Any | None = None,
    body: str | None = None,
    warmup_url: str | None = None,
    timeout: int = 40,
) -> dict[str, Any]:
    payload = {
        "url": url,
        "method": method,
        "headers": headers or {},
        "json_body": json_body,
        "body": body,
        "warmup_url": warmup_url,
        "timeout_ms": max(1000, min(int(timeout * 1000), 120000)),
    }
    req = request.Request(
        browser_base_url() + "/v1/http/fetch",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AUTONOMOUS-INVESTOR/DataBrowserClient/2.0",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout + 10) as response:
            wrapper = json.loads(response.read().decode("utf-8"))
    except Exception:
        if _strict():
            raise
        raise

    status = int(wrapper.get("status") or 0)
    if status >= 400:
        hdrs = wrapper.get("headers") or {}
        raise error.HTTPError(
            url,
            status,
            f"Upstream HTTP {status} via Chromium worker",
            hdrs,
            None,
        )
    return wrapper


def browser_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: Any | None = None,
    body: str | None = None,
    warmup_url: str | None = None,
    timeout: int = 40,
) -> Any:
    wrapper = _gateway_fetch(
        url,
        method=method,
        headers=headers,
        json_body=payload,
        body=body,
        warmup_url=warmup_url,
        timeout=timeout,
    )
    if wrapper.get("json") is not None:
        return wrapper["json"]
    text = wrapper.get("text")
    if text is None:
        text = wrapper.get("text_preview") or ""
    return json.loads(text)


def browser_text(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: Any | None = None,
    body: str | None = None,
    warmup_url: str | None = None,
    timeout: int = 40,
) -> str:
    wrapper = _gateway_fetch(
        url,
        method=method,
        headers=headers,
        json_body=payload,
        body=body,
        warmup_url=warmup_url,
        timeout=timeout,
    )
    if wrapper.get("text") is not None:
        return str(wrapper["text"])
    if wrapper.get("json") is not None:
        return json.dumps(wrapper["json"], ensure_ascii=False)
    return str(wrapper.get("text_preview") or "")
