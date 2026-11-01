"""Stock-only Pine v5/v6 *supported subset* -> Python chart and TV CSV parity.

Never executes input code. Rejects unsupported constructs instead of inventing parity.
TV chart screenshots/CSV must be user-provided genuine artifacts, not simulated.
"""
import csv
import hashlib
import html
import io
import math
import re
from dataclasses import dataclass

MAX_BARS=5000
MAX_CSV_BYTES=1000000
MAX_PINE_BYTES=60000
CSS_COLORS=("#1c9e7e","#e05d6f")
ASSIGN=re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+?)\s*$")
INPUT=re.compile(r"input\.int\(\s*(\d+)")
SERIES=re.compile(r"ta\.(sma|ema)\(\s*close\s*,\s*([A-Za-z_]\w*|\d+)\s*\)")
CROSS=re.compile(r"ta\.(crossover|crossunder)\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*\)")
ALLOWED_HEAD=("strategy(", "indicator(", "plot(", "plotshape(", "plotchar(", "if ", "strategy.entry(", "strategy.close(")
class UnsupportedPine(ValueError): pass

def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def finite(s, field):
    try:
        v=float(str(s).replace(",",""))
        if math.isfinite(v): return v
    except (ValueError,TypeError): pass
    raise ValueError("INVALID_CSV_NUMBER:"+field)

def read_csv(text):
    if not isinstance(text,str) or not text.strip() or len(text.encode())>MAX_CSV_BYTES:
        raise ValueError("CSV_EMPTY_OR_TOO_LARGE")
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames: raise ValueError("CSV_HEADER_REQUIRED")
    cols={c.strip().lower():c for c in reader.fieldnames if c}
    def col(*opts):
        for v in opts:
            if v in cols:return cols[v]
        return None
    fields={k:col(k) for k in ("open","high","low","close")}
    tcol=col("time","timestamp","date","datetime")
    if any(v is None for v in fields.values()) or not tcol:raise ValueError("TV_CSV_REQUIRES_TIME_OHLC")
    rows=[]
    for r in reader:
        if len(rows)>=MAX_BARS:raise ValueError("MAX_BARS_EXCEEDED")
        if not (r.get(fields["close"]) or "").strip():continue
        bar={k:finite(r.get(v),k) for k,v in fields.items()}
        bar["time"]=str(r[tcol]).strip()
        if not bar["time"]:raise ValueError("EMPTY_TIMESTAMP")
        if bar["low"]>min(bar["open"],bar["close"]) or bar["high"]<max(bar["open"],bar["close"]):
            raise ValueError("INVALID_OHLC_RANGE")
        bar["raw"]=r
        rows.append(bar)
    if len(rows)<12:raise ValueError("MINIMUM_12_CANDLES")
    if len({b["time"] for b in rows})!=len(rows):raise ValueError("DUPLICATE_TIMESTAMPS")
    return rows,reader.fieldnames

def parse_pine(code):
    if not isinstance(code,str) or not code.strip() or len(code.encode())>MAX_PINE_BYTES:
        raise UnsupportedPine("PINE_EMPTY_OR_TOO_LARGE")
    version=re.search(r"(?m)^\s*//@version=(5|6)\s*$",code)
    if not version:raise UnsupportedPine("ONLY_PINE_V5_V6")
    params={}; series={}; signals={}; entries=[]; plots=[]
    last_if=None; declared=False
    for index,original in enumerate(code.splitlines(),1):
        line=original.strip()
        if not line or line.startswith("//"):continue
        if line.startswith("strategy("):
            if declared:raise UnsupportedPine("MULTIPLE_DECLARATIONS")
            declared=True
            if not re.search(r"\boverlay\s*=\s*true\b",line):
                raise UnsupportedPine("ONLY_OVERLAY_STRATEGIES")
            if re.search(r"\b(commission|slippage|calc_on_every_tick|process_orders_on_close|pyramiding)\s*=",line):
                raise UnsupportedPine("ORDER_EXECUTION_SETTINGS_NEED_EXPLICIT_ADAPTER")
            continue
        match=ASSIGN.match(line)
        if match:
            name,expr=match.groups()
            inp=INPUT.fullmatch(expr) or re.fullmatch(r"input\.int\(\s*(\d+)\s*,.*\)",expr)
            if inp:
                params[name]=int(inp.group(1))
                if not 1<=params[name]<=2000:raise UnsupportedPine("INVALID_INPUT_LENGTH")
                continue
            ser=SERIES.fullmatch(expr)
            if ser:
                op,length=ser.groups()
                length=int(length) if length.isdigit() else params.get(length)
                if not length:raise UnsupportedPine("UNKNOWN_SMA_EMA_LENGTH:"+name)
                series[name]=(op,length);continue
            cross=CROSS.fullmatch(expr)
            if cross:
                op,left,right=cross.groups()
                if left not in series or right not in series:raise UnsupportedPine("UNKNOWN_CROSS_SERIES")
                signals[name]=(op,left,right);continue
            raise UnsupportedPine(f"UNSUPPORTED_ASSIGNMENT_LINE_{index}")
        if line.startswith("if "):
            last_if=line[3:].strip().strip("() ")
            if last_if not in signals:raise UnsupportedPine(f"UNSUPPORTED_IF_LINE_{index}")
            continue
        if line.startswith("strategy.entry(") or line.startswith("strategy.close("):
            if not last_if:raise UnsupportedPine(f"ENTRY_WITHOUT_IF_LINE_{index}")
            if line.startswith("strategy.entry("):
                side=re.search(r"strategy\.(long|short)",line)
                if not side:raise UnsupportedPine("ENTRY_SIDE_REQUIRED")
                entries.append((last_if,side.group(1)))
            else:
                entries.append((last_if,"close"))
            continue
        if line.startswith(("plot(", "plotshape(","plotchar(")):
            p=re.search(r"^plot(?:shape|char)?\(\s*([A-Za-z_]\w*)",line)
            if not p or p.group(1) not in (series|signals):
                raise UnsupportedPine(f"UNSUPPORTED_PLOT_LINE_{index}")
            plots.append(p.group(1));continue
        raise UnsupportedPine(f"UNSUPPORTED_PINE_LINE_{index}")
    if not declared or not series or not signals or not entries:
        raise UnsupportedPine("REQUIRES_STRATEGY_MA_CROSS_AND_ENTRY")
    if len(series)>4 or len(signals)>4:raise UnsupportedPine("TOO_MANY_SERIES")
    # The supported subset is unambiguously described; it is NOT a full compiler.
    return {"pine_version":int(version.group(1)),"inputs":params,
            "series":series,"conditions":signals,"entries":entries,"plots":plots,
            "supported_subset":"PINE_V5_V6_CLOSE_SMA_EMA_CROSS_STRATEGY"}

