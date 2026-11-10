"""WF02: pinned DDDS/PYNE against real TradingView public-chart worker bars.

The 40-300 latest NASDAQ:AMZN 120-minute OHLCV candles are captured by the
existing browser worker; offline Public API and Quant Lab are not used.
Older 300-bar Vela/Python evidence is cited as PRIOR, never freshly computed.
Original published TV strategy fills and 299 trades remain unverified.
"""
from __future__ import annotations
import hashlib
import json
from urllib.parse import quote
from urllib.request import Request, urlopen

from investment_ddds_parity import DDDS_SOURCE_ID, DDDS_SOURCE_SHA, DDDS_VERSION
from investment_free_pyne_chart import PINNED_PYTHON_SHA, WORKER, validate_bars
from investment_shared_bars_compare import execute_shared_bars


def fetch_site_bars(source_id=DDDS_SOURCE_ID, *, fetch=None):
    """Read exact real TradingView chart OHLCV, no fallback or fabricated bars."""
    if source_id != DDDS_SOURCE_ID:
        raise ValueError("DDDS_ONLY_RUNNER_CANNOT_EXECUTE_OTHER_STRATEGY")
    url=WORKER
    if fetch is None:
        req=Request(url,method="POST",data=b"{}",headers={
            "Accept":"application/json","Content-Type":"application/json",
            "User-Agent":"WF02-exact-DDDS-TV-worker/1.0"})
        with urlopen(req,timeout=90) as response:
            if response.status!=200:
                raise ValueError("DDDS_TV_WORKER_CHART_NOT_200")
            document=json.loads(response.read(500_000))
    else:
        document=fetch(url)
    # The existing worker validator checks NASDAQ:AMZN 120m, websocket
    # provenance, 40-300 candles, observed 120m gaps, and valid OHLCV.
    # The strategy/source SHA is separately validated against the pinned DB.
    data=validate_bars(document)
    bars=[{"time_ms":row["time_ms"],
           **{key:row[key] for key in ("open","high","low","close","volume")}}
          for row in data]
    meta={
        "provider":document["provenance"],
        "bar_count":len(bars),
        "captured_at":document.get("captured_at"),
        "observed_120min_gaps":document["interval_120_observed_gap_count"],
        "licensed_data_api":False,
        "fallback_used":False,
    }
    return bars,meta

def run_ddds_after_conversion(selected,python_code, *, fetch=None, runner=None):
    """No generic fallback or approval from just one converted Python file."""
    if (not isinstance(selected,dict) or
        selected.get("source_id")!=DDDS_SOURCE_ID or
        selected.get("version_key")!=DDDS_VERSION or
        selected.get("source_sha256")!=DDDS_SOURCE_SHA):
        raise ValueError("DDDS_EXACT_PINNED_SOURCE_VERSION_REQUIRED")
    if (not isinstance(python_code,str) or
        hashlib.sha256(python_code.encode()).hexdigest()!=PINNED_PYTHON_SHA):
        raise ValueError("DDDS_EXACT_PYNE_GENERATED_PYTHON_SHA_REQUIRED")

    # Do not use the presence of generated code as parity proof. Query the
    # pre-existing approved record for exactly the same pin and SHA.
    from investment_pipeline import saved_sources
    from investment_verified_catalog import candidate_check
    originals=saved_sources(limit=120)["sources"]
    exact=next((entry for entry in originals
      if entry["source_id"]==DDDS_SOURCE_ID and
         entry["version_key"]==DDDS_VERSION and
         entry.get("source_sha256")==DDDS_SOURCE_SHA),None)
    if not exact:
        raise ValueError("DDDS_SOURCE_NOT_IN_REGISTERED_PINNED_DATABASE")
    verdict=candidate_check(exact)
    if (not verdict.get("publish_ready") or
        verdict.get("python_sha256")!=PINNED_PYTHON_SHA):
        raise ValueError("DDDS_NOT_APPROVED_AND_PREVIOUS_SITE_PARITY_PROVEN")
    prior=verdict.get("verified_evidence") or {}
    if (prior.get("numeric_points")!=864 or
        prior.get("numeric_mismatches")!=0 or
        prior.get("verified_bar_count")!=300 or
        prior.get("symbol")!="NASDAQ:AMZN" or
        prior.get("timeframe")!="2h" or
        not prior.get("evidence_url")):
        raise ValueError("DDDS_PRIOR_PARITY_PROVENANCE_MISSING")
    bars,market=fetch_site_bars(fetch=fetch)
    payload={
      "source_id":DDDS_SOURCE_ID,"pine_source_sha256":DDDS_SOURCE_SHA,
      "symbol":"NASDAQ:AMZN","timeframe":"120","acknowledge_mpl":True,
      "bars":bars}
    runtime=execute_shared_bars(payload,compiled_code=python_code,runner=runner)
    if (runtime["status"]!="EXACT_SITE_CHART_INPUT_PYTHON_EXECUTED" or
        runtime["bar_count"]!=len(bars)):
        raise ValueError("DDDS_TV_WORKER_PYTHON_EXECUTION_NOT_VERIFIED")
    return {
       "status":"DDDS_CURRENT_PYTHON_EXECUTED_PRIOR_SITE_PARITY_REUSED",
       "source_id":DDDS_SOURCE_ID,"version_key":DDDS_VERSION,
       "source_sha256":DDDS_SOURCE_SHA,
       "python_sha256":PINNED_PYTHON_SHA,
       "symbol":"NASDAQ:AMZN","timeframe":"120",
       "bar_count":runtime["bar_count"],
       "first_time_ms":runtime["time_ms"][0],
       "last_time_ms":runtime["time_ms"][-1],
       "input_ohlcv_sha256":runtime["input_ohlcv_sha256"],
       "market_provider":market["provider"],
       "market_capture_time":market["captured_at"],
       "observed_120min_gaps":market["observed_120min_gaps"],
       "current_input_is_full_300_bars":len(bars)==300,
       "current_python_runtime_executed":True,
       "current_input_matches_python":True,
       "current_input_vela_parity_evaluated_in_this_backend_run":False,
       "previous_site_parity_verified":True,
       "previous_site_parity_points":864,
       "previous_site_parity_mismatches":0,
       "previous_site_parity_evidence_url":prior["evidence_url"],
       "previous_visible_interval_evidence_url":prior.get("visible_interval_evidence"),
       "chart_open_url":"/verified/index.html?view=compare&id="+quote(DDDS_SOURCE_ID,safe=""),
       "original_tradingview_299_trades_verified":False,
       "official_tradingview_publication_parity_verified":False,
       "paper_enabled":False,"live_orders_enabled":False
    }
