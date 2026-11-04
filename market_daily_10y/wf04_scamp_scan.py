"""WF-04 one-to-many SCAMP screening over only already-verified local 10Y data.

This command never downloads bars or spawns trading agents. It is an explicit,
bounded screening batch. Nondistributable Yahoo OHLC is never exported.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date

from .collector import Store, ten_year_window
from .wf04_scamp import _atomic_json, run_wf04


def scan_candidates(store, anchor, candidates, asof, *, window=60,
                    feature="log_returns", threshold=0.0, top=3,
                    threads=2, batch_limit=20):
    candidates=list(dict.fromkeys(candidates))
    if not 1 <= len(candidates) <= batch_limit <= 100:
        raise ValueError("WF04_BATCH_OUTSIDE_ALLOWED_RANGE")
    if anchor in candidates:
        raise ValueError("WF04_BATCH_ANCHOR_IS_CANDIDATE")
    results=[]
    errors=[]
    for candidate in candidates:
        try:
            result=run_wf04(store, anchor, candidate, asof,
                            window=window,feature=feature,
                            threshold=threshold,top=top,threads=threads)
            ranked=result["results"]
            results.append({
                "candidate_key":candidate,
                "status":result["status"],
                "best_correlation":ranked[0]["correlation"] if ranked else None,
                "matched_motif_count":len(ranked),
                "common_trading_days":result["aligned_common_trading_days"],
                "left_parquet_sha256":result["left_parquet_sha256"],
                "right_parquet_sha256":result["right_parquet_sha256"],
                "matches":ranked,
            })
        except (ValueError, RuntimeError, OSError) as exc:
            errors.append({
                "candidate_key":candidate,
                "reason_code":str(exc).split(":")[0][:120],
                "error_type":type(exc).__name__,
            })
    results.sort(key=lambda r: (r["best_correlation"] is None,
                -float(r["best_correlation"]) if r["best_correlation"] is not None else 0.0,
                r["candidate_key"]))
    start,end=ten_year_window(asof)
    return {
        "workflow":"WF-04","engine":"pyscamp.abjoin",
        "source":"EXISTING_LOCAL_VERIFIED_10Y_PARQUET_ONLY",
        "anchor_key":anchor,"asof_end_exclusive":str(asof),
        "window_start":str(start),"timeframe":"1d",
        "feature":feature,"motif_window_trading_days":window,
        "attempted":len(candidates),"scored":len(results),
        "blocked":len(errors),
        "blocked_candidate_count":len(errors),
        "trading_enabled":False,
        "ranking_is_forecast":False,
        "ranked":results,"excluded":errors,
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=os.getenv("DAILY_POOL_ROOT","/data/market_daily_10y"))
    p.add_argument("--asof",required=True,type=date.fromisoformat)
    p.add_argument("--anchor",required=True)
    p.add_argument("--candidate",action="append",required=True)
    p.add_argument("--window",type=int,default=60)
    p.add_argument("--feature",choices=["log_returns","close"],default="log_returns")
    p.add_argument("--threshold",type=float,default=0.0)
    p.add_argument("--top",type=int,default=3)
    p.add_argument("--threads",type=int,default=2)
    p.add_argument("--output",required=True)
    args=p.parse_args(argv)
    payload=scan_candidates(Store(args.root),args.anchor,args.candidate,args.asof,
                            window=args.window,feature=args.feature,
                            threshold=args.threshold,top=args.top,
                            threads=args.threads)
    _atomic_json(args.output,payload)
    print(json.dumps({
        "status":"BATCH_FINISHED" if payload["blocked"]==0 else "BATCH_PARTIAL",
        "attempted":payload["attempted"],"scored":payload["scored"],
        "blocked":payload["blocked"],"output":args.output,
    },ensure_ascii=False))


if __name__=="__main__":
    main()
