"""Child process ONLY: run one immutable, SHA-verified DDDS PYNE Python artifact.

This file is invoked via python -I by the parent worker. The HTTP server
NEVER imports generated user Python. No external services or broker actions.
All input bars must have been validated in parent; child still validates shape.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import numpy as np

PINNED_GENERATED_PYTHON_SHA="ef27e69cbb71bc101431a2f9f71783c37f1f8094a7a77e080032ca3bbd7994a1"

def finite(obj):
    try:
        value=float(obj)
        return value if math.isfinite(value) else None
    except (TypeError,ValueError,OverflowError):
        return None

def value(obj):
    if isinstance(obj,(str,int,float,bool)) or obj is None:
        return obj
    if hasattr(obj,"item"):
        return value(obj.item())
    if isinstance(obj,dict):
        return {str(k):value(v) for k,v in list(obj.items())[:35]}
    if isinstance(obj,(tuple,list)):
        return [value(x) for x in obj[:35]]
    return str(obj)[:150]

def main():
    if len(sys.argv)!=2:
        raise RuntimeError("PINNED_DDDS_CODE_PATH_REQUIRED")
    path=Path(sys.argv[1]).resolve()
    code=path.read_bytes()
    digest=hashlib.sha256(code).hexdigest()
    if digest!=PINNED_GENERATED_PYTHON_SHA:
        raise RuntimeError("EXACT_DDDS_FREE_PYNE_CODE_SHA_MISMATCH")
    payload=json.load(sys.stdin)
    rows=payload.get("bars")
    if not isinstance(rows,list) or not 40<=len(rows)<=300:
        raise ValueError("BOUNDED_AMZN_BARS_REQUIRED")
    if payload.get("python_sha256")!=digest:
        raise ValueError("PYTHON_SHA_REQUIRED")
    fields=["open","high","low","close","volume"]
    matrix={key:[] for key in fields}
    times=[]
    for row in rows:
        if not isinstance(row,dict) or isinstance(row.get("time_ms"),bool):
            raise ValueError("OHLCV_OBJECT_REQUIRED")
        ts=row.get("time_ms")
        if type(ts)!=int or (times and times[-1]>=ts):
            raise ValueError("TIME_NOT_MONOTONIC")
        times.append(ts)
        for key in fields:
            number=finite(row.get(key))
            if number is None or (key!="volume" and number<=0) or number<0:
                raise ValueError("INVALID_OHLCV_"+key)
            matrix[key].append(number)
    spec=importlib.util.spec_from_file_location("exact_ddds_free_pyne_generated",str(path))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result=module.execute_script_compiled(
        *(np.asarray(matrix[key],dtype=np.float64) for key in fields),
        np.asarray(times,dtype=np.float64)
    )
    if not isinstance(result,dict):
        raise RuntimeError("FREE_PYNE_BAD_OUTPUT")
    plots={}
    for key in ("Decycler","Price anchor","Gradient","Lower band","Upper band","Stop","Target"):
        vector=result.get(key)
        if vector is None or len(vector)!=len(rows):
            raise RuntimeError("MISSING_DDDS_PLOT_"+key)
        plots[key]=[finite(z) for z in vector]
    if not any(z is not None for z in plots["Decycler"]):
        raise RuntimeError("NO_NUMERIC_DDDS_DECYCLER")
    events=result.get("__events")
    if not isinstance(events,list) or len(events)>2000:
        raise RuntimeError("TRADE_EVENTS_UNEXPECTED")
    output={
        "status":"EXACT_DDDS_FREE_PYNE_EXECUTED_ON_REAL_AMZN_120_BARS",
        "pine_sha256":"5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507",
        "python_sha256":digest,"bars_executed":len(rows),
        "plots":plots,
        "trade_event_count":len(events),
        "trade_events":[value(x) for x in events[:100]],
        "trade_events_truncated":len(events)>100,
        "reported_pyne_equity":finite(result.get("__equity")),
        "reported_pyne_netprofit":finite(result.get("__netprofit")),
        "reported_position_size":finite(result.get("__position_size")),
        "tv_strategy_parity_verified":False,
        "history_2016_2026_complete":False,
        "live_orders_enabled":False
    }
    print(json.dumps(output,allow_nan=False,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
