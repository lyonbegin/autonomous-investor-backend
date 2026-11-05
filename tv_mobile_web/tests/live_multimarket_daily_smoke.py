"""Explicit serial live verification of independent TV chart daily data.

Run only when source is intentionally pushed. No cron and no background agent.
One instrument at a time; each market outcome reported independently.
"""
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import quote
from pathlib import Path
import json
import time

BASE="https://tradingview-full-mobile-web-lab-production.up.railway.app"
SYMBOLS=["KRX:005930","BINANCE:BTCUSDT"]
OUT=Path("/tmp/tv-multimarket-5y-evidence")
OUT.mkdir(parents=True,exist_ok=True)


def call(path,payload=None):
    req=Request(BASE+path,
                data=json.dumps(payload).encode() if payload is not None else None,
                method="POST" if payload is not None else "GET",
                headers={"Accept":"application/json",
                         "Content-Type":"application/json"})
    try:
        with urlopen(req,timeout=35) as resp:
            return resp.status,json.loads(resp.read())
    except HTTPError as exc:
        try:detail=json.loads(exc.read())
        except ValueError:detail={"code":f"HTTP_{exc.code}"}
        return exc.code,detail


def verify(symbol):
    encoded=quote(symbol,safe="")
    status,before=call("/api/chart/status?symbol="+encoded)
    assert status==200,(status,before)
    status,job=call("/api/chart/collect",{
        "symbol":symbol,"years":5,"interval":"1D"})
    if status==409:
        status,job=call("/api/chart/jobs/current")
    if status not in (200,202) or job.get("state")!="running":
        return {"symbol":symbol,"error":"JOB_NOT_STARTED","response":job}
    job_id=job["id"]
    print("START_MARKET",symbol,"job",job_id,flush=True)
    result={"symbol":symbol,"job_id":job_id,"requested":"5Y/1D",
            "before_saved":before.get("saved",False),
            "before_bars":before.get("bar_count",0)}
    final=None
    for i in range(112):
        time.sleep(3)
        code,state=call("/api/chart/jobs/current")
        if code!=200:
            continue
        if state.get("id")!=job_id:
            result["error"]="JOB_REPLACED";break
        if state.get("state")!="running":
            final=state;break
        if i%12==0:
            print("MARKET_RUNNING",symbol,"elapsed",3*(i+1),"seconds",flush=True)
    if final is None:
        result.setdefault("error","CAPTURE_NOT_COMPLETED")
        return result
    code,after=call("/api/chart/status?symbol="+encoded)
    result.update({
        "capture_state":final.get("state"),
        "captured_bars":final.get("observed_count"),
        "original_chart_ws_count":final.get("websocket_connections"),
        "history_more_requests":(final.get("outbound_chart_method_counts") or {}).get("request_more_data",0),
        "ui_5y_range_clicked":final.get("range_5y_ui_clicked"),
        "native_app_range_bridge_available":final.get("native_range_bridge_available"),
        "native_app_range_bridge_called":final.get("native_range_api_called"),
        "ui_pan_attempts":final.get("ui_pan_attempts"),
        "error":final.get("reason"),
        "saved":after.get("saved",False) if code==200 else False,
        "stored_bars":after.get("bar_count") if code==200 else None,
        "five_year_daily_covered":after.get("five_year_extent_covered") if code==200 else False,
        "first_time_ms":after.get("first_time_ms") if code==200 else None,
        "last_time_ms":after.get("last_time_ms") if code==200 else None,
        "source":"ACTUAL_TV_CHART_WEBSOCKET",
        "fixture":False
    })
    if result["saved"]:
        code,stored=call("/api/chart/history?symbol="+encoded)
        if code==200:
            result["history_read_sha256_verified"]=True
            result["history_len"]=len(stored.get("bars",[]))
            result["density"]=stored.get("quality",{}).get("daily_date_coverage_ratio")
            result["calendar"]=stored.get("quality",{}).get("calendar_assumption")
            result["history_match_count"]=result["history_len"]==result["stored_bars"]
        else:
            result["history_read_sha256_verified"]=False
            result["history_read_error"]=stored
    return result


def main():
    start=datetime.now(timezone.utc).isoformat()
    results=[]
    for symbol in SYMBOLS:
        try:
            results.append(verify(symbol))
        except Exception as exc:
            results.append({"symbol":symbol,"error":type(exc).__name__+" "+str(exc)[:250]})
        print("LIVE_MULTIMARKET_RESULT",json.dumps(results[-1],ensure_ascii=False),flush=True)
        time.sleep(4)
    body={"started_at_utc":start,"finished_at_utc":datetime.now(timezone.utc).isoformat(),
          "user_requested_only":True,"no_cron":True,"years":5,"interval":"1D","results":results}
    (OUT/"per-market-results.json").write_text(json.dumps(body,ensure_ascii=False,indent=2),encoding="utf-8")
    successes=sum(bool(x.get("saved")) for x in results)
    print("ACTUAL_MARKET_CHART_SAVED",successes,"of",len(SYMBOLS),flush=True)
    if successes==0:
        raise RuntimeError("No new market's TradingView chart daily data could be stored")


if __name__=="__main__":
    main()
