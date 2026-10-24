from __future__ import annotations

import math
import os
import re
from typing import Any
from urllib.parse import quote

from app.core.browser_http import browser_json
from app.core.market_history import fetch_history_for_agent
from app.core.strategy_spec import StrategySpecError, compile_pine_to_spec, run_strategy_spec


TRADINGVIEW_API = os.getenv(
    "TRADINGVIEW_API",
    "https://autonomous-investor-tradingview-production.up.railway.app",
).rstrip("/")


def _source(script_id: str) -> dict[str, Any]:
    encoded = quote(str(script_id), safe="")
    data = browser_json(
        f"{TRADINGVIEW_API}/api/v1/tradingview/scripts/{encoded}/source",
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "AUTONOMOUS-INVESTOR-PineVisual/1.0"},
        timeout=45,
    )
    if not isinstance(data, dict) or not data.get("source"):
        raise RuntimeError(f"Pine source unavailable for {script_id}")
    return data


def _input_number(source: str, name: str, default: float) -> float:
    pattern = rf"\b{re.escape(name)}\s*=\s*input\.(?:int|float)\s*\(([^\n]+)"
    m = re.search(pattern, source)
    if not m:
        return default
    body = m.group(1)
    named = re.search(r"defval\s*=\s*([-+]?\d+(?:\.\d+)?)", body)
    plain = re.search(r"^\s*([-+]?\d+(?:\.\d+)?)", body)
    hit = named or plain
    return float(hit.group(1)) if hit else default


def _input_bool(source: str, name: str, default: bool) -> bool:
    m = re.search(rf"\b{re.escape(name)}\s*=\s*input\.bool\s*\(([^\n]+)", source)
    if not m:
        return default
    body = m.group(1)
    named = re.search(r"defval\s*=\s*(true|false)", body, re.I)
    plain = re.search(r"^\s*(true|false)", body, re.I)
    hit = named or plain
    return (hit.group(1).lower() == "true") if hit else default


def _input_string(source: str, name: str, default: str) -> str:
    m = re.search(rf"\b{re.escape(name)}\s*=\s*input\.string\s*\(([^\n]+)", source)
    if not m:
        return default
    body = m.group(1)
    named = re.search(r'defval\s*=\s*"([^"]+)"', body)
    plain = re.search(r'^\s*"([^"]+)"', body)
    hit = named or plain
    return hit.group(1) if hit else default


def _rma(values: list[float], length: int) -> list[float]:
    out = [float("nan")] * len(values)
    seed: list[float] = []
    prev = float("nan")
    alpha = 1.0 / max(1, length)
    for i, value in enumerate(values):
        if math.isnan(value):
            continue
        seed.append(value)
        if len(seed) < length:
            continue
        if math.isnan(prev):
            prev = sum(seed[-length:]) / length
        else:
            prev = alpha * value + (1.0 - alpha) * prev
        out[i] = prev
    return out


def _atr(bars: list[dict[str, Any]], length: int) -> list[float]:
    tr: list[float] = []
    for i, b in enumerate(bars):
        h, l = float(b["high"]), float(b["low"])
        if i == 0:
            tr.append(h - l)
        else:
            pc = float(bars[i - 1]["close"])
            tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    return _rma(tr, length)


def _rolling_sum(values: list[float], length: int) -> list[float]:
    out = [0.0] * len(values)
    acc = 0.0
    for i, value in enumerate(values):
        acc += value
        if i >= length:
            acc -= values[i - length]
        out[i] = acc if i >= length - 1 else float("nan")
    return out


def _rolling_extreme(values: list[float], length: int, fn) -> list[float]:
    out = [float("nan")] * len(values)
    for i in range(length - 1, len(values)):
        out[i] = fn(values[i - length + 1 : i + 1])
    return out


def _is_pivot_high(highs: list[float], center: int, left: int, right: int) -> bool:
    if center - left < 0 or center + right >= len(highs):
        return False
    value = highs[center]
    window = highs[center - left : center + right + 1]
    return value == max(window) and window.count(value) == 1


