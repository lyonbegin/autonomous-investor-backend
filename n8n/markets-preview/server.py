"""Read-only market OHLCV API for the isolated market preview.

No trading, credentials, TradingView scraping, or invented prices.
Yahoo's public chart endpoint is a *best-effort* source, not a licensed feed.
Responses always carry provenance and availability state; failures are explicit.
"""
from __future__ import annotations
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Explicit allowlist: no user-controlled URLs, SSRF or arbitrary proxying.
SYMBOLS = {
    "KRX:005930": "005930.KS", "KRX:000660": "000660.KS",
    "KRX:005380": "005380.KS", "KRX:051910": "051910.KS",
    "KRX:207940": "207940.KS", "KRX:017670": "017670.KS",
    "SP:SPX": "^GSPC", "NASDAQ:NDX": "^NDX", "TVC:NI225": "^N225",
    "KRX:KOSPI": "^KS11", "KRX:KOSPI50": "^KS50", "KRX:KOSPI200": "^KS200",
    "NASDAQ:MSFT": "MSFT", "TADAWUL:2222": "2222.SR",
    "NYSE:TSM": "TSM", "EURONEXT:MC": "MC.PA",
    "HKEX:700": "0700.HK",
    "BITSTAMP:BTCUSD": "BTC-USD", "BITSTAMP:ETHUSD": "ETH-USD",
    "COINBASE:SOLUSD": "SOL-USD", "BITSTAMP:XRPUSD": "XRP-USD",
    "BINANCE:BNBUSDT": "BNB-USD", "COINBASE:DOGEUSD": "DOGE-USD",
    "CME_MINI:ES1!": "ES=F", "NYMEX:CL1!": "CL=F",
    "COMEX:GC1!": "GC=F", "NYMEX:NG1!": "NG=F",
    "CBOT:ZC1!": "ZC=F", "COMEX:HG1!": "HG=F",
    "FX:EURUSD": "EURUSD=X", "FX:USDJPY": "JPY=X",
    "FX:GBPUSD": "GBPUSD=X", "FX_IDC:USDKRW": "KRW=X",
    "FX_IDC:USDCNY": "CNY=X", "TVC:DXY": "DX-Y.NYB",
    "AMEX:SPY": "SPY", "NASDAQ:QQQ": "QQQ", "AMEX:IVV": "IVV",
    "AMEX:VOO": "VOO", "AMEX:EEM": "EEM", "AMEX:ARKK": "ARKK",
}
# These presets are explicit user-facing windows; daily prices are sampled
# only for drawing, never silently described as every instrument's full history.
PERIODS = {
    "1D": ("5d", "5m"), "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"), "1Y": ("1y", "1d"),
    "5Y": ("5y", "1d"),
}
CACHE = {}
LOCK = threading.Lock()
CACHE_SECONDS = 120

def get_chart(tv_symbol: str, period: str):
    if tv_symbol not in SYMBOLS:
        return 422, {"status": "UNSUPPORTED_SYMBOL", "symbol": tv_symbol}
    if period not in PERIODS:
        return 400, {"status": "INVALID_PERIOD", "period": period}
    key = (tv_symbol, period)
    now = time.time()
    with LOCK:
        item = CACHE.get(key)
        if item and now - item[0] < CACHE_SECONDS:
            return 200, dict(item[1], cache="HIT")
    y_symbol = SYMBOLS[tv_symbol]
    period1, interval = PERIODS[period]
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" +
        urllib.parse.quote(y_symbol, safe="") + "?" +
        urllib.parse.urlencode({"range": period1, "interval": interval,
                                "events": "history", "includeAdjustedClose": "true"}))
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; InvestmentMarketsReadOnly/1.0)",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read(5_000_000)
        data = json.loads(raw)
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            raise ValueError("provider returned no chart result")
        ts = result.get("timestamp") or []
        quoted = (result.get("indicators", {}).get("quote") or [None])[0] or {}
        bars = []
        opens, highs, lows, closes, vols = (
            quoted.get("open") or [], quoted.get("high") or [],
            quoted.get("low") or [], quoted.get("close") or [],
            quoted.get("volume") or [])
        for i,t in enumerate(ts):
            if any(i >= len(arr) for arr in (opens, highs, lows, closes)):
                break
            values = (opens[i], highs[i], lows[i], closes[i])
            if any(v is None for v in values):
                continue
            row = {"t": int(t), "o": round(float(values[0]), 6),
                   "h": round(float(values[1]), 6), "l": round(float(values[2]), 6),
                   "c": round(float(values[3]), 6),
                   "v": int(vols[i]) if i < len(vols) and vols[i] is not None else None}
            bars.append(row)
        if not bars:
            raise ValueError("provider returned no usable OHLC bars")
        meta = result.get("meta") or {}
        payload = {
            "status": "OK", "source": "Yahoo Finance chart API",
            "source_symbol": y_symbol, "symbol": tv_symbol, "period": period,
            "interval": interval, "currency": meta.get("currency"),
            "exchange_timezone": meta.get("exchangeTimezoneName"),
            "market_state": meta.get("marketState", "UNVERIFIED"),
            "asof_utc": bars[-1]["t"],
            "bar_count": len(bars),
            "bars": bars[-1800:],
            "latest_close": bars[-1]["c"],
            "previous_close": bars[-2]["c"] if len(bars)>1 else None,
            "quote_realtime_verified": False, "cache": "MISS",
            "notice": "Best-effort external data; not official TradingView or verified real-time feed.",
        }
        with LOCK:
            CACHE[key] = (now, payload)
            if len(CACHE)>300:
                oldest=min(CACHE, key=lambda k:CACHE[k][0])
                del CACHE[oldest]
        return 200, payload
    except urllib.error.HTTPError as exc:
        return 503, {"status": "DATA_UNAVAILABLE", "source": "Yahoo Finance chart API",
                     "symbol": tv_symbol, "reason": "provider_http_" + str(exc.code)}
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, OSError) as exc:
        return 503, {"status": "DATA_UNAVAILABLE", "source": "Yahoo Finance chart API",
                     "symbol": tv_symbol, "reason": type(exc).__name__}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _json(self, code, data):
        raw = json.dumps(data, ensure_ascii=False, separators=(",",":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path == "/health":
            return self._json(200, {"status": "ok", "mode": "read_only", "market_data": "best_effort"})
        if u.path == "/api/markets/ohlcv":
            q = urllib.parse.parse_qs(u.query)
            symbol = (q.get("symbol") or [""])[0][:80]
            period = (q.get("period") or ["1M"])[0]
            code, result = get_chart(symbol, period)
            return self._json(code, result)
        if u.path == "/api/markets/data-status":
            return self._json(200, {"status": "provider_not_guaranteed",
                 "source": "Yahoo Finance chart API",
                 "supported_instruments": len(SYMBOLS),
                 "supported_periods": list(PERIODS),
                 "external_chart_fallback": "TradingView official embeddable widget"})
        if u.path == "/":
            self.path = "/index.html"
        return super().do_GET()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print("markets preview listening on",port,flush=True)
    if os.getenv("MARKETS_PROBE_ON_START") == "1":
        def probe():
            code, result = get_chart("NASDAQ:MSFT","1M")
            print("PROVIDER_STARTUP_PROBE", code, result.get("status"), result.get("reason",""), "bars=", result.get("bar_count",0), flush=True)
        threading.Thread(target=probe, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0",port), Handler).serve_forever()
