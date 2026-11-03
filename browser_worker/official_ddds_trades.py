"""Bounded public TradingView DDDS publication report capture, via REAL browser UI.

No private API, websocket replay, auth bypass, invented strategy trades or
market-data service. The public publication represents a frozen author's
backtest and does NOT establish live brokerage fills or Pine/Python parity.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import re

PUBLISHED_DDDS_URL = (
    "https://www.tradingview.com/script/"
    "LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/"
)
EXPECTED_COUNT = 299
TRADE_PATTERN = re.compile(r"^\s*(\d{1,4})\s*(Long|Short)\b", re.I)
TIME_PATTERN = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d{2}$")


def _numeric(text):
    if not isinstance(text, str):
        return None
    raw = text.replace("\u2212", "-").replace("\u202f", "").replace("\xa0", "").replace(",", "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


def parse_visible_trade(raw: str) -> dict | None:
    """Exact public report row with no guessing of timezone/order event timing."""
    match = TRADE_PATTERN.match(raw)
    if not match:
        return None
    number = int(match.group(1))
    if number < 1 or number > 500:
        return None
    side = match.group(2).upper()
    lines = [x.strip().replace("\u202f", " ") for x in raw.splitlines() if x.strip()]
    # Public TradingView row visually displays Exit and Entry as two lines,
    # then their timestamps and prices. Never infer a timezone from the display.
    exit_time = next((x for x in lines if TIME_PATTERN.fullmatch(x)), None)
    pos = lines.index(exit_time) if exit_time is not None else -1
    entry_time = lines[pos+1] if pos>=0 and len(lines)>pos+1 and TIME_PATTERN.fullmatch(lines[pos+1]) else None
    money = []
    for i in range(max(pos+2,0),len(lines)-1):
        if lines[i+1]=="USD" and _numeric(lines[i]) is not None:
            money.append(_numeric(lines[i]))
    return {
        "trade_number":number,"side":side,
        "entry_time_display":entry_time,
        "exit_time_display":exit_time,
        "entry_price_display":money[1] if len(money)>=2 else None,
        "exit_price_display":money[0] if money else None,
        "time_zone":"NOT_DECLARED_IN_PUBLISHED_ROW",
        "raw_visible_trade":raw[:700]
    }


async def observe_public_ddds_trade_report(context):
    page = await context.new_page()
    try:
        response = await page.goto(PUBLISHED_DDDS_URL,
                                   wait_until="domcontentloaded",timeout=45000)
        if not response or response.status != 200:
            raise ValueError("PUBLIC_DDDS_PAGE_NOT_HTTP_200")
        await page.wait_for_timeout(4500)
        top = page.get_by_text("Strategy report",exact=True).filter(visible=True).first
        await top.click(timeout=10000)
        report = page.locator('[data-qa-id="backtesting-static"]').first
        await report.wait_for(timeout=18000)
        key_facts = " | ".join(await report.locator('[data-qa-id="strategy-key-facts"]').all_inner_texts())
        trades_tab = report.locator('[role="tab"][id="List of Trades"]').first
        await trades_tab.click(timeout=10000)
        await page.wait_for_timeout(1300)
        scroll = await report.evaluate_handle("""root => {
            const els = [...root.querySelectorAll('*')].filter(el => {
                const style=getComputedStyle(el);
                return el.clientHeight>120 &&
                  el.scrollHeight>el.clientHeight+150 &&
                  /auto|scroll/.test(style.overflowY) &&
                  el.querySelectorAll('tr,[role="row"]').length>2;
            });
            return els.sort((a,b)=>
              (b.scrollHeight-b.clientHeight)-(a.scrollHeight-a.clientHeight))[0] || null;
        }""")
        if not await scroll.evaluate("(el)=>Boolean(el)"):
            raise ValueError("PUBLISHED_REPORT_TRADES_SCROLL_CONTAINER_MISSING")
        seen={}
        for _ in range(90):
            texts=await report.locator('tr,[role="row"]').all_inner_texts()
            for txt in texts:
                row=parse_visible_trade(txt)
                if row is not None:
                    seen[row["trade_number"]]=row
            details=await scroll.evaluate("""el=>({
                top:el.scrollTop, max:el.scrollHeight-el.clientHeight, viewport:el.clientHeight
            })""")
            if details["top"]>=details["max"]-12:
                break
            await scroll.evaluate("""el=>{
                el.scrollTop=Math.min(el.scrollHeight-el.clientHeight,
                  el.scrollTop+Math.max(180,el.clientHeight*.85))
            }""")
            await page.wait_for_timeout(150)
        results=[seen[n] for n in sorted(seen,reverse=True)]
        missing=[n for n in range(1,EXPECTED_COUNT+1) if n not in seen]
        count_ok=len(results)==EXPECTED_COUNT and not missing
        immutable_report_matches=(
            "17,961.73" in key_facts and "88/299" in key_facts and
            "1.556" in key_facts)
        # Require exact report metrics AND 299/299 contiguous trades before
        # labelling a complete immutable published reference.
        status=("PUBLISHED_DDDS_299_TRADES_CAPTURED"
                if count_ok and immutable_report_matches
                else "PUBLISHED_DDDS_REPORT_SNAPSHOT_INCOMPLETE_OR_CHANGED")
        digest=hashlib.sha256(
            "\n".join(f'{r["trade_number"]}\t{r["raw_visible_trade"]}' for r in results)
            .encode("utf-8")).hexdigest()
        return {
            "status":status,
            "source":"OFFICIAL_TRADINGVIEW_PUBLICATION_VISIBLE_STRATEGY_REPORT",
            "is_live_strategy_tester_export":False,
            "is_trade_execution_proof":False,
            "tradingview_pynecore_parity_verified":False,
            "publication_url":PUBLISHED_DDDS_URL,
            "source_code_reference_sha256":"5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507",
            "displayed_symbol":"BATS:AMZN",
            "displayed_timeframe":"2h",
            "report_key_facts":key_facts[:600],
            "expected_trade_count":EXPECTED_COUNT,
            "observed_trade_count":len(results),
            "missing_trade_numbers":missing,
            "rows_sha256":digest,
            "trades":results,
            "capture_verified_complete":status=="PUBLISHED_DDDS_299_TRADES_CAPTURED",
            "captured_at":datetime.now(timezone.utc).isoformat()
        }
    finally:
        await page.close()
