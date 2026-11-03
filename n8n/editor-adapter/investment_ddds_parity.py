"""DDDS Pine-v6 ↔ PyneComp/PyneCore evidence gate.

Compare the exact published TradingView 299-trade baseline with one genuine
isolated PyneCore run. A visual match, backfilled price series, unverified
source, or matching summary never grants equivalence or PAPER/LIVE access.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
from typing import Any

DDDS_SOURCE_SHA = "5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507"
DDDS_SOURCE_ID = "PUB;5442675d418140c58486eb4a7ae12768"
DDDS_VERSION = "snapshot-sha256-" + DDDS_SOURCE_SHA[:16]
DDDS_COMPILER = "pynecomp-http-v1-pynecore-6.11.1"
DDDS_PUBLICATION_SYMBOL = "NASDAQ:AMZN"
DDDS_FROZEN_SNAPSHOT_SYMBOL = "BATS:AMZN"
DDDS_PUBLICATION_TIMEFRAME = "120"
EXPECTED_TRADES = 299
# Source defaults, not a claim that the author's published Properties tab is
# equal to these settings. A separate TV Properties capture is mandatory.
SOURCE_DEFAULTS = {
    "startLen":31,"endLen":36,"allowLongs":True,"allowShorts":True,
    "useDecycler":True,"decPeriod":60,"slopeBars":3,
    "useMFI":True,"mfiLen":14,"mfiSmooth":4,
    "atrLen":14,"stopMult":2.0,"tpMult":3.0,
    "initial_capital":10000,
    "default_qty_type":"strategy.percent_of_equity",
    "default_qty_value":100,
    "commission_type":"strategy.commission.percent",
    "commission_value":0.05,
    "pyramiding":0,
}


def source_defaults_from_pine(pine: str) -> dict:
    """Read the verified Pine, not values invented by the comparison UI."""
    if not isinstance(pine,str) or hashlib.sha256(pine.encode()).hexdigest()!=DDDS_SOURCE_SHA:
        raise ValueError("DDDS_EXACT_PINNED_SOURCE_REQUIRED")
    typed = dict()
    for name in ("startLen","endLen","allowLongs","allowShorts","useDecycler",
                 "decPeriod","slopeBars","useMFI","mfiLen","mfiSmooth",
                 "atrLen","stopMult","tpMult"):
        kind = ("bool" if name in ("allowLongs","allowShorts","useDecycler","useMFI")
                else "float" if name in ("stopMult","tpMult") else "int")
        match=re.search(
            r"(?m)^\s*"+kind+r"\s+"+name+
            r"\s*=\s*input\.(?:int|bool|float)\(\s*([0-9.]+|true|false)\b",pine)
        if not match:raise ValueError("DDDS_PINNED_INPUT_NOT_PARSED:"+name)
        raw=match.group(1)
        typed[name]=raw=="true" if kind=="bool" else float(raw) if kind=="float" else int(raw)
    match=re.search(r"(?s)\bstrategy\s*\((.*?)\)\s*[\r\n]",pine)
    if not match:raise ValueError("DDDS_STRATEGY_SETTINGS_MISSING")
    declaration=match.group(1)
    for name in ("initial_capital","default_qty_value","commission_value","pyramiding"):
        hit=re.search(r"\b"+name+r"\s*=\s*([0-9.]+)\b",declaration)
        if not hit:raise ValueError("DDDS_STRATEGY_PROPERTY_MISSING:"+name)
        typed[name]=float(hit.group(1)) if "." in hit.group(1) else int(hit.group(1))
    for name in ("default_qty_type","commission_type"):
        hit=re.search(r"\b"+name+r"\s*=\s*([A-Za-z0-9_.]+)\b",declaration)
        if not hit:raise ValueError("DDDS_STRATEGY_PROPERTY_MISSING:"+name)
        typed[name]=hit.group(1)
    if typed!=SOURCE_DEFAULTS:
        raise ValueError("DDDS_SOURCE_DEFAULT_SETTINGS_CHANGED")
    return typed


def _f(value: Any, label: str) -> float:
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        raise ValueError(label+"_MISSING_OR_INVALID")
    from math import isfinite
    if not isfinite(float(value)):raise ValueError(label+"_NONFINITE")
    return float(value)


def _status(code,reason,**extra) -> dict:
    return {
        "status":code,"reason":reason,
        "pine_sha256":DDDS_SOURCE_SHA,"symbol":DDDS_PUBLICATION_SYMBOL,
        "timeframe_minutes":120,"tradingview_pynecore_parity_verified":False,
        "conversion_validated":False,
        "paper_enabled":False,"live_orders_enabled":False,
        **extra
    }


def compare_published_ddds_trades(reference: dict, runtime: dict,
                                  *, max_samples=12) -> dict:
    """Compare only actual chronological closed trades.

    Publication times omit the timezone, broker order events and fill-rule
    settings. Even a price/side-only match is provisional and cannot
    constitute order/event parity. Cannot turn on PAPER or LIVE trading.
    """
    if (not isinstance(reference,dict) or
        reference.get("status")!="PUBLISHED_DDDS_299_TRADES_CAPTURED" or
        reference.get("pine_source_sha256")!=DDDS_SOURCE_SHA or
        reference.get("capture_verified_complete") is not True or
        reference.get("observed_trade_count")!=EXPECTED_TRADES):
        return _status("BLOCKED_OFFICIAL_TRADE_BASELINE_MISSING",
                       "정확한 DDDS 299/299 게시 거래 기준값이 없습니다.")
    rows=reference.get("trades")
    if (not isinstance(rows,list) or len(rows)!=EXPECTED_TRADES or
        [x.get("trade_number") for x in rows]!=list(range(299,0,-1))):
        return _status("BLOCKED_OFFICIAL_TRADE_BASELINE_INCOMPLETE",
                       "게시 거래 번호나 행 개수가 일치하지 않습니다.")
    if not isinstance(runtime,dict):
        return _status("BLOCKED_DDDS_PYNECORE_RESULT_MISSING",
                       "DDDS를 실행한 PyneCore 결과가 없습니다.")
    if (runtime.get("pine_source_sha256")!=DDDS_SOURCE_SHA or
        runtime.get("source_id")!=DDDS_SOURCE_ID or
        runtime.get("version_key")!=DDDS_VERSION or
        runtime.get("compiler_id")!=DDDS_COMPILER or
        runtime.get("compiler_result_origin")!="REAL_PYNECOMP_API" or
        not isinstance(runtime.get("python_sha256"),str) or
        re.fullmatch(r"[0-9a-f]{64}",runtime["python_sha256"]) is None):
        return _status("BLOCKED_IDENTICAL_PYNECOMP_ARTIFACT_NOT_PROVEN",
                       "동일 Pine 원본에서 PyneComp로 생성된 Python 산출물의 출처·해시가 필요합니다.")
    # The original author-posted chart snapshot and the current published
    # Strategy Report Properties disagree (BATS vs NASDAQ). No equivalence
    # can be declared until the chosen original reference is reconciled.
    if runtime.get("reference_symbol_resolution") != "PUBLISHED_REPORT_NASDAQ_AMZN_RECONCILED":
        return _status("BLOCKED_PUBLISHED_CHART_REPORT_SYMBOL_CONFLICT",
                       "공식 게시 차트 BATS:AMZN과 Strategy Report 속성 NASDAQ:AMZN이 일치하지 않습니다.",
                       frozen_chart_symbol=DDDS_FROZEN_SNAPSHOT_SYMBOL,
                       published_report_symbol=DDDS_PUBLICATION_SYMBOL)
    if (runtime.get("symbol")!=DDDS_PUBLICATION_SYMBOL or
        str(runtime.get("interval_minutes"))!="120"):
        return _status("BLOCKED_MARKET_SYMBOL_TIMEFRAME_MISMATCH",
                       "공식 게시 기준은 BATS:AMZN 2시간봉입니다.")
    trades=runtime.get("closed_trades")
    if not isinstance(trades,list):
        return _status("BLOCKED_PYNECORE_TRADE_EVENTS_MISSING",
                       "실제 PyneCore 종료 거래 이벤트가 없습니다.")
    if (runtime.get("run_origin")!="ISOLATED_PYNECORE_SCRIPT_RUNNER" or
        runtime.get("data_origin") not in
          ("OFFICIAL_TRADINGVIEW_CHART_WITH_PROVENANCE",
           "INDEPENDENT_LICENSED_BATS_AMZN_HISTORY")):
        return _status("BLOCKED_PYNECORE_OR_MARKET_PROVENANCE",
                       "격리 PyneCore 실행 및 실제 BATS:AMZN OHLCV 출처를 확인할 수 없습니다.")
    if runtime.get("data_coverage_complete") is not True:
        return _status("BLOCKED_BATS_AMZN_2H_HISTORY_COVERAGE",
                       "2016년부터 2026년까지의 NASDAQ:AMZN 2시간봉 전체 입력 구간이 확인되지 않았습니다.",
                       actual_trade_count=len(trades))
    if len(trades)!=EXPECTED_TRADES:
        return _status("DDDS_TRADE_COUNT_MISMATCH",
                       "TV 게시 거래 수와 PyneCore 종료 거래 수가 다릅니다.",
                       reference_trade_count=299,actual_trade_count=len(trades),
                       count_difference=len(trades)-EXPECTED_TRADES)
    # Reference rows are newest first. Python closed trades are oldest first.
    expected=list(reversed(rows))
    mismatches=[]
    compared_prices=0
    for index,(tv,py) in enumerate(zip(expected,trades),start=1):
        fail=[]
        if tv["trade_number"]!=index:fail.append("TV_TRADE_ORDER")
        if not isinstance(py,dict):fail.append("PY_TRADE_NOT_OBJECT")
        else:
            if py.get("direction")!=tv.get("side"):fail.append("DIRECTION")
            for label,py_key,tv_key in (
                ("ENTRY_PRICE","entry_price","entry_price_display"),
                ("EXIT_PRICE","exit_price","exit_price_display")):
                try:
                    a=_f(py.get(py_key),label)
                    b=_f(tv.get(tv_key),label)
                    # Published UI only prints cents. +/- half cent is a
                    # display-rounding check, not an engine exactness claim.
                    if abs(a-b)>0.005000001:fail.append(label)
                    compared_prices+=1
                except ValueError:
                    fail.append(label+"_MISSING")
        if fail and len(mismatches)<max_samples:
            mismatches.append({
                "trade_number":index,"fields":fail,
                "tv_direction":tv.get("side"),
                "tv_entry_price":tv.get("entry_price_display"),
                "tv_exit_price":tv.get("exit_price_display"),
                "py_direction":py.get("direction") if isinstance(py,dict) else None,
                "py_entry_price":py.get("entry_price") if isinstance(py,dict) else None,
                "py_exit_price":py.get("exit_price") if isinstance(py,dict) else None
            })
    if mismatches:
        return _status("DDDS_PUBLISHED_PRICE_SIDE_MISMATCH",
                       "실제 DDDS PyneCore 거래와 게시 거래의 방향·가격이 다릅니다.",
                       reference_trade_count=299,actual_trade_count=299,
                       compared_price_values=compared_prices,
                       mismatch_samples=mismatches)
    # Even all matched prices cannot confer 1:1 TV parity because report
    # timezone, intra-bar fills, order submission/cancel events and TV
    # Properties defaults have not been externally verified.
    return _status("DDDS_TRADE_PRICES_MATCH_REVIEW_REQUIRED",
                   "299건 방향·진입가·청산가가 게시 표시 정밀도에서 일치하지만, "
                   "TV 설정·시각·주문/체결 이벤트 동등성은 별도 검증이 필요합니다.",
                   reference_trade_count=299,actual_trade_count=299,
                   compared_price_values=compared_prices,
                   displayed_price_tolerance_usd=0.005,
                   missing_fidelity_checks=[
                       "TV_STRATEGY_PROPERTIES_VERIFIED",
                       "TV_PUBLISHED_TIMESTAMPS_TIMEZONE",
                       "PINE_INPUTS_ON_PUBLISHED_RUN",
                       "ORDER_PLACEMENT_AND_FILL_EVENTS",
                       "FULL_SERIES_PLOTS_BY_UTC_BAR",
                   ])


def current_published_properties_proof() -> dict:
    """Immutable excerpt from ACTUAL Chromium-observed TradingView Properties.

    Original BATS author snapshot conflicts with current NASDAQ report; this
    document is evidence of the current public report, not equivalence proof.
    """
    from pathlib import Path
    import json
    file=Path(__file__).resolve().parent/"fixtures/ddds_verified_public_properties_20261103.json"
    evidence=json.loads(file.read_text(encoding="utf-8"))
    if (evidence.get("raw_properties_text_sha256")!=
       "bd6f98715fd4c5462130dac2aa31d188d42875655cf87e5a1fc5d8e30ab0aab7" or
       evidence.get("currently_displayed_report_symbol")!=DDDS_PUBLICATION_SYMBOL or
       evidence.get("publication_chart_snapshot_symbol")!=DDDS_FROZEN_SNAPSHOT_SYMBOL or
       evidence.get("symbol_discrepancy") is not True):
        raise ValueError("PUBLISHED_DDDS_PROPERTIES_PINNED_EVIDENCE_CONFLICT")
    matches=all(SOURCE_DEFAULTS.get(k)==v for k,v in
                {**evidence["current_report_strategy_inputs"],
                 **{k:v for k,v in evidence["current_report_execution"].items()
                     if k!="slippage_ticks"}}.items())
    evidence["current_report_inputs_match_pine_defaults"]=bool(matches)
    evidence["same_chart_symbol_confirmed"]=False
    return evidence


def readiness_from_existing_cache(*, pine: str, reference: dict|None,
                                  cached_python: str|None, free_compiler_installed: bool,
                                  postgres_synced: bool|None = None) -> dict:
    settings=source_defaults_from_pine(pine)
    property_evidence=current_published_properties_proof()
    has_published=(isinstance(reference,dict) and
      reference.get("status")=="PUBLISHED_DDDS_299_TRADES_CAPTURED" and
      reference.get("pine_source_sha256")==DDDS_SOURCE_SHA and
      reference.get("observed_trade_count")==299 and
      reference.get("capture_verified_complete") is True)
    code_sha=hashlib.sha256(cached_python.encode()).hexdigest() if cached_python else None
    missing=[]
    if not has_published:missing.append("OFFICIAL_PUBLISHED_DDDS_299_TRADES")
    if not cached_python and not free_compiler_installed:missing.append("PYNE_FREE_RUNTIME_NOT_INSTALLED")
    if not cached_python:missing.append("EXACT_DDDS_FREE_PYNE_PYTHON")
    missing.extend([
        "VERIFIED_NASDAQ_AMZN_120MIN_FULL_HISTORY_2016_2026",
        "RECONCILE_BATS_CHART_VS_NASDAQ_STRATEGY_REPORT",
        "ISOLATED_DDDS_FREE_PYNE_RUNTIME_RESULT",
        "PUBLISHED_TV_PROPERTIES_AND_INPUTS",
        "PUBLISHED_TRADE_TIMEZONE",
        "ORDER_EVENT_AND_UTC_PLOT_PARITY"
    ])
    return _status(
      "DDDS_VERIFICATION_BLOCKED" if missing else "DDDS_READY_TO_REVIEW",
      "원본 DDDS와 게시 거래가 있어도 생성 Python과 동일 시장/설정·주문 검증 없이 승인 불가",
      saved_published_trade_count=299 if has_published else 0,
      exact_free_pyne_code_available=bool(cached_python),
      exact_free_pyne_python_sha256=code_sha,
      free_pyne_compiler_installed=bool(free_compiler_installed),
      postgres_synced=postgres_synced,
      source_input_defaults=settings,
      published_properties_observed_at=property_evidence["observed_at"],
      published_properties_evidence_url=property_evidence["evidence_run"],
      published_properties_current_report_inputs_match_defaults=
          property_evidence["current_report_inputs_match_pine_defaults"],
      published_properties_trade_range_display=
          property_evidence["current_report_trading_range_display"],
      published_properties_backtest_range_display=
          property_evidence["current_report_backtesting_range_display"],
      published_properties_slippage_ticks=
          property_evidence["current_report_execution"]["slippage_ticks"],
      published_chart_snapshot_symbol=DDDS_FROZEN_SNAPSHOT_SYMBOL,
      current_strategy_report_properties_symbol=DDDS_PUBLICATION_SYMBOL,
      strategy_report_symbol_conflict=True,
      settings_are_published_properties=False,
      missing_requirements=missing)


def readiness_for_studio_session(sid: str) -> dict:
    """Read existing DDDS source, exact free PYNE cache and TV 299 trades.

    GET endpoint calls NO remote compiler, fetches no unsupported market feed,
    and never executes untrusted Python. Reports actual blockers rather than
    using the unrelated AAPL/SMA demo as a stand-in for DDDS.
    """
    from contextlib import closing
    import os
    from investment_tv_publication import latest_reference
    from investment_tv_trade_reference import latest as latest_trades
    from investment_source_registry import open_registry

    source=latest_reference(sid)
    if source.get("source_sha256")!=DDDS_SOURCE_SHA:
        return _status("BLOCKED_SELECTED_PINE_IS_NOT_DDDS",
                       "선택한 TradingView 게시 원본은 DDDS 141줄이 아닙니다.",
                       selected_sha256=source.get("source_sha256"))
    source_defaults_from_pine(source["pine_source"])
    cache=None
    rights=None
    sqlite_present=False
    with closing(open_registry()) as db:
        names={row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "investment_pine_payloads" in names:
            source_row=db.execute(
                "SELECT rights_state,pine_code FROM investment_pine_payloads "
                "WHERE kind='strategy' AND source_id=? AND version_key=?",
                (DDDS_SOURCE_ID,DDDS_VERSION)).fetchone()
            if source_row is not None:
                rights=source_row["rights_state"]
                sqlite_present=hashlib.sha256(source_row["pine_code"].encode()).hexdigest()==DDDS_SOURCE_SHA
                if not sqlite_present:rights="BLOCKED_SHA_MISMATCH"
        if "investment_pyne_free_artifacts" in names:
            from investment_pynecomp import dependency_lock
            from investment_free_pyne import cached as free_cached
            cache=free_cached("strategy",DDDS_SOURCE_ID,DDDS_VERSION,
                              DDDS_SOURCE_SHA,dependency_lock([]))
    tv=latest_trades(sid)
    readiness=readiness_from_existing_cache(
        pine=source["pine_source"],
        reference=tv,cached_python=cache,
        free_compiler_installed=__import__("investment_free_pyne").installed(),
        postgres_synced=None)
    readiness.update({
        "source_id":DDDS_SOURCE_ID,"version_key":DDDS_VERSION,
        "stored_source_rights_state":rights,
        "identical_source_in_workflow_db":sqlite_present,
        "tradingview_reference_rows_sha256":tv.get("rows_sha256")
           if tv.get("status")=="PUBLISHED_DDDS_299_TRADES_CAPTURED" else None,
        "actual_ddds_pynecore_run_available":False,
        "historical_data_coverage_verified":False,
        "published_properties_verified":False,
        "live_execution_available":False
    })
    # This is ACTUAL DDDS free PYNE execution on published TradingView AMZN
    # 120-minute bars. It is NOT PyneCore, not a full-history backtest, and
    # cannot imply TradingView trade/plot parity.
    from investment_free_pyne_chart import latest as latest_free_ddds_chart
    execution=latest_free_ddds_chart(sid)
    has_actual_free_ddds_run=(
        execution.get("status")=="EXACT_DDDS_FREE_PYNE_EXECUTED_ON_REAL_AMZN_120_BARS"
        and execution.get("pine_source_sha256")==DDDS_SOURCE_SHA
        and execution.get("python_sha256")==readiness.get("exact_free_pyne_python_sha256")
        and execution.get("runtime")=="ACTUAL_FREE_PYNE_EMITTED_PYTHON_SUBPROCESS"
        and execution.get("symbol")=="NASDAQ:AMZN"
        and execution.get("timeframe")=="120"
        and execution.get("tradingview_strategies_parity_verified") is False
        and execution.get("complete_2016_2026_history") is False
        and isinstance(execution.get("bar_count"),int)
        and execution["bar_count"]>=40)
    readiness["actual_ddds_free_pyne_run_available"]=bool(has_actual_free_ddds_run)
    readiness["actual_ddds_free_pyne_run_bars"]=(execution["bar_count"]
        if has_actual_free_ddds_run else 0)
    readiness["actual_ddds_free_pyne_order_events"]=(execution.get("strategy_event_count")
        if has_actual_free_ddds_run else None)
    if has_actual_free_ddds_run:
        readiness["missing_requirements"]=[
            item for item in readiness["missing_requirements"]
            if item!="ISOLATED_DDDS_FREE_PYNE_RUNTIME_RESULT"]
    if rights!="APPROVED":
        readiness["missing_requirements"].insert(0,"EXACT_DDDS_MPL_SOURCE_APPROVAL")
    if not sqlite_present:
        readiness["missing_requirements"].insert(0,"EXACT_DDDS_IN_WORKFLOW_SOURCE_DB")
    return readiness
