"""Execute actual DDDS FREE PYNE-generated Python on actual AMZN 2h OHLCV.

Real published tradingview chart via bounded existing browser worker.
No invented Pine compilation, SMA/Bollinger substitution or TV fills.
Generated Python is run ONLY in a timed child process, NEVER imported by
the public web server. Explicitly not complete 2016-2026 backtesting.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import struct
import sys
import tempfile
import threading
import urllib.request

from investment_free_pyne import ddds_artifact
from investment_ddds_parity import DDDS_SOURCE_SHA

WORKER="https://autonomous-investor-tradingview-browser-production.up.railway.app/v1/inspect/official-ddds-amzn-120-bars"
PINNED_PYTHON_SHA="ef27e69cbb71bc101431a2f9f71783c37f1f8094a7a77e080032ca3bbd7994a1"
ROOT=Path(os.environ.get("STUDIO_DB_PATH","/data/studio.sqlite3")).parent
_LOCK=threading.Lock()

def _db(root:Path=ROOT):
    root.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(root/"free_pyne_ddds_chart.sqlite3"),timeout=12)
    con.row_factory=sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS exact_ddds_chart_runs(
       sid TEXT PRIMARY KEY, captured_at TEXT NOT NULL, result_json TEXT NOT NULL)""")
    return con

def latest(sid:str,*,root:Path=ROOT)->dict:
    with _db(root) as db:
        row=db.execute("SELECT result_json FROM exact_ddds_chart_runs WHERE sid=?",(sid,)).fetchone()
    if row:return json.loads(row["result_json"])
    return {"status":"FREE_PYNE_DDDS_NOT_EXECUTED","tradingview_parity_verified":False,
            "live_orders_enabled":False}

def _finite(x):
    if type(x) not in (int,float):return None
    f=float(x)
    return f if math.isfinite(f) else None

def validate_bars(response:dict)->list[dict]:
    if not isinstance(response,dict) or (response.get("status")!="OFFICIAL_CHART_OHLCV_CAPTURED"
       or response.get("provenance")!="TRADINGVIEW_PUBLIC_CHART_PASSIVE_WEBSOCKET"
       or response.get("symbol")!="NASDAQ:AMZN" or response.get("timeframe")!="120"
       or response.get("licensed_data_api") is not False
       or response.get("complete_2016_2026_history") is not False
       or response.get("ddds_tradingview_orders_available") is not False):
        raise ValueError("FREE_DDDS_EXPECTS_REAL_PUBLIC_NASDAQ_AMZN_120_BARS")
    bars=response.get("bars")
    if not isinstance(bars,list) or not 40<=len(bars)<=300 or response.get("bar_count")!=len(bars):
        raise ValueError("FREE_DDDS_OHLCV_BAR_COUNT_INVALID")
    if response.get("interval_120_observed_gap_count",0)<12:
        raise ValueError("FREE_DDDS_TIMEFRAME_NOT_PROVEN")
    prev=None
    gaps=0
    for row in bars:
        if not isinstance(row,dict) or type(row.get("time_ms"))!=int:
            raise ValueError("FREE_DDDS_INVALID_TIME_OR_BAR")
        ts=row["time_ms"]
        if prev is not None:
            if ts<=prev:raise ValueError("FREE_DDDS_BARS_NOT_MONOTONIC")
            if ts-prev==7200000:gaps+=1
        prev=ts
        nums={key:_finite(row.get(key)) for key in ("open","high","low","close","volume")}
        if any(x is None for x in nums.values()):
            raise ValueError("FREE_DDDS_NONFINITE_OHLCV_OR_MISSING_VOLUME")
        if (nums["low"]<0 or nums["low"]>min(nums["open"],nums["close"])
             or nums["high"]<max(nums["open"],nums["close"])
             or nums["volume"]<0):
            raise ValueError("FREE_DDDS_INVALID_OHLC")
    if gaps<12:raise ValueError("FREE_DDDS_ACTUAL_120_INTERVAL_NOT_IN_BARS")
    return bars