def _is_pivot_low(lows: list[float], center: int, left: int, right: int) -> bool:
    if center - left < 0 or center + right >= len(lows):
        return False
    value = lows[center]
    window = lows[center - left : center + right + 1]
    return value == min(window) and window.count(value) == 1


def _dynamic_liquidity_clouds(source: str, bars: list[dict[str, Any]]) -> dict[str, Any]:
    pivot_len = max(2, int(_input_number(source, "pivotLength", 5)))
    cloud_width = max(10, int(_input_number(source, "cloudWidth", 100)))
    atr_len = max(1, int(_input_number(source, "atrLen", 14)))
    atr_mult = max(0.01, float(_input_number(source, "atrMult", 0.1)))
    cloud_count = max(1, min(10, int(_input_number(source, "cloudCount", 6))))
    sweep_detection = _input_bool(source, "sweepDetection", True)
    sweep_src = _input_string(source, "sweepSrc", "Close")

    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    closes = [float(b["close"]) for b in bars]
    volumes = [float(b.get("volume") or 0.0) for b in bars]
    atrs = _atr(bars, atr_len)

    span = 2 * pivot_len + 1
    vol_sum = _rolling_sum(volumes, span)
    vol_hi = _rolling_extreme(volumes, 100, max)
    vol_lo = _rolling_extreme(volumes, 100, min)

    nodes: list[dict[str, Any]] = []

    for confirm in range(2 * pivot_len, len(bars)):
        center = confirm - pivot_len
        atr_val = atrs[confirm]
        pvol = vol_sum[confirm]
        if math.isnan(atr_val) or math.isnan(pvol):
            continue
        hi = vol_hi[confirm]
        lo = vol_lo[confirm]
        if math.isnan(hi) or math.isnan(lo):
            ratio = 0.5
        else:
            vhi = hi * span
            vlo = lo * span
            rng = vhi - vlo
            ratio = (pvol - vlo) / rng if rng > 0 else 0.5
            ratio = max(0.0, min(1.0, ratio))
        max_hw = cloud_width * ratio
        step = atr_val * atr_mult
        right_index = center + int(max_hw)

        specs: list[tuple[str, float]] = []
        if _is_pivot_high(highs, center, pivot_len, pivot_len):
            specs.append(("BSL", highs[center]))
        if _is_pivot_low(lows, center, pivot_len, pivot_len):
            specs.append(("SSL", lows[center]))

        for side, price in specs:
            layers = []
            for k in range(1, cloud_count + 1):
                half_w = max_hw * k / cloud_count
                left_idx = max(0, center - int(half_w))
                layer_right = min(len(bars) - 1, center + int(half_w))
                if side == "BSL":
                    bottom = price + step * k
                    top = price + step * (k + cloud_count)
                else:
                    top = price - step * k
                    bottom = price - step * (k + cloud_count)
                layers.append(
                    {
                        "from_time": int(bars[left_idx]["timestamp"]),
                        "to_time": int(bars[layer_right]["timestamp"]),
                        "top": float(top),
                        "bottom": float(bottom),
                    }
                )

            outer_top = price + step * (2 * cloud_count) if side == "BSL" else price
            outer_bottom = price if side == "BSL" else price - step * (2 * cloud_count)
            swept = False
            swept_index = None
            if sweep_detection:
                end = min(len(bars) - 1, max(confirm, right_index))
                for j in range(confirm, end + 1):
                    hi_src = closes[j] if sweep_src == "Close" else highs[j]
                    lo_src = closes[j] if sweep_src == "Close" else lows[j]
                    if side == "BSL" and hi_src > outer_top:
                        swept, swept_index = True, j
                        break
                    if side == "SSL" and lo_src < outer_bottom:
                        swept, swept_index = True, j
                        break

            nodes.append(
                {
                    "side": side,
                    "pivot_time": int(bars[center]["timestamp"]),
                    "pivot_price": float(price),
                    "right_time": int(bars[min(len(bars) - 1, max(center, right_index))]["timestamp"]),
                    "outer_top": float(outer_top),
                    "outer_bottom": float(outer_bottom),
                    "swept": swept,
                    "swept_time": int(bars[swept_index]["timestamp"]) if swept_index is not None else None,
                    "volume_ratio": round(ratio, 6),
                    "layers": layers,
                }
            )

    bsl = [x for x in nodes if x["side"] == "BSL"][-60:]
    ssl = [x for x in nodes if x["side"] == "SSL"][-60:]
    final_nodes = sorted(bsl + ssl, key=lambda x: int(x["pivot_time"]))

    return {
        "runtime": "pine-visual-v1",
        "adapter": "dynamic-liquidity-clouds",
        "inputs": {
            "pivotLength": pivot_len,
            "cloudWidth": cloud_width,
            "atrLen": atr_len,
            "atrMult": atr_mult,
            "cloudCount": cloud_count,
            "sweepDetection": sweep_detection,
            "sweepSrc": sweep_src,
        },
        "nodes": final_nodes,
        "node_count": len(final_nodes),
    }


