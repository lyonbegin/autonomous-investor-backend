"""Study-only extension of the project's existing official TradingView chart
WebSocket observation. 5-year DAILY (1D) only, no 5-year minute history.
Copies no TradingView JavaScript, tokens or private access credentials.
Do not interpret user-selected range as confirmation all 5 years arrived.
"""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import calendar
import math
import re
from urllib.parse import quote, urlparse

from .chart_protocol import ALLOWED_MESSAGES, collect_bars, decode_chart_messages

# Fixed 5-year DAILY requirement. Do not expose minute history here.
TIMEFRAMES = {
    "1D": ("일봉", 86400),  # 5-year request ALWAYS DAILY, never minute candles
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
    if interval != "1D":
        raise ValueError("UNSUPPORTED_CHART_TIMEFRAME")
    return (f"https://{TV_HOST}/chart/?symbol={quote(symbol, safe='')}"
            f"&interval={quote(interval, safe='')}&range=60M")


def five_year_start(asof: date) -> date:
    """Inclusive date exactly five calendar years before asof; handle Feb 29."""
    try:
        return asof.replace(year=asof.year - 5)
    except ValueError:
        return asof.replace(year=asof.year - 5, day=28)


def evaluate_history(bars: list[dict], *, interval: str,
                     asof: date, years: int = 5, symbol: str = "") -> dict:
    """Only observed, valid, chronological OHLCV; never fake missing candles.

    The coverage check does NOT confuse a chosen 5Y range on the UI with
    five years' worth of retrieved data. No claim of licensed access.
    """
    if interval != "1D" or years != 5:
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
    tolerance_days=21  # exchange closures and holidays; date extent is not completeness
    first_covered=bool(times and times[0]<=start_ms+tolerance_days*86400000)
    last_covered=bool(times and times[-1]>=end_ms-14*86400000)
    # Date extent is insufficient: 20 old candles + 300 recent candles must
    # not pass as "five years complete". Require 90% of expected trading dates.
    # This is a conservative provisional weekday/24x7 calendar, NOT a full
    # official exchange holiday-session audit.
    always_open=symbol.split(":")[0] in {
        "BINANCE","BYBIT","BITSTAMP","COINBASE","KRAKEN","OKX","BITFINEX"
    }
    expected_days=(asof-start).days
    if not always_open:
        expected_days=sum((start+timedelta(days=i)).weekday()<5
                          for i in range(expected_days))
    observed_dates={datetime.fromtimestamp(t/1000,timezone.utc).date()
                    for t in times}
    if not always_open:
        counted=sum(d.weekday()<5 for d in observed_dates)
    else:
        counted=len(observed_dates)
    date_density=counted/expected_days if expected_days else 0.0
    dense_enough=date_density>=.90
    complete=bool(verified_interval and first_covered and last_covered
                  and dense_enough)
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
        "expected_calendar_dates":expected_days,
        "observed_calendar_dates":counted,
        "daily_date_coverage_ratio":round(date_density,4),
        "calendar_assumption":"24x7" if always_open else "weekday",
        "min_date_coverage_ratio_for_5y":.90,
        "coverage_status":("COVERED_5Y_DAILY_DATE_DENSITY" if complete
                           else "PARTIAL_HISTORY" if ordered else "NO_BARS_OBSERVED"),
        "market_sessions_filled":False,
        "source_interval_verified_from_bars":verified_interval,
        "note":"At least 90% of assumed dates observed. Official exchange session/holiday calendar still requires audit.",
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
    outbound_methods=Counter()
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
        def sent_frame(frame):
            # Record method names only; never retain full frames, session IDs,
            # account information or other network payloads.
            for message in decode_chart_messages(frame):
                name=message.get("m")
                if name in {"create_series","request_more_data","resolve_symbol",
                            "set_visible_range","switch_timezone",
                            "modify_series","remove_series"}:
                    outbound_methods[name]+=1
        ws.on("framesent",sent_frame)
    page.on("websocket",ws_created)
    page.on("pageerror",lambda exc:js_errors.append(type(exc).__name__))
    http_status=None
    last_growth=0
    stagnation=0
    pan_attempts=0
    range_clicked=False
    range_api_available=False
    range_api_invoked=False
    range_errors=[]
    first_count=0
    range_control_candidates=[]
    try:
        response=await page.goto(target,wait_until="domcontentloaded",timeout=45000)
        http_status=response.status if response else None
        await page.wait_for_timeout(9000)
        first_count=len(observed)
        # APK sources provide setResolution('1D') and ranges().selectRange(...)
        # through TradingViewApi; this bridge may not be exposed on the PUBLIC
        # website. Discover presence at runtime, do not assume it exists.
        try:
            inspection=await page.evaluate("""() => ({
              bridge: !!(window.TradingViewApi && typeof window.TradingViewApi.activeChart === 'function'),
              rangeButtons: Array.from(document.querySelectorAll('button,[role="button"]'))
                .map(e=>(e.innerText||e.getAttribute('aria-label')||'').trim())
                .filter(s=>/^(5Y|5y|5 years|5년|5 Yr|5 yr)$/.test(s)).slice(0,8),
            })""")
            range_api_available=bool(inspection.get("bridge"))
            range_control_candidates=inspection.get("rangeButtons",[])
        except Exception as exc:
            range_errors.append("INSPECTION_"+type(exc).__name__)

        # 1. Try ordinary UI 5Y range preset where the chart exposes it.
        #    This uses the SAME click path as a user, and is preferred over
        #    any undocumented protocol message construction.
        try:
            import re
            preset=page.get_by_role("button",name=re.compile(r"^(5Y|5 years|5년|5 Yr)$",re.I))
            if await preset.count():
                await preset.first.click(timeout=2500)
                range_clicked=True
                await page.wait_for_timeout(1800)
        except Exception as exc:
            range_errors.append("UI_5Y_"+type(exc).__name__)

        # 2. When the native app-style TradingViewApi bridge is genuinely
        #    available, request DAILY resolution and the explicit five-year
        #    date range using its own public page methods. Never synthesize or
        #    replay WebSocket traffic and never access another site's cookies.
        if range_api_available and not range_clicked:
            try:
                outcome=await page.evaluate("""async ({startSec,endSec}) => {
                  const chart=window.TradingViewApi?.activeChart?.();
                  if(!chart)return {invoked:false,error:'NO_ACTIVE_CHART'};
                  if(typeof chart.setResolution==='function'){
                    await Promise.resolve(chart.setResolution('1D'));
                  }
                  const ranges=typeof chart.ranges==='function'?chart.ranges():null;
                  if(!ranges||typeof ranges.selectRange!=='function')
                    return {invoked:false,error:'NO_SELECT_RANGE'};
                  await Promise.resolve(ranges.selectRange({from:startSec,to:endSec}));
                  return {invoked:true};
                }""",{
                    "startSec":int(datetime.combine(five_year_start(asof),
                              datetime.min.time(),timezone.utc).timestamp()),
                    "endSec":int(datetime.combine(asof,
                              datetime.min.time(),timezone.utc).timestamp()),
                })
                range_api_invoked=bool(outcome.get("invoked"))
                if outcome.get("error"):
                    range_errors.append(outcome["error"])
                if range_api_invoked:
                    await page.wait_for_timeout(1800)
            except Exception as exc:
                range_errors.append("NATIVE_RANGE_"+type(exc).__name__)
        # 3. Additional historical candles normally arrive when the
        #    user drags the PRICE PANE to the right (towards older history).
        #    Do not terminate after just 3 unproductive drags.
        for attempt in range(max_pans):
            current=evaluate_history(list(observed.values()),interval=interval,asof=asof,symbol=symbol)
            if current["five_year_window_covered"]:
                break
            if len(observed)>last_growth:
                stagnation=0
            else:
                stagnation+=1
            if (stagnation>=16 or len(observed)>=MAX_BARS_OBSERVED):
                break
            last_growth=len(observed)
            # Largest on-screen price-pane canvas, not blindly the viewport.
            canvas=await page.evaluate("""() => Array.from(document.querySelectorAll('canvas'))
               .map(x=>x.getBoundingClientRect())
               .filter(r=>r.width>380&&r.height>120&&r.top>=0&&r.top<innerHeight)
               .sort((a,b)=>b.width*b.height-a.width*a.height)
               .map(r=>({x:r.x,y:r.y,w:r.width,h:r.height}))[0]||null""")
            if canvas:
                start_x=canvas["x"]+canvas["w"]*.35
                end_x=canvas["x"]+canvas["w"]*.88
                y=canvas["y"]+canvas["h"]*.55
            else:
                size=page.viewport_size or {"width":1440,"height":900}
                start_x=size["width"]*.33
                end_x=size["width"]*.85
                y=size["height"]*.56
            await page.mouse.move(start_x,y)
            await page.mouse.down()
            await page.mouse.move(end_x,y,steps=14)
            await page.mouse.up()
            pan_attempts+=1
            await page.wait_for_timeout(load_wait_ms)
        quality=evaluate_history(list(observed.values()),interval=interval,asof=asof,symbol=symbol)
        # Chart time aggregation (1D) and five calendar years of history are two independent checks.
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
            "initial_bar_count":first_count,
            "range_5y_ui_clicked":range_clicked,
            "native_range_bridge_available":range_api_available,
            "native_range_api_called":range_api_invoked,
            "range_control_candidates":range_control_candidates,
            "range_interaction_errors":range_errors[:6],
            "message_counts":dict(methods),
            "outbound_chart_method_counts":dict(outbound_methods),
            "history_request_observed":outbound_methods["request_more_data"]>0,
            "page_errors":js_errors[:6],
            **quality,
        }
    finally:
        await page.close()
