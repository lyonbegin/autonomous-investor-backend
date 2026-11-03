"""Actual deployed OUR SITE 2h AMZN chart OHLCV -> real pinned DDDS Python.

This is NOT the TradingView publication's private chart export. No mocking.
Run read-only public site API and offline local compiler, never store cookies.
"""
from __future__ import annotations
import hashlib,json,os
from pathlib import Path
import sys
from urllib.request import urlopen,Request
from urllib.parse import quote

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"editor-adapter"))
from investment_ddds_parity import DDDS_SOURCE_ID,DDDS_SOURCE_SHA
from investment_shared_bars_compare import execute_shared_bars
from investment_free_pyne_chart import PINNED_PYTHON_SHA

API="https://autonomous-investor-public-api-production.up.railway.app"

def load(url):
    req=Request(url,headers={"Accept":"application/json","User-Agent":"WF02-DDDS-Same-Bars-Verification/1.0"})
    with urlopen(req,timeout=45) as res:
        if res.status!=200:raise RuntimeError("LIVE_SITE_HTTP_NOT_200")
        blob=res.read(1_800_000)
        return json.loads(blob)

def main():
    key=quote(DDDS_SOURCE_ID,safe="")
    src=load(API+"/api/public/scripts/"+key+"/source")
    if (src.get("source_hash")!=DDDS_SOURCE_SHA or
        hashlib.sha256(src.get("source","").encode("utf-8")).hexdigest()!=DDDS_SOURCE_SHA):
        raise RuntimeError("LIVE_SITE_DDDS_PINE_SHA_MISMATCH")
    chart=load(API+"/api/public/scripts/"+key+"/chart?symbol=NASDAQ%3AAMZN&horizon=2h")
    bars=chart.get("bars")
    if (chart.get("source_hash")!=DDDS_SOURCE_SHA or
        chart.get("script_id")!=DDDS_SOURCE_ID or
        chart.get("symbol")!="NASDAQ:AMZN" or
        chart.get("horizon")!="2h" or
        chart.get("market_data",{}).get("fallback_used") is True or
        not isinstance(bars,list) or len(bars)<40):
        raise RuntimeError("LIVE_SITE_DDDS_CHART_NOT_VALID")
    shared=[{**{k:row[k] for k in ("open","high","low","close","volume")},
        "time_ms":int(row["timestamp"])} for row in bars[-300:]]
    payload={"source_id":DDDS_SOURCE_ID,"pine_source_sha256":DDDS_SOURCE_SHA,
      "symbol":"NASDAQ:AMZN","timeframe":"120","acknowledge_mpl":True,"bars":shared}
    out=execute_shared_bars(payload)
    if out["bar_count"]!=len(shared) or out["python_sha256"]!=PINNED_PYTHON_SHA:
        raise RuntimeError("LIVE_SITE_DDDS_PYTHON_RUNTIME_MISMATCH")
    if out["time_ms"]!=[b["time_ms"] for b in shared]:
        raise RuntimeError("LIVE_SITE_TIME_ALIGNMENT_FAILED")
    if out["close"]!=[float(b["close"]) for b in shared]:
        raise RuntimeError("LIVE_SITE_CLOSE_ALIGNMENT_FAILED")
    report={
      "status":"REAL_PUBLIC_SITE_DDDS_BARS_IN_PYTHON_EXECUTED",
      "source_id":DDDS_SOURCE_ID,
      "source_sha":DDDS_SOURCE_SHA,
      "python_sha":PINNED_PYTHON_SHA,
      "price_source":chart["market_data"].get("provider"),
      "price_symbol":chart["symbol"],"timeframe":chart["horizon"],
      "site_total_bars":len(bars),"same_bars_executed":out["bar_count"],
      "input_ohlcv_sha256":out["input_ohlcv_sha256"],
      "numeric_decycler_points":sum(v is not None for v in out["plots"]["Decycler"]),
      "published_tv_parity":False,"paper":False,"live":False
    }
    print("REAL_DDDS_SITE_BARS_PYTHON_PASS "+json.dumps(report,ensure_ascii=False))
    output=os.environ.get("DDDS_SITE_EVIDENCE_OUTPUT")
    if output:Path(output).write_text(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=="__main__":main()
