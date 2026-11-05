"""One explicit live Railway-to-TradingView 5Y/1D verification.

This workflow is not cron; one NASDAQ:AAPL test, no account/session credentials.
Preserves source-observed metadata only, never copies OHLCV into CI artifact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os
import sys
import time

BASE=os.getenv("LIVE_MOBILE_BASE","https://tradingview-full-mobile-web-lab-production.up.railway.app").rstrip("/")
EVIDENCE=Path(os.getenv("LIVE_CHART_EVIDENCE","/tmp/actual-tv-5y-daily-evidence.json"))
SYMBOL="NASDAQ:AAPL"


def request(path,body=None):
    raw=json.dumps(body).encode() if body is not None else None
    req=Request(BASE+path,data=raw,
                headers={"Content-Type":"application/json","Accept":"application/json"},
                method="POST" if body is not None else "GET")
    try:
        with urlopen(req,timeout=30) as response:
            return response.status,json.loads(response.read())
    except HTTPError as exc:
        response=exc.read().decode("utf-8","replace")[:400]
        return exc.code,{"error":response}


def main():
    for attempt in range(35):
        status,info=request("/api/chart/options")
        if status==200:
            break
        print("WAIT_LIVE_DEPLOYMENT",attempt,status)
        time.sleep(4)
    assert status==200,f"Live service is missing chart endpoints: {status} {info}"
    assert info["periods"]==[{"value":5,"label":"최근 5년"}]
    assert info["intervals"]==[{"value":"1D","label":"일봉"}]
    status,invalid=request("/api/chart/collect",{
        "symbol":SYMBOL,"years":5,"interval":"1"})
    assert status==422, f"5y minute capture MUST be rejected: {status} {invalid}"
    before_status, before=request("/api/chart/status?symbol=NASDAQ%3AAAPL")
    assert before_status==200, (before_status,before)
    print("STORED_BEFORE",json.dumps({
        k:before.get(k) for k in ("state","bar_count","asof_exclusive",
                                  "five_year_extent_covered","first_time_ms","last_time_ms")},
        ensure_ascii=False))
    started_at=datetime.now(timezone.utc).isoformat()
    status,job=request("/api/chart/collect",{
        "symbol":SYMBOL,"years":5,"interval":"1D"})
    if status==409:
        # Never initiate another job concurrently. Observe existing job only.
        status,job=request("/api/chart/jobs/current")
        print("JOB_ALREADY_RUNNING",job.get("id"))
    assert status in (200,202) and job.get("state")=="running", f"No live job started: {status} {job}"
    job_id=job["id"]
    finished=None
    for attempt in range(110):
        time.sleep(3)
        status,current=request("/api/chart/jobs/current")
        if status!=200:
            print("WAIT_JOB_HEALTH",attempt,status)
            continue
        if current.get("id")!=job_id:
            raise RuntimeError("Capture task replaced during verification")
        if current.get("state")!="running":
            finished=current
            break
        if attempt%10==0:
            print("WAIT_REAL_TV_CHART",attempt*3,"seconds")
    assert finished is not None,"Live observation did not complete"
    status,after=request("/api/chart/status?symbol=NASDAQ%3AAAPL")
    meta={
        "verification":"explicit live TradingView chart through separate Railway worker",
        "verified_at":datetime.now(timezone.utc).isoformat(),
        "started_at":started_at,
        "symbol":SYMBOL,"requested_years":5,"requested_interval":"1D",
        "job_id":job_id,"job_state":finished.get("state"),
        "capture_count":finished.get("observed_count"),
        "capture_error":finished.get("reason"),
        "ws_count":finished.get("websocket_connections"),
        "history_request_observed":finished.get("history_request_observed"),
        "initial_bars_before_range":finished.get("initial_bar_count"),
        "ui_pan_attempts":finished.get("ui_pan_attempts"),
        "range_5y_ui_clicked":finished.get("range_5y_ui_clicked"),
        "native_range_bridge_available":finished.get("native_range_bridge_available"),
        "native_range_api_called":finished.get("native_range_api_called"),
        "range_control_candidates":finished.get("range_control_candidates"),
        "range_interaction_errors":finished.get("range_interaction_errors"),
        "outbound_method_counts":finished.get("outbound_chart_method_counts"),
        "persisted":status==200 and after.get("saved") is True,
        "persisted_bar_count":after.get("bar_count") if status==200 else None,
        "stored_5y_date_extent":after.get("five_year_extent_covered") if status==200 else None,
        "stored_first_time_ms":after.get("first_time_ms") if status==200 else None,
        "stored_last_time_ms":after.get("last_time_ms") if status==200 else None,
        "reference_bars_from_ci_fixture":False,
    }
    EVIDENCE.parent.mkdir(parents=True,exist_ok=True)
    EVIDENCE.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print("LIVE_TRADINGVIEW_CHART_5Y_DAILY_AUDIT",json.dumps(meta,ensure_ascii=False))
    if finished["state"] not in ("completed","saved_partial"):
        raise RuntimeError("Live chart failed; see job evidence, do not claim collected")
    assert meta["persisted"],"Real chart bars were observed but not saved to volume"
    assert (meta["persisted_bar_count"] or 0)>0
    if not meta["stored_5y_date_extent"]:
        print("IMPORTANT_ONLY_PARTIAL_HISTORY: 5Y daily NOT complete")
    else:
        print("OBSERVED_FIVE_YEAR_DATE_EXTENT: Exchange day completeness not independently audited")


if __name__=="__main__":
    main()
