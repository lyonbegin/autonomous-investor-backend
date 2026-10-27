from __future__ import annotations

import json
import os
import threading
import time
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError

from app.core.browser_http import browser_json

BASE_URL = "https://openapi.tossinvest.com"
TOKEN_URL = BASE_URL + "/oauth2/token"

_token_lock = threading.Lock()
_token_value: str | None = None
_token_expires_at: float = 0.0


class TossConfigError(RuntimeError):
    pass


class TossApiError(RuntimeError):
    pass


def credentials_configured() -> bool:
    return bool(os.getenv("TOSS_CLIENT_ID") and os.getenv("TOSS_CLIENT_SECRET"))


def _client_credentials() -> tuple[str, str]:
    client_id = os.getenv("TOSS_CLIENT_ID")
    client_secret = os.getenv("TOSS_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise TossConfigError(
            "TOSS_CLIENT_ID/TOSS_CLIENT_SECRET are not configured in Railway."
        )
    return client_id, client_secret


def access_token() -> str:
    global _token_value, _token_expires_at
    now = time.time()
    if _token_value and now < _token_expires_at - 60:
        return _token_value

    with _token_lock:
        now = time.time()
        if _token_value and now < _token_expires_at - 60:
            return _token_value

        client_id, client_secret = _client_credentials()
        body = parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )
        try:
            payload = browser_json(
                TOKEN_URL,
                method="POST",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "User-Agent": "AUTONOMOUS-INVESTOR-Toss/2.0",
                },
                body=body,
                timeout=30,
            )
        except Exception as exc:
            raise TossApiError(f"Toss OAuth failed via Chromium gateway: {type(exc).__name__}: {exc}") from exc

        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            raise TossApiError("Toss OAuth response did not contain access_token")
        expires_in = int(payload.get("expires_in") or 86400)
        _token_value = str(token)
        _token_expires_at = now + max(60, expires_in)
        return _token_value

def _get_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    token = access_token()
    query = parse.urlencode(
        {k: v for k, v in params.items() if v is not None},
        doseq=True,
    )
    url = BASE_URL + path + ("?" + query if query else "")
    try:
        payload = browser_json(
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "AUTONOMOUS-INVESTOR-Toss/2.0",
            },
            timeout=40,
        )
        if not isinstance(payload, dict):
            raise TossApiError(f"Toss API returned {type(payload).__name__}")
        return payload
    except Exception as exc:
        if isinstance(exc, TossApiError):
            raise
        raise TossApiError(f"Toss API failed via Chromium gateway: {type(exc).__name__}: {exc}") from exc

def get_candles(
    symbol: str,
    *,
    interval: str,
    count: int = 200,
    before: str | None = None,
    adjusted: bool = True,
) -> dict[str, Any]:
    if interval not in {"1m", "1d"}:
        raise ValueError("Toss candle interval must be 1m or 1d")
    count = min(max(int(count), 1), 200)
    payload = _get_json(
        "/api/v1/candles",
        {
            "symbol": symbol,
            "interval": interval,
            "count": count,
            "before": before,
            "adjusted": str(bool(adjusted)).lower(),
        },
    )
    result = payload.get("result") or {}
    candles = result.get("candles") or []
    normalized = [
        {
            "timestamp": row.get("timestamp"),
            "open": float(row["openPrice"]),
            "high": float(row["highPrice"]),
            "low": float(row["lowPrice"]),
            "close": float(row["closePrice"]),
            "volume": float(row["volume"]),
            "currency": row.get("currency"),
        }
        for row in candles
    ]
    return {
        "symbol": symbol,
        "interval": interval,
        "adjusted": adjusted,
        "count": len(normalized),
        "candles": normalized,
        "next_before": result.get("nextBefore"),
    }


def fetch_history(
    symbol: str,
    *,
    interval: str,
    max_bars: int,
    adjusted: bool = True,
) -> list[dict[str, Any]]:
    target = min(max(int(max_bars), 1), 20000)
    before: str | None = None
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    while len(rows) < target:
        page = get_candles(
            symbol,
            interval=interval,
            count=min(200, target - len(rows)),
            before=before,
            adjusted=adjusted,
        )
        page_rows = page["candles"]
        if not page_rows:
            break
        for row in page_rows:
            ts = str(row.get("timestamp") or "")
            if ts and ts not in seen:
                seen.add(ts)
                rows.append(row)
        next_before = page.get("next_before")
        if not next_before or next_before == before:
            break
        before = str(next_before)
        time.sleep(0.08)

    rows.sort(key=lambda x: str(x.get("timestamp") or ""))
    return rows[-target:]


def base_interval_for_horizon(horizon: str) -> str:
    value = horizon.strip().lower()
    if value in {"1d", "1w", "1mth", "1mo"}:
        return "1d"
    return "1m"
