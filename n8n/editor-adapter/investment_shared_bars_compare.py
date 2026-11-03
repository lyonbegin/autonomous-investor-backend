"""WF02: execute exact DDDS-generated Python on the EXACT market bars supplied
to our existing React Vela/PineWorkerEngine chart. Not TV original export.
No extra market data request, no broker, no TradingView 299-trade comparison.
"""
from __future__ import annotations
from functools import lru_cache
import hashlib
import json
import math
import struct
from typing import Any

from investment_ddds_parity import DDDS_SOURCE_SHA, DDDS_SOURCE_ID
from investment_free_pyne_chart import (
    PINNED_PYTHON_SHA, run_generated_exact_pyne_python
)

FIELDS=("open","high","low","close","volume")
SYMBOL="NASDAQ:AMZN"
MAX_BARS=300
MIN_BARS=40


def exact_bars(payload:dict[str,Any])->tuple[list[dict],str]:
    if not isinstance(payload,dict) or set(payload)!={
        "source_id","pine_source_sha256","symbol","timeframe",
        "bars","acknowledge_mpl"
    }:
        raise ValueError("DDDS_EXACT_CHART_PAYLOAD_REQUIRED")
    if (payload["source_id"]!=DDDS_SOURCE_ID or
        payload["pine_source_sha256"]!=DDDS_SOURCE_SHA or
        payload["symbol"]!=SYMBOL or
        payload["timeframe"] not in ("120","2h") or
        payload["acknowledge_mpl"] is not True):
        raise ValueError("DDDS_SOURCE_SYMBOL_TIMEFRAME_OR_RIGHTS_MISMATCH")
    bars=payload["bars"]
    if not isinstance(bars,list) or not MIN_BARS<=len(bars)<=MAX_BARS:
        raise ValueError("DDDS_BARS_MUST_BE_40_TO_300")
    canonical=[]
    previous=None
    fingerprint=hashlib.sha256()
    for row in bars:
        if not isinstance(row,dict) or set(row)!={"time_ms",*FIELDS}:
            raise ValueError("DDDS_BAR_SHAPE_MISMATCH")
        ts=row["time_ms"]
        if type(ts) is not int or not 946684800000 <= ts <= 4102444800000:
            raise ValueError("DDDS_TIMESTAMP_INVALID")
        if previous is not None and ts<=previous:
            raise ValueError("DDDS_BARS_NOT_STRICTLY_INCREASING")
        previous=ts
        numbers={}
        for key in FIELDS:
            n=row[key]
            if type(n) not in (int,float) or not math.isfinite(n):
                raise ValueError("DDDS_OHLCV_NOT_FINITE")
            numbers[key]=float(n)
        if (numbers["open"]<=0 or numbers["high"]<=0 or
            numbers["low"]<=0 or numbers["close"]<=0 or
            numbers["low"]>min(numbers["open"],numbers["close"]) or
            numbers["high"]<max(numbers["open"],numbers["close"]) or
            numbers["high"]<numbers["low"] or
            numbers["volume"]<0):
            raise ValueError("DDDS_OHLCV_INVALID")
        normalized={"time_ms":ts,**numbers}
        canonical.append(normalized)
        fingerprint.update(struct.pack("!q5d",ts,*(numbers[k] for k in FIELDS)))
    return canonical,fingerprint.hexdigest()


@lru_cache(maxsize=1)
def pinned_python()->str:
    """Compile solely the checked-in DDDS original, never an unrelated script."""
    from investment_tv_publication import bundled_ddds_reference
    from investment_free_pyne import compile_pine
    published=bundled_ddds_reference()
    source=published.get("pine_source")
    if (published.get("source_id")!=DDDS_SOURCE_ID or
        published.get("source_sha256")!=DDDS_SOURCE_SHA or
        published.get("source_rights")!="MPL-2.0" or
        len(source.splitlines())!=141 or
        hashlib.sha256(source.encode("utf-8")).hexdigest()!=DDDS_SOURCE_SHA):
        raise ValueError("DDDS_EXACT_BUNDLED_SOURCE_INVALID")
    emitted=compile_pine(source,expected_sha=DDDS_SOURCE_SHA)
    if hashlib.sha256(emitted.encode("utf-8")).hexdigest()!=PINNED_PYTHON_SHA:
        raise ValueError("DDDS_GENERATED_PYTHON_SHA_MISMATCH")
    return emitted


def execute_shared_bars(payload:dict[str,Any], *,
                        compiled_code:str|None=None, runner=None)->dict:
    bars,bar_sha=exact_bars(payload)
    code=compiled_code if compiled_code is not None else pinned_python()
    if hashlib.sha256(code.encode("utf-8")).hexdigest()!=PINNED_PYTHON_SHA:
        raise ValueError("DDDS_GENERATED_PYTHON_SHA_MISMATCH")
    run=(runner or run_generated_exact_pyne_python)(code,bars)
    if (not isinstance(run,dict) or
        run.get("status")!="EXACT_DDDS_FREE_PYNE_EXECUTED_ON_REAL_AMZN_120_BARS" or
        run.get("bars_executed")!=len(bars) or
        run.get("python_sha256")!=PINNED_PYTHON_SHA or
        run.get("pine_sha256")!=DDDS_SOURCE_SHA):
        raise ValueError("DDDS_PYTHON_RUNTIME_PROVENANCE_MISMATCH")
    expected=("Decycler","Price anchor","Gradient","Lower band","Upper band","Stop","Target")
    plots=run.get("plots")
    if not isinstance(plots,dict) or any(
        not isinstance(plots.get(name),list) or len(plots[name])!=len(bars)
        for name in expected
    ):
        raise ValueError("DDDS_PYTHON_PLOT_SERIES_MISSING")
    for name in expected:
        if any(v is not None and (type(v) not in (float,int) or not math.isfinite(v))
               for v in plots[name]):
            raise ValueError("DDDS_PYTHON_PLOT_NOT_FINITE")
    return {
        "status":"EXACT_SITE_CHART_INPUT_PYTHON_EXECUTED",
        "source_id":DDDS_SOURCE_ID,
        "pine_source_sha256":DDDS_SOURCE_SHA,
        "python_sha256":PINNED_PYTHON_SHA,
        "input_source":"OUR_SITE_REACT_CHART_BAR_PAYLOAD",
        "input_ohlcv_sha256":bar_sha,
        "symbol":SYMBOL,"timeframe":"120",
        "bar_count":len(bars),
        "time_ms":[b["time_ms"] for b in bars],
        "close":[b["close"] for b in bars],
        "plots":{key:plots[key] for key in expected},
        "market_data_same_as_python_input":True,
        "vela_pine_ddds_indicator_parity_verified":False,
        "official_tradingview_publication_parity_verified":False,
        "published_299_trades_compared":False,
        "paper_enabled":False,"live_orders_enabled":False
    }