def moving_average(close,kind,n):
    arr=[];prev=None
    for i,v in enumerate(close):
        if kind=="sma":
            arr.append(sum(close[i-n+1:i+1])/n if i>=n-1 else None)
        else:
            prev=v if prev is None else (v*2/(n+1)+prev*(1-2/(n+1)))
            arr.append(prev)
    return arr

def run_python(bars,spec):
    close=[b["close"] for b in bars]
    series={key:moving_average(close,op,length) for key,(op,length) in spec["series"].items()}
    conditions={}
    for key,(op,left,right) in spec["conditions"].items():
        a,b=series[left],series[right];values=[False]
        for i in range(1,len(close)):
            if any(v is None for v in (a[i],b[i],a[i-1],b[i-1])):
                values.append(False)
            elif op=="crossover": values.append(a[i]>b[i] and a[i-1]<=b[i-1])
            else: values.append(a[i]<b[i] and a[i-1]>=b[i-1])
        conditions[key]=values
    trades=[]
    for i in range(len(close)):
        for sig,side in spec["entries"]:
            if conditions[sig][i]:
                trades.append({"bar_index":i,"time":bars[i]["time"],"direction":side,
                               "signal_price":close[i],
                               "assumed_fill_time":bars[i+1]["time"] if i+1<len(close) else None,
                               "assumed_fill_price":bars[i+1]["open"] if i+1<len(close) else None})
    return series,conditions,trades

def numeric_compare(bars,series,conditions,columns):
    columns=columns or {}
    if not isinstance(columns,dict):raise ValueError("COLUMN_MAPPING_OBJECT_REQUIRED")
    headers=set(bars[0]["raw"])
    comparison=[]
    all_required=True;all_match=True
    for key,values in {**series,**conditions}.items():
        mapped=columns.get(key)
        if mapped not in headers:
            all_required=False
            comparison.append({"variable":key,"column":mapped,"status":"MISSING_TV_EXPORT",
                               "mismatch_bars":[]});continue
        mismatch=[];compared=0
        for i,(b,actual) in enumerate(zip(bars,values)):
            reference=b["raw"].get(mapped,"")
            if reference is None or str(reference).strip() in ("","NaN","na"):
                if actual is not None and actual is not False:
                    mismatch.append({"bar_index":i,"time":b["time"],"expected":None,"python":actual})
                continue
            try:expected=float(reference)
            except (ValueError,TypeError):
                mismatch.append({"bar_index":i,"time":b["time"],"expected":reference,"python":actual})
                continue
            if actual is None:
                mismatch.append({"bar_index":i,"time":b["time"],"expected":expected,"python":None})
            else:
                observed=float(actual)
                if not math.isclose(expected,observed,rel_tol=1e-6,abs_tol=1e-6):
                    mismatch.append({"bar_index":i,"time":b["time"],"expected":expected,"python":observed})
            compared+=1
        ok=not mismatch and compared>0
        all_match=all_match and ok
        comparison.append({"variable":key,"column":mapped,
            "status":"MATCH" if ok else "MISMATCH",
            "compared_bars":compared,"mismatch_count":len(mismatch),
            "mismatch_bars":mismatch[:8]})
    return comparison,all_required,all_match