def _limits():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(28,30))
        resource.setrlimit(resource.RLIMIT_NOFILE,(70,70))
        resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024*1024,4*1024*1024))
    except (ImportError,ValueError,OSError):
        pass

def run_generated_exact_pyne_python(python_code:str,bars:list[dict]):
    if not isinstance(python_code,str) or hashlib.sha256(
         python_code.encode("utf-8")).hexdigest()!=PINNED_PYTHON_SHA:
        raise ValueError("UNEXPECTED_DDDS_PYNE_GENERATED_CODE_SHA")
    runner=Path(__file__).resolve().parent/"investment_free_pyne_runner.py"
    if not runner.is_file():raise RuntimeError("FREE_DDDS_SUBPROCESS_RUNNER_MISSING")
    with tempfile.TemporaryDirectory(prefix="ddds-free-pyne-") as directory:
        path=Path(directory)/"exact_generated_ddds.py"
        path.write_text(python_code,encoding="utf-8")
        try:
            proc=subprocess.run(
                [sys.executable,"-I",str(runner),str(path)],
                input=json.dumps({"bars":bars,"python_sha256":PINNED_PYTHON_SHA}),
                text=True,capture_output=True,timeout=42,
                env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"},
                preexec_fn=_limits if os.name=="posix" else None,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("DDDS_FREE_PYNE_CHILD_TIMEOUT") from None
        if proc.returncode!=0 or len(proc.stdout)>800_000:
            raise RuntimeError("DDDS_FREE_PYNE_GENERATED_RUNTIME_FAILED")
        try:out=json.loads(proc.stdout)
        except ValueError:raise RuntimeError("DDDS_FREE_PYNE_OUTPUT_NOT_JSON") from None
        if (out.get("status")!="EXACT_DDDS_FREE_PYNE_EXECUTED_ON_REAL_AMZN_120_BARS"
            or out.get("python_sha256")!=PINNED_PYTHON_SHA
            or out.get("pine_sha256")!=DDDS_SOURCE_SHA
            or out.get("bars_executed")!=len(bars)
            or out.get("tv_strategy_parity_verified") is not False):
            raise RuntimeError("DDDS_FREE_PYNE_CHILD_PROVENANCE_MISMATCH")
        return out

def compare_same_market_bars(bars:list[dict], child:dict)->dict:
    """Compare the TV chart OHLCV with numpy arrays USED by the Python child.

    This is an INPUT-ONLY comparison, not a claim that the historic published
    BATS:AMZN snapshot or TradingView indicator outputs match Python plots.
    """
    if not isinstance(child,dict) or child.get("bars_executed")!=len(bars):
        raise ValueError("DDDS_MARKET_BAR_COUNT_MISMATCH")
    checksum=hashlib.sha256()
    for row in bars:
        try:
            checksum.update(struct.pack("!q5d",row["time_ms"],
                *(float(row[k]) for k in ("open","high","low","close","volume"))))
        except (KeyError,ValueError,TypeError,OverflowError,struct.error) as exc:
            raise ValueError("DDDS_INVALID_MARKET_BAR_INPUT") from exc
    ref_sha=checksum.hexdigest()
    if child.get("market_input_sha256")!=ref_sha:
        raise ValueError("DDDS_PYTHON_INPUT_OHLCV_MISMATCH")
    closes=child.get("market_input_close")
    if not isinstance(closes,list) or len(closes)!=len(bars):
        raise ValueError("DDDS_PYTHON_INPUT_CLOSE_SERIES_MISSING")
    mismatches=[]
    for i,(row,got) in enumerate(zip(bars,closes)):
        if type(got) not in (int,float) or not math.isfinite(got) or float(row["close"])!=float(got):
            mismatches.append(i)
    if mismatches:
        raise ValueError("DDDS_PYTHON_INPUT_CLOSE_SERIES_MISMATCH")
    return {"status":"SAME_TV_MARKET_BARS_USED_BY_PYTHON",
            "scope":"INPUT_OHLCV_ONLY",
            "symbol":"NASDAQ:AMZN","timeframe":"120",
            "tv_bar_count":len(bars),"python_bar_count":len(bars),
            "matching_bars":len(bars),"mismatching_bars":0,
            "tv_ohlcv_sha256":ref_sha,"python_input_ohlcv_sha256":child["market_input_sha256"],
            "published_bats_snapshot_compared":False,
            "tradingview_pine_indicator_parity_verified":False}

def execute(sid:str)->dict:
    if not _LOCK.acquire(blocking=False):
        raise ValueError("DDDS_FREE_PYNE_CHART_EXECUTION_ALREADY_RUNNING")
    try:
        artifact=ddds_artifact(sid,include_code=True)
        if artifact.get("status")!="PYNE_FREE_GENERATED_UNVALIDATED":
            raise ValueError("DDDS_ORIGINAL_PYNE_PYTHON_NOT_GENERATED")
        code=artifact.get("python_code")
        if artifact.get("python_sha256")!=PINNED_PYTHON_SHA:
            raise ValueError("DDDS_FREE_PYNE_OUTPUT_VERSION_NOT_AUDITED")
        request=urllib.request.Request(WORKER,method="POST",data=b"{}",
                headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(request,timeout=90) as resp:
            if resp.status!=200:raise RuntimeError("DDDS_AMZN_BROWSER_HTTP_ERROR")
            payload=resp.read(180_000)
        provider=json.loads(payload)
        bars=validate_bars(provider)
        result=run_generated_exact_pyne_python(code,bars)
        input_compare=compare_same_market_bars(bars,result)
        chart=[
            {"time_ms":row["time_ms"],"open":row["open"],"high":row["high"],
             "low":row["low"],"close":row["close"],"volume":row["volume"],
             "python_input_close":result["market_input_close"][index],
             **{key:result["plots"][key][index] for key in
                ("Decycler","Price anchor","Gradient","Lower band","Upper band","Stop","Target")}}
            for index,row in enumerate(bars)
        ]
        evidence={
            "status":result["status"],
            "pine_source_sha256":DDDS_SOURCE_SHA,
            "python_sha256":PINNED_PYTHON_SHA,
            "converter":"hoox-pyne-0.6.31-offline",
            "runtime":"ACTUAL_FREE_PYNE_EMITTED_PYTHON_SUBPROCESS",
            "symbol":"NASDAQ:AMZN","timeframe":"120","bar_count":len(bars),
            "observed_120min_gaps":provider["interval_120_observed_gap_count"],
            "provider":"TRADINGVIEW_PUBLIC_CHART_PASSIVE_WEBSOCKET",
            "licensed_market_data_api":False,
            "chart":chart,
            "market_data_comparison":input_compare,
            "strategy_event_count":result["trade_event_count"],
            "strategy_events":result["trade_events"],
            "strategy_events_truncated":result["trade_events_truncated"],
            "reported_netprofit":result["reported_pyne_netprofit"],
            "reported_equity":result["reported_pyne_equity"],
            "complete_2016_2026_history":False,
            "original_tv_strategy_order_fills_available":False,
            "bats_chart_snapshot_vs_nasdaq_report_conflict":True,
            "pine_to_python_emitted":True,
            "pyne_runtime_executed":True,
            "tradingview_strategies_parity_verified":False,
            "paper_enabled":False,"live_orders_enabled":False,
            "captured_at":datetime.now(timezone.utc).isoformat()
        }
        with _db() as db:
            db.execute("""INSERT INTO exact_ddds_chart_runs(sid,captured_at,result_json)
                VALUES(?,?,?) ON CONFLICT(sid) DO UPDATE SET
                captured_at=excluded.captured_at,result_json=excluded.result_json""",
                (sid,evidence["captured_at"],json.dumps(evidence,ensure_ascii=False,allow_nan=False)))
            db.commit()
        return evidence
    finally:
        _LOCK.release()
