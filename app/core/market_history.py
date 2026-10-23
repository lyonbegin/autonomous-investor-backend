from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any
from urllib import parse, request


USER_AGENT = "AUTONOMOUS-INVESTOR-QuantLab/1.0"


def _json(url: str) -> dict[str, Any]:
    req = request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def _qualified(symbol: str) -> tuple[str, str]:
    value = str(symbol or "").strip()
    if ":" in value:
        exchange, ticker = value.split(":", 1)
        return exchange.upper(), ticker
    return "", value


def _yahoo_symbol(symbol: str, market: str = "") -> str:
    exchange, ticker = _qualified(symbol)
    ticker = ticker.replace(".P", "")
    if exchange in {"NASDAQ", "NYSE", "AMEX", "BATS", "ARCA"}:
        return ticker
    if exchange in {"KRX", "KOSPI"}:
        return ticker + ".KS"
    if exchange in {"KOSDAQ"}:
        return ticker + ".KQ"
    if not exchange and ticker.isdigit() and len(ticker) == 6:
        return ticker + (".KQ" if "kosdaq" in market.lower() else ".KS")
    return ticker


def _target_minutes(horizon: str) -> int | None:
    value = str(horizon or "").strip().lower()
    if value.endswith("m") and value[:-1].isdigit():
        return int(value[:-1])
    if value.endswith("h") and value[:-1].isdigit():
        return int(value[:-1]) * 60
    return None


def _yahoo_base_interval(horizon: str) -> tuple[str, str]:
    minutes = _target_minutes(horizon)
    if minutes is None:
        return "1d", "5y"
    if minutes <= 2:
        return "1m", "7d"
    if minutes <= 10:
        return "5m", "60d"
    if minutes <= 30:
        return "15m", "60d"
    if minutes <= 60:
        return "60m", "730d"
    return "60m", "730d"


def _bar(ts: int, o: Any, h: Any, l: Any, c: Any, v: Any) -> dict[str, float | int]:
    return {
        "timestamp": int(ts) * 1000,
        "open": float(o),
        "high": float(h),
        "low": float(l),
        "close": float(c),
        "volume": float(v or 0.0),
    }


def fetch_yahoo_history(
    symbol: str,
    *,
    horizon: str,
    market: str = "",
) -> dict[str, Any]:
    ticker = _yahoo_symbol(symbol, market)
    interval, range_value = _yahoo_base_interval(horizon)
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + parse.quote(ticker, safe="=^-")
        + "?"
        + parse.urlencode(
            {
                "interval": interval,
                "range": range_value,
                "includePrePost": "false",
                "events": "div,splits",
            }
        )
    )
    raw = _json(url)
    chart = raw.get("chart") or {}
    if chart.get("error"):
        raise RuntimeError(f"Yahoo chart error: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"Yahoo returned no history for {ticker}")
    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    bars: list[dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        try:
            values = (opens[i], highs[i], lows[i], closes[i])
        except IndexError:
            continue
        if any(x is None for x in values):
            continue
        try:
            b = _bar(ts, opens[i], highs[i], lows[i], closes[i], volumes[i] if i < len(volumes) else 0)
        except (TypeError, ValueError):
            continue
        if all(math.isfinite(float(b[k])) for k in ("open", "high", "low", "close")):
            bars.append(b)
    return {
        "provider": "Yahoo Finance chart API",
        "provider_symbol": ticker,
        "base_interval": interval,
        "count": len(bars),
        "bars": bars,
    }


def fetch_binance_history(symbol: str, *, horizon: str, limit: int = 1000) -> dict[str, Any]:
    exchange, ticker = _qualified(symbol)
    if exchange and exchange != "BINANCE":
        raise RuntimeError(f"Binance provider cannot serve exchange {exchange}")
    ticker = ticker.replace(".P", "").replace("/", "")
    interval_map = {
        "1m": "1m", "3m": "3m", "5m": "5m", "10m": "5m",
        "15m": "15m", "30m": "30m", "1h": "1h", "2h": "1h",
        "4h": "4h", "1d": "1d",
    }
    interval = interval_map.get(str(horizon).lower(), "1h")
    url = "https://api.binance.com/api/v3/klines?" + parse.urlencode(
        {"symbol": ticker, "interval": interval, "limit": min(max(limit, 1), 1000)}
    )
    raw = _json(url)
    if not isinstance(raw, list):
        raise RuntimeError(f"Binance returned unexpected payload: {str(raw)[:200]}")
    bars = [
        {
            "timestamp": int(x[0]),
            "open": float(x[1]),
            "high": float(x[2]),
            "low": float(x[3]),
            "close": float(x[4]),
            "volume": float(x[5]),
        }
        for x in raw
        if isinstance(x, list) and len(x) >= 6
    ]
    return {
        "provider": "Binance public klines",
        "provider_symbol": ticker,
        "base_interval": interval,
        "count": len(bars),
        "bars": bars,
    }


def _aggregate_minutes(bars: list[dict[str, Any]], minutes: int) -> list[dict[str, Any]]:
    if minutes <= 1:
        return bars
    width = minutes * 60_000
    buckets: dict[int, list[dict[str, Any]]] = {}
    for bar in bars:
        key = int(bar["timestamp"]) // width * width
        buckets.setdefault(key, []).append(bar)
    out: list[dict[str, Any]] = []
    for key in sorted(buckets):
        group = buckets[key]
        if not group:
            continue
        out.append(
            {
                "timestamp": key,
                "open": float(group[0]["open"]),
                "high": max(float(x["high"]) for x in group),
                "low": min(float(x["low"]) for x in group),
                "close": float(group[-1]["close"]),
                "volume": sum(float(x.get("volume") or 0.0) for x in group),
            }
        )
    return out


def fetch_history_for_agent(
    symbol: str,
    *,
    horizon: str,
    market: str = "",
    country: str = "",
) -> dict[str, Any]:
    exchange, _ = _qualified(symbol)
    if exchange == "BINANCE":
        payload = fetch_binance_history(symbol, horizon=horizon)
    elif exchange in {"GATE", "BYBIT", "OKX"}:
        raise RuntimeError(f"Historical provider for {exchange} is not connected yet")
    elif any(token in (country + " " + market).lower() for token in ("fx", "외환", "선물", "vn30", "hose", "hnx")):
        raise RuntimeError("Historical provider for this FX/futures market is not connected yet")
    else:
        payload = fetch_yahoo_history(symbol, horizon=horizon, market=market)

    target_minutes = _target_minutes(horizon)
    base = str(payload.get("base_interval") or "")
    if target_minutes and base.endswith("m") and base[:-1].isdigit():
        base_minutes = int(base[:-1])
        if target_minutes > base_minutes and target_minutes % base_minutes == 0:
            payload["bars"] = _aggregate_minutes(payload["bars"], target_minutes)
            payload["count"] = len(payload["bars"])
            payload["effective_interval"] = f"{target_minutes}m"
        else:
            payload["effective_interval"] = base
    else:
        payload["effective_interval"] = "1d" if str(horizon).lower().endswith("d") else base
    payload["fetched_at"] = datetime.now(UTC).isoformat()
    return payload