def render_svg(bars,series,conditions,title="Python strategy chart"):
    # Returned SVG is rendered by Python, not by JS / TradingView.
    n=min(180,len(bars));start=len(bars)-n;part=bars[start:]
    width=1100;height=470;left=62;right=18;top=35;bottom=46
    ymin=min(b["low"] for b in part); ymax=max(b["high"] for b in part)
    for v in series.values():
        for x in v[start:]:
            if x is not None:ymin=min(ymin,x);ymax=max(ymax,x)
    pad=max((ymax-ymin)*.07,.01);ymin-=pad;ymax+=pad
    pw=width-left-right;ph=height-top-bottom
    x=lambda i:left+(i+.5)*pw/n
    y=lambda v:top+(ymax-v)/(ymax-ymin)*ph
    esc=lambda z:html.escape(str(z),quote=True)
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
         '<rect width="100%" height="100%" fill="#0d1626"/>',
         f'<text x="18" y="20" font-size="14" fill="#cbd5e1">{esc(title)}</text>']
    for i in range(6):
        yy=top+i*ph/5
        price=ymax-(ymax-ymin)*i/5
        out.append(f'<path d="M{left} {yy:.1f} H{width-right}" stroke="#223147"/><text x="5" y="{yy+4:.1f}" font-size="11" fill="#93a3b9">{price:.4g}</text>')
    for j,bar in enumerate(part):
        xx=x(j);green=bar["close"]>=bar["open"];color=CSS_COLORS[0 if green else 1]
        out.append(f'<path d="M{xx:.2f} {y(bar["low"]):.2f} V{y(bar["high"]):.2f}" stroke="{color}" stroke-width="1.3"/>')
        topbar=min(y(bar["open"]),y(bar["close"]));body=max(abs(y(bar["open"])-y(bar["close"])),1.2)
        out.append(f'<rect x="{xx-2:.2f}" y="{topbar:.2f}" width="4" height="{body:.2f}" fill="{color}"/>')
    palette=["#51a1ff","#f5b74b","#d782ed","#6ad1c4"]
    for j,(key,values) in enumerate(series.items()):
        segments=[];current=[]
        for i in range(start,len(bars)):
            value=values[i]
            if value is None:
                if current:segments.append(current);current=[]
            else:current.append(f'{x(i-start):.2f},{y(value):.2f}')
        if current:segments.append(current)
        for segment in segments:
            out.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{palette[j%4]}" stroke-width="2"/>')
        out.append(f'<text x="{left+j*170}" y="{height-12}" fill="{palette[j%4]}" font-size="12">{esc(key)}</text>')
    for key,vals in conditions.items():
        for i in range(start,len(bars)):
            if not vals[i]:continue
            xx=x(i-start); bullish="crossunder" not in key.lower()
            # Shape direction is based on the actual condition operation, not its name.
            bullish=key and True
            tip=y(bars[i]["low"])-8
            if any(s[0]==key and s[1]=="short" for s in []):bullish=False
            if bullish:
                out.append(f'<path d="M{xx:.2f} {tip:.2f} l-6 9 h12 Z" fill="#2de4a7"/>')
            else:
                out.append(f'<path d="M{xx:.2f} {tip:.2f} l-6 -9 h12 Z" fill="#ff6f7a"/>')
    for i in range(0,n,max(1,n//7)):
        out.append(f'<text x="{x(i):.2f}" y="{height-27}" text-anchor="middle" font-size="10" fill="#9aaec6">{esc(part[i]["time"][:16])}</text>')
    out.append('</svg>')
    return "".join(out)

def analyze(pine_code,csv_text,column_mapping=None,title="Python re-render"):
    spec=parse_pine(pine_code)
    bars,headers=read_csv(csv_text)
    series,signals,trades=run_python(bars,spec)
    comparisons,complete,match=numeric_compare(bars,series,signals,column_mapping)
    status=("REFERENCE_COLUMNS_REQUIRED" if not complete else
           "NUMERIC_MISMATCH" if not match else "NUMERIC_MATCH_VISUAL_REVIEW_REQUIRED")
    return {"status":status,"pine_sha256":sha(pine_code),"csv_sha256":sha(csv_text),
        "bars":len(bars),"csv_headers":headers,"strategy":spec,
        "comparison":comparisons,"trades":trades[:500],"trade_count":len(trades),
        "numeric_match":bool(complete and match),
        "svg":render_svg(bars,series,signals,title),"source":"PYTHON_STRICT_SUPPORTED_SUBSET",
        "baseline_source":"USER_SUPPLIED_TV_CSV_NOT_AUTOMATICALLY_AUTHENTICATED",
        "image_match":"NOT_AUTOMATICALLY_VERIFIED"}
