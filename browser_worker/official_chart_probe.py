"""Passive TradingView public-chart transport probe for the WF-02 test UI.

FIXED NASDAQ:AAPL 1D, 300 bars maximum. This is browser-observed chart data,
not a documented licensed TradingView API and not Strategy Tester output.
No sessions, raw frames, tokens, account state or market-data reselling API.
"""
from __future__ import annotations
from collections import Counter
import json
import math
from datetime import datetime, timezone

TARGET = "https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL"
ALLOWED_MESSAGES = {"series_loading", "timescale_update", "du"}


def decode_chart_messages(frame: str) -> list[dict]:
    if not isinstance(frame, str) or len(frame) > 2_000_000:
        return []
    results: list[dict] = []
    position = 0
    while position < len(frame) and len(results) < 200:
        head = frame.find("~m~", position)
        if head < 0:
            break
        divider = frame.find("~m~", head + 3)
        if divider < 0:
            break
        length = frame[head + 3:divider]
        if not length.isdigit() or len(length) > 8:
            break
        start = divider + 3
        end = start + int(length)
        if end > len(frame):
            break
        position = end
        if frame[start:start + 1] != "{":
            continue
        try:
            item = json.loads(frame[start:end])
            if isinstance(item, dict) and isinstance(item.get("m"), str):
                results.append(item)
        except ValueError:
            continue
    if results:
        return results
    try:
        data = json.loads(frame)
        return [data] if isinstance(data, dict) and isinstance(data.get("m"), str) else []
    except ValueError:
        return []


def _valid_bar(values):
    if not isinstance(values, list) or not 5 <= len(values) <= 8:
        return False
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values[:5]):
        return False
    t, o, h, l, c = values[:5]
    return (100_000_000 < t < 5_000_000_000 and o > 0 and c > 0
            and l >= 0 and l <= min(o, c) and h >= max(o, c))


def collect_bars(payload, output: dict):
    # Treat structures in an observed official chart message as data; never
    # execute JS or interact with private websocket endpoints.
    stack = [(payload, 0)]
    while stack:
        value, depth = stack.pop()
        if depth > 16:
            continue
        if isinstance(value, dict):
            v = value.get("v")
            if _valid_bar(v):
                t, o, h, l, c = v[:5]
                volume = v[5] if len(v) > 5 and isinstance(v[5], (int, float)) and math.isfinite(v[5]) else None
                output[int(t * 1000)] = {
                    "time_ms": int(t * 1000), "open": float(o), "high": float(h),
                    "low": float(l), "close": float(c),
                    "volume": float(volume) if volume is not None else None
                }
            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    stack.append((nested, depth + 1))
        elif isinstance(value, list):
            for nested in value:
                if isinstance(nested, (dict, list)):
                    stack.append((nested, depth + 1))


async def observe_public_chart(context) -> dict:
    page = await context.new_page()
    bars: dict[int, dict] = {}
    methods = Counter()
    websocket_hosts = Counter()
    errors = []
    http_status = None

    def on_ws(ws):
        from urllib.parse import urlparse
        host = urlparse(ws.url).hostname or ""
        if host != "data.tradingview.com":
            return
        websocket_hosts[host] += 1

        def on_frame(frame):
            for message in decode_chart_messages(frame):
                method = message["m"]
                methods[method] += 1
                if method in ALLOWED_MESSAGES:
                    collect_bars(message.get("p"), bars)
        ws.on("framereceived", on_frame)

    page.on("websocket", on_ws)
    page.on("pageerror", lambda err: errors.append(type(err).__name__))
    try:
        response = await page.goto(TARGET, wait_until="domcontentloaded", timeout=45_000)
        http_status = response.status if response else None
        await page.wait_for_timeout(13_000)
        chosen = sorted(bars.values(), key=lambda bar: bar["time_ms"])[-300:]
        if http_status != 200 or len(chosen) < 20:
            return {"status": "OFFICIAL_CHART_BARS_NOT_RECEIVED", "http_status": http_status,
                    "bar_count": len(chosen), "method_counts": dict(methods),
                    "tv_strategy_trades_available": False}
        return {
            "status": "OFFICIAL_CHART_OHLCV_CAPTURED",
            "provenance": "TRADINGVIEW_PUBLIC_CHART_PASSIVE_WEBSOCKET",
            "licensed_data_api": False,
            "symbol": "NASDAQ:AAPL", "timeframe": "1D",
            "bar_count": len(chosen),
            "bars": chosen,
            "first_time_ms": chosen[0]["time_ms"],
            "last_time_ms": chosen[-1]["time_ms"],
            "http_status": http_status,
            "websocket_connections": sum(websocket_hosts.values()),
            "message_counts": {key: methods[key] for key in
                               ("series_loading", "timescale_update", "du", "study_loading", "study_completed")},
            "tv_strategy_trades_available": False,
            "tv_strategy_parity_verified": False,
            "captured_at": datetime.now(timezone.utc).isoformat()
        }
    finally:
        await page.close()
