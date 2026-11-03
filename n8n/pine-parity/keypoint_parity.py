"""Important-point numerical comparison for two REAL exported chart series.

Never compare a published TradingView screenshot's pixels with mismatched
OHLCV periods, nor treat a different Python engine as PyneCore output.
Trade timestamps, OHLC, orders and plotted levels are checked separately.
"""
import csv,io,math,datetime
from collections import Counter

IGNORED={"time","timestamp","date","datetime","volume"}
OHLC=("open","high","low","close")
EVENT_FIELDS=("signal","event","order","order_id","action","direction","entry","exit")
MAX_ROWS=150000

class KeypointError(ValueError):
    pass

def _time(value):
    value=str(value or "").strip()
    if not value:raise KeypointError("CSV_MISSING_TIMESTAMP")
    try:
        n=float(value)
        if not math.isfinite(n):raise ValueError()
        return int(n if abs(n)>10**11 else n*1000)
    except ValueError:
        try:
            d=datetime.datetime.fromisoformat(value.replace("Z","+00:00"))
            if d.tzinfo is None:raise KeypointError("CSV_TIMESTAMP_MUST_INCLUDE_TIMEZONE")
            return int(d.timestamp()*1000)
        except (ValueError,OverflowError):
            raise KeypointError("CSV_TIMESTAMP_UNRECOGNIZED") from None

def _read(text):
    if not isinstance(text,str) or len(text)>14_000_000:
        raise KeypointError("CSV_DATA_TOO_LARGE")
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:raise KeypointError("CSV_EMPTY_HEADERS")
    fields={f.lower().strip():f for f in reader.fieldnames if f}
    time_key=next((fields[x] for x in ("time","timestamp","datetime","date") if x in fields),None)
    if not time_key:raise KeypointError("CSV_MISSING_TIME_COLUMN")
    if not all(key in fields for key in OHLC):
        raise KeypointError("CSV_MISSING_REQUIRED_OHLC")
    out={}
    for idx,row in enumerate(reader):
        if idx>=MAX_ROWS:raise KeypointError("CSV_TOO_MANY_ROWS")
        if not row or not any(str(x or "").strip() for x in row.values()):continue
        stamp=_time(row[time_key])
        if stamp in out:raise KeypointError("CSV_DUPLICATE_BAR_TIMESTAMP")
        normalized={k:str(row.get(orig) or "").strip() for k,orig in fields.items()}
        out[stamp]=normalized
    if not out:raise KeypointError("CSV_EMPTY_ROWS")
    return out,set(fields)

def _number(row,key):
    value=row.get(key,"")
    if not value or value.lower() in ("na","nan","null","none"):return None
    try:n=float(value)
    except ValueError:raise KeypointError("CSV_NOT_NUMERIC_IN_"+key.upper()) from None
    return n if math.isfinite(n) else None

def _equal(a,b,absolute,relative):
    if a is None or b is None:return a is None and b is None
    return math.isclose(a,b,abs_tol=absolute,rel_tol=relative)

def compare_keypoints(tv_csv,py_csv,*,absolute=0.00001,relative=0.00001):
    """Returns important mismatches; never a numeric VERIFIED approval.

    Inputs must be genuine TradingView and PyneCore exports supplied by caller.
    Neither source is authenticated by this pure function.
    """
    try:
        tv,tf=_read(tv_csv);py,pf=_read(py_csv)
        if not (0<=absolute<=1 and 0<=relative<=1):raise KeypointError("INVALID_TOLERANCE")
        tv_time=set(tv);py_time=set(py)
        shared=sorted(tv_time&py_time)
        if len(shared)!=len(tv) or len(shared)!=len(py):
            return {"status":"BLOCKED_OHLC_TIMESET_MISMATCH",
                "tv_bars":len(tv),"python_bars":len(py),"aligned_bars":len(shared),
                "missing_tv_bars":len(py_time-tv_time),
                "missing_python_bars":len(tv_time-py_time),
                "numeric_match":False,"keypoints":[],"verified":False}
        plots=sorted((tf&pf)-IGNORED-set(OHLC)-set(EVENT_FIELDS))
        events=sorted((tf&pf)&set(EVENT_FIELDS))
        focus=[];counts=Counter()
        for stamp in shared:
            t=tv[stamp];p=py[stamp]
            for name in (*OHLC,*plots):
                x,y=_number(t,name),_number(p,name)
                if not _equal(x,y,absolute,relative):
                    group="OHLC" if name in OHLC else "PLOT"
                    counts[group]+=1
                    focus.append({"timestamp_ms":stamp,"group":group,
                        "field":name,"tradingview":x,"pynecore":y,
                        "absolute_delta":abs(x-y) if x is not None and y is not None else None})
            for name in events:
                if t.get(name,"").lower()!=p.get(name,"").lower():
                    counts["ORDER_OR_SIGNAL"]+=1
                    focus.append({"timestamp_ms":stamp,"group":"ORDER_OR_SIGNAL",
                        "field":name,"tradingview":t.get(name),
                        "pynecore":p.get(name),"absolute_delta":None})
        # Event discrepancies are more actionable than ordinary plot levels.
        order={"ORDER_OR_SIGNAL":0,"OHLC":1,"PLOT":2}
        focus.sort(key=lambda x:(order[x["group"]],x["timestamp_ms"],x["field"]))
        result={"status":"KEYPOINTS_DIFFER" if focus else
                   "KEYPOINTS_MATCH_REVIEW_REQUIRED" if plots and events else
                   "KEYPOINTS_PARTIAL_NO_ORDER_OR_PLOT_EXPORT",
                "tv_bars":len(tv),"python_bars":len(py),
                "aligned_bars":len(shared),
                "comparison_columns":{"ohlc":list(OHLC),"plots":plots,"orders_or_signals":events},
                "mismatch_counts":dict(counts),"mismatch_total":len(focus),
                "keypoints":focus[:80],"keypoints_truncated":len(focus)>80,
                "absolute_tolerance":absolute,"relative_tolerance":relative,
                "numeric_match":not focus and bool(plots and events),
                "verified":False,"provenance":"CALLER_SUPPLIED_UNAUTHENTICATED_EXPORTS"}
        return result
    except KeypointError as exc:
        return {"status":str(exc),"numeric_match":False,"verified":False,
            "keypoints":[]}
