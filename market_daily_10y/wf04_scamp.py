"""WF-04: real SCAMP AB-join on independently collected, verified 10Y 1D pool.

No live downloads here. Only exact as-of, SHA-verified Parquet from Store.
Correlation motifs are descriptive similarities, NOT trade signals or backtests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import date, datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

from .collector import Store
from .pool_reader import eligible_manifest, instrument_from_row


def prepare_series(shared, feature="log_returns"):
    """Map each shared exchange-session date to a non-filled float64 observation."""
    if feature not in ("log_returns", "close"):
        raise ValueError("UNSUPPORTED_SCAMP_FEATURE")
    dates = shared["date"].tolist()
    left = shared["left_close"].to_numpy(dtype=np.float64)
    right = shared["right_close"].to_numpy(dtype=np.float64)
    if (not len(dates) or not shared["date"].is_unique or
            any(dates[i] >= dates[i+1] for i in range(len(dates)-1))):
        raise ValueError("SCAMP_ALIGNED_DATES_REQUIRED")
    if not (np.isfinite(left).all() and np.isfinite(right).all() and
            (left > 0).all() and (right > 0).all()):
        raise ValueError("SCAMP_NONPOSITIVE_OR_INVALID_CLOSE")
    if feature == "log_returns":
        left = np.diff(np.log(left))
        right = np.diff(np.log(right))
        dates = dates[1:]
    if not (len(dates) and len(left) == len(right) == len(dates)):
        raise ValueError("SCAMP_EMPTY_FEATURE_SERIES")
    return np.ascontiguousarray(left), np.ascontiguousarray(right), dates


def scamp_ab_matches(series_a, series_b, dates, window,
                     threshold=0.0, top=5, threads=2, backend=None):
    """Run actual pyscamp 1NN AB join and verify reported scores with NumPy."""
    if not isinstance(window, int) or not 8 <= window <= len(dates)-2:
        raise ValueError("SCAMP_INVALID_SUBSEQUENCE_LENGTH")
    if len(series_a) != len(dates) or len(series_b) != len(dates):
        raise ValueError("SCAMP_INPUT_DIMENSION_MISMATCH")
    if not -1 <= threshold <= 1 or not 1 <= top <= 50 or not 1 <= threads <= 16:
        raise ValueError("SCAMP_INVALID_SEARCH_PARAMETERS")
    if backend is None:
        try:
            import pyscamp as backend
        except ImportError as exc:
            raise RuntimeError("PYSCAMP_NOT_INSTALLED") from exc
    # Default to CPU even when a GPU exists; avoid fighting with ingestion cron.
    profile, indices = backend.abjoin(series_a, series_b, window,
                                       pearson=True, threads=threads, gpus=[])
    profile = np.asarray(profile, dtype=np.float64).reshape(-1)
    indices = np.asarray(indices).reshape(-1)
    expected = len(dates)-window+1
    if len(profile) != expected or len(indices) != expected:
        raise RuntimeError("SCAMP_MATRIX_PROFILE_SHAPE_MISMATCH")
    candidates = []
    for i, (corr, raw_j) in enumerate(zip(profile, indices)):
        if not np.isfinite(corr) or corr < threshold:
            continue
        j = int(raw_j)
        if j < 0 or j > len(series_b)-window:
            continue
        a = series_a[i:i+window]
        b = series_b[j:j+window]
        if np.std(a) < 1e-12 or np.std(b) < 1e-12:
            continue
        np_corr = float(np.corrcoef(a, b)[0, 1])
        if not np.isfinite(np_corr):
            continue
        if abs(np_corr - corr) > 0.02:
            raise RuntimeError("SCAMP_SCORE_NOT_NUMPY_PEARSON_EQUIVALENT")
        # Correlation is a shape similarity metric, not a forecast probability.
        candidates.append((float(np_corr), i, j))
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    selected=[]
    for corr,i,j in candidates:
        # Avoid dozens of nearly-identical overlapping motifs masquerading as
        # independent hits. Both series windows must be disjoint.
        if any(abs(i-prev["left_index"])<window or
               abs(j-prev["right_index"])<window for prev in selected):
            continue
        selected.append({
            "correlation":round(corr, 7),
            "left_index":i, "right_index":j,
            "left_start":dates[i], "left_end":dates[i+window-1],
            "right_start":dates[j], "right_end":dates[j+window-1],
            "same_calendar_window":i==j,
        })
        if len(selected)>=top:
            break
    return selected


def _installed_scamp_version():
    for package in ("pyscamp", "pyscamp-cpu", "pyscamp-gpu"):
        try:
            return version(package)
        except PackageNotFoundError:
            continue
    import pyscamp
    return str(getattr(pyscamp, "__version__", "UNKNOWN"))


def run_wf04(store, left_key, right_key, asof, *,
             window=60, feature="log_returns", threshold=0.0, top=5,
             threads=2, backend=None):
    """Full 10Y snapshot eligibility and per-file content hash is mandatory."""
    manifest = eligible_manifest(store, asof, verify_digest=True,
                                 only_keys={left_key, right_key})
    lookup = {x["key"]:x for x in manifest["instruments"]}
    if left_key not in lookup or right_key not in lookup:
        raise ValueError("WF04_SOURCE_NOT_VERIFIED_AT_EXACT_ASOF")
    if left_key == right_key:
        raise ValueError("WF04_REQUIRES_DIFFERENT_INSTRUMENTS")
    inst_a = instrument_from_row(lookup[left_key])
    inst_b = instrument_from_row(lookup[right_key])
    shared, alignment = store.align(inst_a, inst_b, asof=asof)
    left, right, dates = prepare_series(shared,feature=feature)
    hits = scamp_ab_matches(left,right,dates,window,
                            threshold=threshold,top=top,threads=threads,
                            backend=backend)
    return {
        "status":"MATCHES_FOUND" if hits else "NO_MATCHES_ABOVE_THRESHOLD",
        "workflow":"WF-04", "engine":"pyscamp.abjoin",
        "engine_version":_installed_scamp_version() if backend is None else "injected_test_backend",
        "compute_device":"CPU", "thread_limit":threads,
        "left":left_key, "right":right_key,
        "left_parquet_sha256":lookup[left_key]["sha256"],
        "right_parquet_sha256":lookup[right_key]["sha256"],
        "asof_end_exclusive":str(asof),
        "window_start":manifest["window_start"],
        "timeframe":"1d",
        "feature":feature, "motif_window_trading_days":window,
        "min_pearson_correlation":threshold,
        "aligned_common_trading_days":alignment["common_dates"],
        "feature_points":len(dates),
        "filled_missing_sessions":False, "downloaded_bars_in_wf04":False,
        "evaluation_is_predictive_backtest":False,
        "search_method":"AB_JOIN_1NN_BEST_MATCH_PER_LEFT_SUBSEQUENCE",
        "no_overlap_motif_selection":True,
        "results":hits,
    }


def _atomic_json(path, data):
    dest=Path(path)
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".wf04-",suffix=".json",dir=dest.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            json.dump(data,handle,ensure_ascii=False,indent=2,allow_nan=False)
        os.replace(tmp,dest)
    finally:
        Path(tmp).unlink(missing_ok=True)


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=os.getenv("DAILY_POOL_ROOT","/data/market_daily_10y"))
    p.add_argument("--asof",type=date.fromisoformat,required=True)
    p.add_argument("--left",required=True)
    p.add_argument("--right",required=True)
    p.add_argument("--window",type=int,default=60)
    p.add_argument("--feature",choices=("log_returns","close"),default="log_returns")
    p.add_argument("--threshold",type=float,default=0.0)
    p.add_argument("--top",type=int,default=5)
    p.add_argument("--threads",type=int,default=2)
    p.add_argument("--output",required=True)
    args=p.parse_args(argv)
    result=run_wf04(Store(args.root),args.left,args.right,args.asof,
                    window=args.window,feature=args.feature,
                    threshold=args.threshold,top=args.top,threads=args.threads)
    _atomic_json(args.output,result)
    print(json.dumps({
        "status":result["status"],"engine":result["engine"],
        "asof_end_exclusive":result["asof_end_exclusive"],
        "aligned_common_trading_days":result["aligned_common_trading_days"],
        "motifs":len(result["results"]),
        "output":str(args.output),
    },ensure_ascii=False))


if __name__=="__main__":
    main()