def _strategy_visual(script_id: str, source: str, bars: list[dict[str, Any]]) -> dict[str, Any]:
    spec = compile_pine_to_spec(script_id, source)
    result = run_strategy_spec(spec, bars)
    markers = []
    for trade in result.get("trades") or []:
        markers.append(
            {
                "time": int(trade["entry_time"]),
                "position": "belowBar" if trade["side"] == "long" else "aboveBar",
                "shape": "arrowUp" if trade["side"] == "long" else "arrowDown",
                "text": "LONG" if trade["side"] == "long" else "SHORT",
            }
        )
        markers.append(
            {
                "time": int(trade["exit_time"]),
                "position": "aboveBar" if trade["side"] == "long" else "belowBar",
                "shape": "circle",
                "text": "EXIT",
            }
        )
    return {
        "runtime": "pine-strategy-spec-v1",
        "adapter": "strategy-spec",
        "spec": spec,
        "metrics": result.get("metrics"),
        "trades": result.get("trades") or [],
        "markers": markers,
        "equity_curve": result.get("equity_curve") or [],
    }


def visualize_pine_script(
    script_id: str,
    *,
    symbol: str,
    horizon: str,
    market: str = "",
    country: str = "",
) -> dict[str, Any]:
    pine = _source(script_id)
    source = str(pine.get("source") or "")
    history = fetch_history_for_agent(
        symbol,
        horizon=horizon,
        market=market,
        country=country,
    )
    bars = list(history.get("bars") or [])
    if not bars:
        raise RuntimeError("market data returned no OHLCV bars")

    kind = str(pine.get("kind") or "").lower()
    name = str(pine.get("script_name") or script_id)

    if "Dynamic Liquidity Clouds" in name or (
        "type liqNode" in source and "bslNodes" in source and "sslNodes" in source
    ):
        visual = _dynamic_liquidity_clouds(source, bars)
    elif kind == "strategy" or "strategy(" in source:
        try:
            visual = _strategy_visual(script_id, source, bars)
        except StrategySpecError as exc:
            visual = {
                "runtime": "pine-strategy-spec-v1",
                "adapter": "unsupported",
                "error": str(exc),
                "markers": [],
            }
    else:
        visual = {
            "runtime": "pine-visual-v1",
            "adapter": "unsupported",
            "error": "This Pine indicator has not yet been translated to a visual adapter.",
            "markers": [],
        }

    return {
        "script_id": script_id,
        "script_name": name,
        "kind": pine.get("kind"),
        "pine_version": pine.get("pine_version"),
        "source_hash": pine.get("source_hash"),
        "symbol": symbol,
        "horizon": horizon,
        "market_data": {
            "provider": history.get("provider"),
            "provider_symbol": history.get("provider_symbol"),
            "base_interval": history.get("base_interval"),
            "effective_interval": history.get("effective_interval"),
            "fallback_used": history.get("fallback_used", False),
            "fallback_reason": history.get("fallback_reason"),
            "fetched_at": history.get("fetched_at"),
            "count": len(bars),
        },
        "bars": bars,
        "visual": visual,
    }
