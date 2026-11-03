"""WF02 official DDDS publication TRADE REPORT reference, NOT broker executions.

This module only uses the existing project's original Playwright browser worker
to click the publicly visible Strategy Report/Trades tabs. It intentionally
does not mark Pine→PyneCore strategy parity or create market-data snapshots.
"""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
from urllib import request

from investment_tv_publication import bundled_ddds_reference,latest_reference

ROOT = Path("/data/tv_publication_trade_snapshots")
WORKER_URL = ("https://autonomous-investor-tradingview-browser-production.up.railway.app"
              "/v1/inspect/official-published-ddds-trades")


def _file(sid: str, root: Path = ROOT) -> Path:
    return root / (hashlib.sha256(sid.encode("utf-8")).hexdigest()+".json")


def latest(sid: str, root: Path = ROOT) -> dict:
    p=_file(sid,root)
    if not p.is_file():
        return {
            "status":"NO_OFFICIAL_DDDS_TRADES_CAPTURE",
            "tradingview_pynecore_parity_verified":False,
            "live_orders_enabled":False
        }
    return json.loads(p.read_text(encoding="utf-8"))


def capture(sid: str, *, root: Path = ROOT, transport=None) -> dict:
    pinned=bundled_ddds_reference()
    ref=latest_reference(sid)
    if (ref.get("source_id")!=pinned["source_id"] or
        ref.get("source_sha256")!=pinned["source_sha256"]):
        raise ValueError("ONLY_EXACT_PUBLISHED_DDDS_SOURCE_TRADES_SUPPORTED")
    req=request.Request(WORKER_URL,method="POST",data=b"{}",
                        headers={"Content-Type":"application/json"})
    if transport is None:
        with request.urlopen(req,timeout=145) as response:
            if response.status != 200:
                raise ValueError("OFFICIAL_TRADE_BROWSER_WORKER_BAD_RESPONSE")
            body=response.read(380_000)
    else:
        body=transport(req)
    if isinstance(body,bytes):
        result=json.loads(body)
    elif isinstance(body,dict):
        result=body
    else:
        raise ValueError("OFFICIAL_TRADES_RESPONSE_TYPE_INVALID")
    if (result.get("status")!="PUBLISHED_DDDS_299_TRADES_CAPTURED" or
        result.get("source")!="OFFICIAL_TRADINGVIEW_PUBLICATION_VISIBLE_STRATEGY_REPORT" or
        result.get("source_code_reference_sha256")!=pinned["source_sha256"] or
        result.get("expected_trade_count")!=299 or
        result.get("observed_trade_count")!=299 or
        result.get("capture_verified_complete") is not True or
        result.get("tradingview_pynecore_parity_verified") is not False or
        result.get("is_live_strategy_tester_export") is not False):
        raise ValueError("OFFICIAL_PUBLISHED_TRADES_PROVENANCE_OR_COUNT_INCOMPLETE")
    trades=result.get("trades")
    if not isinstance(trades,list) or len(trades)!=299:
        raise ValueError("OFFICIAL_PUBLISHED_TRADES_ARRAY_INVALID")
    if [row.get("trade_number") for row in trades] != list(range(299,0,-1)):
        raise ValueError("OFFICIAL_PUBLISHED_TRADES_SEQUENCE_OR_DUPLICATES")
    for t in trades:
        if (t.get("side") not in ("LONG","SHORT") or
            not isinstance(t.get("entry_time_display"),str) or
            not isinstance(t.get("exit_time_display"),str) or
            t.get("time_zone")!="NOT_DECLARED_IN_PUBLISHED_ROW"):
            raise ValueError("OFFICIAL_PUBLISHED_TRADES_UNTYPED_OR_TIMEZONE_ASSUMED")
        for key in ("entry_price_display","exit_price_display"):
            n=t.get(key)
            if (type(n) not in (float,int) or not math.isfinite(n) or n<=0):
                raise ValueError("OFFICIAL_PUBLISHED_TRADE_PRICE_MISSING")
        raw=t.get("raw_visible_trade")
        if not isinstance(raw,str) or len(raw)>800:
            raise ValueError("OFFICIAL_PUBLISHED_TRADE_ROW_MISSING")
        # Price fields must match the actual posted row, not only the same
        # internally consistent but potentially corrupted parsed JSON.
        import re
        fields=[line.strip().replace("\u202f"," ") for line in raw.splitlines() if line.strip()]
        first=re.match(r"^(\d{1,4})\s*(Long|Short)\b",fields[0],re.I) if fields else None
        if not first or int(first.group(1))!=t["trade_number"] or first.group(2).upper()!=t["side"]:
            raise ValueError("OFFICIAL_PUBLISHED_TRADE_NUMBER_SIDE_RAW_MISMATCH")
        usd_prices=[]
        for i in range(len(fields)-1):
            if fields[i+1]=="USD":
                try:usd_prices.append(float(fields[i].replace("−","-").replace(",","")))
                except ValueError:pass
        if len(usd_prices)<2 or usd_prices[0]!=t["exit_price_display"] or usd_prices[1]!=t["entry_price_display"]:
            raise ValueError("OFFICIAL_PUBLISHED_TRADE_PRICE_RAW_TEXT_MISMATCH")
    digest=hashlib.sha256(
        "\n".join(f'{row["trade_number"]}\t{row["raw_visible_trade"]}' for row in trades)
        .encode("utf-8")).hexdigest()
    if digest!=result.get("rows_sha256"):
        raise ValueError("OFFICIAL_TRADE_RAW_UI_ROWS_HASH_MISMATCH")
    # Correct source provenance and explicit no-parity verdict preserved.
    record={**result,
            "publication_source_id":pinned["source_id"],
            "pine_source_sha256":pinned["source_sha256"],
            "exact_pine_version_key":"snapshot-sha256-"+pinned["source_sha256"][:16],
            "storage":"ORIGINAL_WF02_SESSION_IMMUTABLE_REFERENCE",
            "tradingview_pynecore_parity_verified":False,
            "paper_enabled":False,"live_orders_enabled":False,
            "stored_at":datetime.now(timezone.utc).isoformat()}
    root.mkdir(parents=True,exist_ok=True)
    import tempfile
    fd, tmp=tempfile.mkstemp(prefix=".ddds-trades-",suffix=".tmp",dir=str(root))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            json.dump(record,handle,ensure_ascii=False,allow_nan=False)
        os.replace(tmp,_file(sid,root))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return record
