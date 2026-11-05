"""Five-year TradingView public chart *observation* in a dedicated research branch.

Extends the existing official_chart_probe decoder. No private data API calls,
account impersonation, session tokens, WebSocket replay, data licensing claim,
scheduled downloads or side effects outside the current browser visit.

A user-selected chart interval is only a REQUEST. Coverage, interval and
first/last timestamps MUST be independently verified from received bars.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import calendar
import math
import re
from urllib.parse import quote, urlparse

try:
    from browser_worker.official_chart_probe import ALLOWED_MESSAGES, collect_bars, decode_chart_messages
except ModuleNotFoundError:
    from official_chart_probe import ALLOWED_MESSAGES, collect_bars, decode_chart_messages

# Timeframes match TradingView's chart interval query parameter; regular timebars.
TIMEFRAMES = {
    "1": ("1분", 60),
    "3": ("3분", 180),
    "5": ("5분", 300),
    "15": ("15분", 900),
    "30": ("30분", 1800),
    "60": ("1시간", 3600),
    "120": ("2시간", 7200),
    "240": ("4시간", 14400),
    "1D": ("일봉", 86400),
    "1W": ("주봉", 604800),
}
# Whole symbol is an exchange-prefixed TradingView ticker.
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9_]{1,30}:[A-Z0-9_.!/-]{1,65}$")
TV_HOST = "www.tradingview.com"
TV_WS_HOST = "data.tradingview.com"
MAX_BARS_OBSERVED = 60000    # bounded memory only; never promises all minutes
MAX_PANS = 32


def chart_url(symbol: str, interval: str) -> str:
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("INVALID_EXCHANGE_PREFIXED_SYMBOL")
    if interval not in TIMEFRAMES:
        raise ValueError("UNSUPPORTED_CHART_TIMEFRAME")
    return (f"https://{TV_HOST}/chart/?symbol={quote(symbol, safe='')}"
            f"&interval={quote(interval, safe='')}")


def five_year_start(asof: date) -> date:
    """Inclusive date exactly five calendar years before asof; handle Feb 29."""
    try:
        return asof.replace(year=asof.year - 5)
    except ValueError:
        return asof.replace(year=asof.year - 5, day=28)


def evaluate_history(bars: list[dict], *, interval: str,
                     asof: date, years: int = 5) -> dict:
    """Only observed, valid, chronological OHLCV; never fake missing candles.

    The coverage check does NOT confuse a chosen 5Y range on the UI with
    five years' worth of retrieved data. No claim of licensed access.
    """
    if interval not in TIMEFRAMES or years != 5:
        raise ValueError("INVALID_HISTORY_PARAMETERS")
    start=five_year_start(asof)
    start_ms=int(datetime.combine(start,datetime.min.time(),timezone.utc).timestamp()*1000)
    end_ms=int(datetime.combine(asof,datetime.min.time(),timezone.utc).timestamp()*1000)
    step_ms=TIMEFRAMES[interval][1]*1000
    unique={}
    for item in bars:
        if not isinstance(item, dict):
            continue
        t=item.get("time_ms")
        if type(t) is not int or not start_ms <= t < end_ms:
            continue
        vals=[item.get(k) for k in ("open","high","low","close")]
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in vals):
            continue
        o,h,l,c=vals
        if o<=0 or c<=0 or l<0 or l>min(o,c) or h<max(o,c):
            continue
        unique[t]=dict(item)
    ordered=[unique[t] for t in sorted(unique)]
    times=[x["time_ms"] for x in ordered]
    diffs=[b-a for a,b in zip(times,times[1:])]
    observed_exact=sum(1 for d in diffs if d==step_ms)
    # Trades close overnight and holidays, hence don't require every gap.
    exact_share=observed_exact/len(diffs) if diffs else 0
    # Weekly chart exchanges may show holiday variations. The 5Y window
    # requires enough bars AND date depth; flat trading days are not fabricated.
    verified_interval=exact_share>=.20 if len(diffs)>=10 else False
    tolerance_days=21 if interval in ("1D","1W") else 7
    first_covered=bool(times and times[0]<=start_ms+tolerance_days*86400000)
    last_covered=bool(times and times[-1]>=end_ms-14*86400000)
    complete=bool(verified_interval and first_covered and last_covered)
    return {
        "requested_start":start.isoformat(),
        "requested_end_exclusive":asof.isoformat(),
        "interval":interval,
        "timeframe_name":TIMEFRAMES[interval][0],
        "observed_count":len(ordered),
        "first_observed_utc":datetime.fromtimestamp(times[0]/1000,timezone.utc).isoformat() if times else None,
        "last_observed_utc":datetime.fromtimestamp(times[-1]/1000,timezone.utc).isoformat() if times else None,
        "matching_adjacent_interval_fraction":round(exact_share,4),
        "interval_verified":verified_interval,
        "reaches_requested_start":first_covered,
        "reaches_requested_end":last_covered,
        "five_year_window_covered":complete,
        "coverage_status":("COVERED_BY_OBSERVED_TIME_EXTENT" if complete
                           else "PARTIAL_HISTORY" if ordered else "NO_BARS_OBSERVED"),
        "market_sessions_filled":False,
        "note":"Time-extent coverage is not a guarantee that every exchange session exists; audit missing sessions separately.",
        "bars":ordered,
    }


async def observe_five_year_chart(context, *, symbol: str,
                                  interval: str = "1D",
                                  asof: date | None = None,
                                  max_pans: int = 10,
                                  load_wait_ms: int = 900):
    """Observe a normal chart visit and limited ordinary UI history panning.

    Panning via Playwright mouse is a best-effort user-equivalent action;
    it does NOT forge/replay WebSocket requests or exceed account plan limits.
    """
    target=chart_url(symbol,interval)
    if not 0<=max_pans<=MAX_PANS:
        raise ValueError("INVALID_HISTORY_PAN_BUDGET")
    if not 250<=load_wait_ms<=2500:
        raise ValueError("INVALID_CHART_WAIT")
    asof=asof or datetime.now(timezone.utc).date()
    page=await context.new_page()
    observed={}
    methods=Counter()
    ws_count=0
    js_errors=[]
    def ws_created(ws):
        nonlocal ws_count
        if (urlparse(ws.url).hostname or "").lower()!=TV_WS_HOST:
            return
        ws_count+=1
        def got_frame(frame):
            for message in decode_chart_messages(frame):
                method=message.get("m")
                methods[method]+=1
                if method in ALLOWED_MESSAGES and len(observed)<MAX_BARS_OBSERVED:
                    collect_bars(message.get("p"),observed)
        ws.on("framereceived",got_frame)
    page.on("websocket",ws_created)
    page.on("pageerror",lambda exc:js_errors.append(type(exc).__name__))
    http_status=None
    last_growth=0
    stagnation=0
    pan_attempts=0
    try:
        response=await page.goto(target,wait_until="domcontentloaded",timeout=45000)
        http_status=response.status if response else None
        await page.wait_for_timeout(9000)
        # History is requested by ordinary UI panning, not proprietary
        # API calls. Old bars might never load for access/plan reasons.
        for _ in range(max_pans):
            current=evaluate_history(list(observed.values()),interval=interval,asof=asof)
            if current["five_year_window_covered"]:
                break
            if len(observed)<=last_growth:
                stagnation+=1
            else:
                stagnation=0
            if stagnation>=3 or len(observed)>=MAX_BARS_OBSERVED:
                break
            last_growth=len(observed)
            size=page.viewport_size or {"width":1400,"height":900}
            w,h=size["width"],size["height"]
            y=int(h*.56)
            await page.mouse.move(int(w*.38),y)
            await page.mouse.down()
            await page.mouse.move(int(w*.84),y,steps=10)
            await page.mouse.up()
            pan_attempts+=1
            await page.wait_for_timeout(load_wait_ms)
        quality=evaluate_history(list(observed.values()),interval=interval,asof=asof)
        # 5Y interval and 5Y coverage are two different conditions.
        success=http_status==200 and quality["observed_count"]>=20 and quality["interval_verified"]
        return {
            "status":("OBSERVED_5Y_TIME_EXTENT" if quality["five_year_window_covered"] and success
                      else "OBSERVED_PARTIAL" if success else "CHART_VERIFICATION_INCOMPLETE"),
            "source":"TRADINGVIEW_PUBLIC_CHART_NORMAL_UI_PASSIVE_WEBSOCKET",
            "licensed_bulk_data_source":False,
            "symbol":symbol,"requested_period":"5Y",
            "interval":interval,"timeframe_name":TIMEFRAMES[interval][0],
            "url":target,"http_status":http_status,
            "ui_pan_attempts":pan_attempts,"ws_connections":ws_count,
            "message_counts":dict(methods),"page_errors":js_errors[:6],
            **quality,
        }
    finally:
        await page.close()
