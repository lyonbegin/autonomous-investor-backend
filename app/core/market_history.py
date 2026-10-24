from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib import parse

from app.core.browser_http import browser_json


USER_AGENT = "AUTONOMOUS-INVESTOR-QuantLab/1.0"


def _json(url: str, headers: dict[str, str] | None = None) -> Any:
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        merged.update(headers)
    return browser_json(
        url,
        method="GET",
        headers=merged,
        timeout=35,
    )

def _qualified(symbol: str) -> tuple[str, str]:
    value = str(symbol or "").strip()
    if ":" in value:
        exchange, ticker = value.split(":", 1)
        return exchange.upper(), ticker
    return "", value


def _yahoo_symbol(symbol: str, market: str = "") -> str:
    exchange, ticker = _qualified(symbol)
    ticker = ticker.replace(".P", "")
    upper = ticker.upper()

    # TradingView symbols do not always match provider symbols. Normalize the
    # common FX, index and continuous-futures forms used by collected scripts.
    index_aliases = {
        "SPX500USD": "^GSPC",
        "SPX": "^GSPC",
        "US500": "^GSPC",
        "NAS100USD": "^NDX",
        "NDX": "^NDX",
        "US30USD": "^DJI",
        "DJI": "^DJI",
        "UK100GBP": "^FTSE",
        "DE40EUR": "^GDAXI",
        "DE30EUR": "^GDAXI",
        "JP225USD": "^N225",
        "DXY": "DX-Y.NYB",
    }
    if upper in index_aliases:
        return index_aliases[upper]

    if exchange in {"FX", "FX_IDC", "OANDA", "FOREXCOM", "SAXO"}:
        compact = upper.replace("/", "").replace("-", "")
        if len(compact) == 6 and compact.isalpha():
            return compact + "=X"

    if exchange in {"CME_MINI", "CME", "CBOT", "COMEX", "NYMEX", "ICEUS"}:
        continuous = upper
        if continuous.endswith("1!"):
            continuous = continuous[:-2]
        futures_aliases = {
            "NQ": "NQ=F",
            "ES": "ES=F",
            "YM": "YM=F",
            "RTY": "RTY=F",
            "CL": "CL=F",
            "GC": "GC=F",
            "SI": "SI=F",
            "HG": "HG=F",
            "NG": "NG=F",
            "ZB": "ZB=F",
            "ZN": "ZN=F",
            "ZF": "ZF=F",
            "ZT": "ZT=F",
        }
        if continuous in futures_aliases:
            return futures_aliases[continuous]

    if exchange in {"NASDAQ", "NYSE", "AMEX", "BATS", "ARCA"}:
        return ticker
    if exchange in {"BINANCE", "COINBASE", "BITSTAMP", "BITFINEX"}:
        upper = ticker.upper().replace(".P", "")
        for quote in ("USDT", "USDC", "BUSD", "USD"):
            if upper.endswith(quote) and len(upper) > len(quote):
                return upper[:-len(quote)] + "-USD"
        return upper
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
        "15m": "15m", "30m": "30m", "1h": "1h", "2h": "2h",
        "4h": "4h", "6h": "6h", "8h": "8h", "12h": "12h", "1d": "1d",
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



def _clean_price(value: Any) -> float:
    text = str(value or "").replace("$", "").replace(",", "").strip()
    return float(text)


