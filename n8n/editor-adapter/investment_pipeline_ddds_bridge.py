"""WF02 bridge: same exact stored Pine/PYNE artifact, 300 real site bars.

This stage executes the generated Python on the current public API's 2h bars.
The *previous* Vela-vs-Python comparison is independently stored and linked,
not misrepresented as a new TradingView website comparison or a newly run
Vela check in this backend process. Rendering both charts is delegated to the
verified admin React UI, which re-executes Vela and Python on matching bars.
"""
from __future__ import annotations
import hashlib
import json
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import os

from investment_ddds_parity import DDDS_SOURCE_ID, DDDS_SOURCE_SHA, DDDS_VERSION
from investment_free_pyne_chart import PINNED_PYTHON_SHA
from investment_shared_bars_compare import execute_shared_bars

PUBLIC_API_DEFAULT="https://autonomous-investor-public-api-production.up.railway.app"


def fetch_site_bars(source_id=DDDS_SOURCE_ID, *, fetch=None):
    if source_id != DDDS_SOURCE_ID:
        raise ValueError("DDDS_ONLY_RUNNER_CANNOT_EXECUTE_OTHER_STRATEGY")
    api=os.environ.get("INVESTMENT_PUBLIC_API",PUBLIC_API_DEFAULT).rstrip("/")
    url=(api+"/api/public/scripts/"+quote(source_id,safe="")+"/chart?"+
         urlencode({"symbol":"NASDAQ:AMZN","horizon":"2h"}))
    if fetch is None:
        req=Request(url,headers={"Accept":"application/json",
              "User-Agent":"WF02-exact-DDDS-site-chart/1.0"})
        with urlopen(req,timeout=45) as response:
            if response.status!=200:
                raise ValueError("PINNED_DDDS_PUBLIC_CHART_NOT_200")
            document=json.loads(response.read(3_000_000))
    else:
        document=fetch(url)
    if (not isinstance(document,dict) or
        document.get("script_id")!=DDDS_SOURCE_ID or
        document.get("source_hash")!=DDDS_SOURCE_SHA or
        document.get("symbol")!="NASDAQ:AMZN" or
        document.get("horizon")!="2h"):
        raise ValueError("DDDS_SITE_CHART_SOURCE_SYMBOL_OR_TIMEFRAME_CHANGED")
    meta=document.get("market_data") or {}
    if meta.get("fallback_used") is True or not meta.get("provider"):
        raise ValueError("DDDS_SITE_CHART_FALLBACK_OR_PROVIDER_UNKNOWN")
    data=document.get("bars")
    if not isinstance(data,list) or len(data)<300:
        raise ValueError("DDDS_SITE_CHART_LESS_THAN_300_BARS")
    bars=[]
    for entry in data[-300:]:
        if not isinstance(entry,dict):
            raise ValueError("DDDS_SITE_CHART_INVALID_OHLCV")
        bars.append({"time_ms":entry.get("timestamp"),
          **{k:entry.get(k) for k in ("open","high","low","close","volume")}})
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
    if runtime["status"]!="EXACT_SITE_CHART_INPUT_PYTHON_EXECUTED" or runtime["bar_count"]!=300:
        raise ValueError("DDDS_300_BARS_ACTUAL_PYTHON_EXECUTION_NOT_VERIFIED")
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