def fetch_nasdaq_daily_history(symbol: str, *, days: int = 365 * 5) -> dict[str, Any]:
    exchange, ticker = _qualified(symbol)
    if exchange and exchange not in {"NASDAQ", "NYSE", "AMEX", "BATS", "ARCA"}:
        raise RuntimeError(f"Nasdaq provider cannot serve exchange {exchange}")
    ticker = ticker.replace(".P", "")
    end = datetime.now(UTC).date()
    start = end - timedelta(days=max(30, min(int(days), 365 * 10)))
    url = (
        f"https://api.nasdaq.com/api/quote/{parse.quote(ticker)}/historical?"
        + parse.urlencode(
            {
                "assetclass": "stocks",
                "limit": 5000,
                "offset": 0,
                "fromdate": start.isoformat(),
                "todate": end.isoformat(),
            }
        )
    )
    raw = _json(
        url,
        {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/historical",
            "Origin": "https://www.nasdaq.com",
        },
    )
    status = raw.get("status") if isinstance(raw, dict) else None
    if not isinstance(raw, dict) or not isinstance(raw.get("data"), dict) or (status or {}).get("rCode") != 200:
        raise RuntimeError(f"Nasdaq historical response invalid: {str(raw)[:500]}")
    rows = ((((raw.get("data") or {}).get("tradesTable") or {}).get("rows")) or [])
    bars: list[dict[str, Any]] = []
    for row in rows:
        try:
            ts = int(datetime.strptime(str(row["date"]), "%m/%d/%Y").replace(tzinfo=UTC).timestamp() * 1000)
            bars.append(
                {
                    "timestamp": ts,
                    "open": _clean_price(row.get("open")),
                    "high": _clean_price(row.get("high")),
                    "low": _clean_price(row.get("low")),
                    "close": _clean_price(row.get("close")),
                    "volume": float(str(row.get("volume") or "0").replace(",", "")),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    bars.sort(key=lambda x: int(x["timestamp"]))
    return {
        "provider": "Nasdaq official historical API",
        "provider_symbol": ticker,
        "base_interval": "1d",
        "count": len(bars),
        "bars": bars,
    }


def _coinbase_product(symbol: str) -> str:
    _, ticker = _qualified(symbol)
    value = ticker.upper().replace(".P", "").replace("/", "").replace("-", "")
    for quote in ("USDT", "USDC", "BUSD", "USD"):
        if value.endswith(quote) and len(value) > len(quote):
            return value[:-len(quote)] + "-USD"
    return value + "-USD"


def _crypto_minutes(horizon: str) -> int:
    value = str(horizon or "").strip().lower()
    if value.endswith("d") and value[:-1].isdigit():
        return int(value[:-1]) * 1440
    return _target_minutes(value) or 60


def fetch_coinbase_history(symbol: str, *, horizon: str) -> dict[str, Any]:
    product = _coinbase_product(symbol)
    minutes = _crypto_minutes(horizon)
    allowed = [1, 5, 15, 60, 360, 1440]
    base_minutes = max([x for x in allowed if x <= minutes] or [1])
    granularity = base_minutes * 60
    url = (
        f"https://api.exchange.coinbase.com/products/{parse.quote(product, safe='-')}/candles?"
        + parse.urlencode({"granularity": granularity})
    )
    raw = _json(url, {"User-Agent": "AUTONOMOUS-INVESTOR-QuantLab/2.0"})
    if not isinstance(raw, list):
        raise RuntimeError(f"Coinbase returned unexpected payload: {str(raw)[:300]}")
    bars = []
    for row in raw:
        if not isinstance(row, list) or len(row) < 6:
            continue
        try:
            bars.append(
                {
                    "timestamp": int(row[0]) * 1000,
                    "low": float(row[1]),
                    "high": float(row[2]),
                    "open": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
            )
        except (TypeError, ValueError):
            continue
    bars.sort(key=lambda x: int(x["timestamp"]))
    return {
        "provider": "Coinbase Exchange public candles",
        "provider_symbol": product,
        "base_interval": f"{base_minutes}m" if base_minutes < 1440 else "1d",
        "count": len(bars),
        "bars": bars,
    }


def fetch_kraken_history(symbol: str, *, horizon: str) -> dict[str, Any]:
    product = _coinbase_product(symbol)
    base, quote = product.split("-", 1)
    pair = ("XBT" if base == "BTC" else base) + quote
    minutes = _crypto_minutes(horizon)
    allowed = [1, 5, 15, 30, 60, 240, 1440]
    interval = max([x for x in allowed if x <= minutes] or [1])
    url = "https://api.kraken.com/0/public/OHLC?" + parse.urlencode({"pair": pair, "interval": interval})
    raw = _json(url)
    if not isinstance(raw, dict) or raw.get("error"):
        raise RuntimeError(f"Kraken returned error: {str(raw)[:300]}")
    result = raw.get("result") or {}
    key = next((k for k in result.keys() if k != "last"), None)
    rows = result.get(key) if key else None
    if not isinstance(rows, list):
        raise RuntimeError(f"Kraken returned no OHLC rows for {pair}")
    bars = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 7:
            continue
        try:
            bars.append(
                {
                    "timestamp": int(row[0]) * 1000,
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[6]),
                }
            )
        except (TypeError, ValueError):
            continue
    bars.sort(key=lambda x: int(x["timestamp"]))
    return {
        "provider": "Kraken public OHLC",
        "provider_symbol": pair,
        "base_interval": f"{interval}m" if interval < 1440 else "1d",
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
    lower_horizon = str(horizon).lower()
    is_daily = lower_horizon.endswith("d") or lower_horizon in {"1w", "1mo", "1mth"}

    if exchange == "BINANCE":
        errors: list[str] = []
        for provider in (
            lambda: fetch_binance_history(symbol, horizon=horizon),
            lambda: fetch_coinbase_history(symbol, horizon=horizon),
            lambda: fetch_kraken_history(symbol, horizon=horizon),
        ):
            try:
                payload = provider()
                payload["fallback_used"] = bool(errors)
                if errors:
                    payload["fallback_reason"] = " | ".join(errors)
                break
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        else:
            raise RuntimeError("All crypto history providers failed: " + " | ".join(errors))
    elif exchange == "COINBASE":
        try:
            payload = fetch_coinbase_history(symbol, horizon=horizon)
            payload["fallback_used"] = False
        except Exception as exc:
            payload = fetch_kraken_history(symbol, horizon=horizon)
            payload["fallback_used"] = True
            payload["fallback_reason"] = f"Coinbase unavailable: {type(exc).__name__}: {exc}"
    elif exchange in {"BITSTAMP", "BITFINEX", "GATE", "BYBIT", "OKX"}:
        try:
            payload = fetch_coinbase_history(symbol, horizon=horizon)
            payload["fallback_used"] = True
            payload["fallback_reason"] = f"{exchange} historical API not connected; Coinbase market proxy used"
        except Exception as exc:
            payload = fetch_kraken_history(symbol, horizon=horizon)
            payload["fallback_used"] = True
            payload["fallback_reason"] = f"Coinbase proxy unavailable: {type(exc).__name__}: {exc}; Kraken proxy used"
    elif any(token in (country + " " + market).lower() for token in ("fx", "외환", "선물", "vn30", "hose", "hnx")):
        raise RuntimeError("Historical provider for this FX/futures market is not connected yet")
    else:
        try:
            payload = fetch_yahoo_history(symbol, horizon=horizon, market=market)
            payload["fallback_used"] = False
        except Exception as yahoo_exc:
            if is_daily and (not exchange or exchange in {"NASDAQ", "NYSE", "AMEX", "BATS", "ARCA"}):
                payload = fetch_nasdaq_daily_history(symbol)
                payload["fallback_used"] = True
                payload["fallback_reason"] = f"Yahoo unavailable: {type(yahoo_exc).__name__}: {yahoo_exc}"
            else:
                raise

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
