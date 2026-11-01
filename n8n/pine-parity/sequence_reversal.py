"""Restricted converter for Pine RSI-confirmed reversal-run strategies.

This is not a general Pine interpreter. It recognizes a concrete, checked
collection of expressions and emits Python for the RSI + candle-sequence
signals. Trade *fills* are explicitly approximate, never TradingView parity.
Input Pine is inspected as data and is never executed.
"""
import inspect
import re
import math

class UnsupportedSequencePine(ValueError):
    pass

SCOPE="PINE_V6_RSI_REVERSAL_RUN_SIGNAL"
def _compact(text):
    # Only for exact structural checks; no Pine input is executed.
    cleaned=[]
    for raw in text.splitlines():
        line=raw.split("//",1)[0].strip()
        if line:cleaned.append(line)
    return re.sub(r"\s+","", "\n".join(cleaned))

def _get_input(code,name,kind):
    kinds={"int":r"(-?\d+)","float":r"(-?\d+(?:\.\d+)?)",
           "bool":r"(true|false)","string":r'("[^"\n]*")'}
    pattern=(r"(?m)^\s*"+re.escape(name)+r"\s*=\s*input\."+kind+
             r"\s*\(\s*"+kinds[kind]+r"\s*(?:,|\))")
    match=re.search(pattern,code)
    if not match:raise UnsupportedSequencePine("INPUT_NOT_SUPPORTED:"+name)
    value=match.group(1)
    if kind=="bool":return value=="true"
    if kind=="string":return value[1:-1]
    return int(value) if kind=="int" else float(value)

# Each expression here influences the computed signal or order.
# If the Pine logic changes, do not silently reuse the same Python.
ESSENTIAL=(
    "rsiVal=ta.rsi(close,rsiLen)",
    "rsiRising=rsiVal>rsiVal[1]",
    "rsiFalling=rsiVal<rsiVal[1]",
    "rsiOkLong=notuseRsiFilteror(rsiVal>rsiMinLongandrsiRising)",
    "rsiOkShort=notuseRsiFilteror(rsiVal<rsiMaxShortandrsiFalling)",
    "reversalWasDown=close[runLength]<open[runLength]",
    "reversalWasUp=close[runLength]>open[runLength]",
    "boolrunIsBullish=true",
    "boolrunIsBearish=true",
    "ifclose[i]<=open[i]runIsBullish:=false",
    "iflow[i]<=low[runLength]runIsBullish:=false",
    "floorClose=close[i+1]*(1-tolerancePct/100)",
    "ifclose[i]<=floorCloserunIsBullish:=false",
    "ifclose[i]>=open[i]runIsBearish:=false",
    "ifhigh[i]>=high[runLength]runIsBearish:=false",
    "ceilClose=close[i+1]*(1+tolerancePct/100)",
    "ifclose[i]>=ceilCloserunIsBearish:=false",
    "longSetup=reversalWasDownandrunIsBullishandrsiOkLong",
    "shortSetup=reversalWasUpandrunIsBearishandrsiOkShort",
    "ifenableLongTradesandlongSetupandstrategy.position_size==0",
    "stopLossPrice:=low[runLength]",
    "riskPts=close-stopLossPrice",
    "takeProfitPrice:=close+riskPts*rrMultiple",
    'strategy.entry("Long",strategy.long)',
    "ifenableShortTradesandshortSetupandstrategy.position_size==0",
    "stopLossPrice:=high[runLength]",
    "riskPts=stopLossPrice-close",
    "takeProfitPrice:=close-riskPts*rrMultiple",
    'strategy.entry("Short",strategy.short)',
    'strategy.exit("LongExit",from_entry="Long",stop=stopLossPrice,limit=takeProfitPrice)',
    'strategy.exit("ShortExit",from_entry="Short",stop=stopLossPrice,limit=takeProfitPrice)',
)
def parse_sequence_pine(code):
    if not isinstance(code,str) or not code.strip() or len(code.encode("utf-8"))>60000:
        raise UnsupportedSequencePine("PINE_SOURCE_REQUIRED")
    if not re.search(r"(?m)^\s*//@version=6\s*$",code):
        raise UnsupportedSequencePine("SEQUENCE_REQUIRES_PINE_V6")
    condensed=_compact(code)
    if not re.search(r"(?m)^\s*strategy\s*\(",code):
        raise UnsupportedSequencePine("STRATEGY_DECLARATION_REQUIRED")
    if condensed.count("fori=0torunLength-1")!=2:
        raise UnsupportedSequencePine("UNSUPPORTED_CANDLE_LOOP")
    for expr in ESSENTIAL:
        if expr not in condensed:
            raise UnsupportedSequencePine("SEQUENCE_RULE_CHANGED:"+expr[:75])
    # Explicitly reject unmodeled order actions and duplicate trading calls.
    for command,count in (("strategy.entry(",2),("strategy.exit(",2),
                          ("strategy.close(",0),("strategy.cancel(",0),
                          ("strategy.order(",0),("strategy.close_all(",0)):
        if condensed.count(command)!=count:
            raise UnsupportedSequencePine("UNSUPPORTED_ORDER_BEHAVIOR:"+command)
    params={
        "run_length":_get_input(code,"runLength","int"),
        "tolerance_pct":_get_input(code,"tolerancePct","float"),
        "use_rsi_filter":_get_input(code,"useRsiFilter","bool"),
        "rsi_length":_get_input(code,"rsiLen","int"),
        "rsi_min_long":_get_input(code,"rsiMinLong","int"),
        "rsi_max_short":_get_input(code,"rsiMaxShort","int"),
        "enable_long":_get_input(code,"enableLongTrades","bool"),
        "enable_short":_get_input(code,"enableShortTrades","bool"),
        "reward_choice":_get_input(code,"takeProfitR","string")
    }
    if not 2<=params["run_length"]<=5 or not 2<=params["rsi_length"]<=250:
        raise UnsupportedSequencePine("UNSUPPORTED_INPUT_RANGE")
    if not 0<=params["tolerance_pct"]<=25 or not 0<=params["rsi_min_long"]<=100 or not 0<=params["rsi_max_short"]<=100:
        raise UnsupportedSequencePine("UNSUPPORTED_INPUT_RANGE")
    # Read actual reward switch arms rather than hardcode 1.5R.
    arms=dict(re.findall(r'"(\d+(?:\.\d+)?R)"\s*=>\s*(\d+(?:\.\d+)?)',code))
    allowed={"0.5R":0.5,"1R":1.0,"1.5R":1.5,"2R":2.0}
    if set(arms)!=set(allowed) or any(abs(float(arms[k])-v)>1e-12 for k,v in allowed.items()):
        raise UnsupportedSequencePine("UNSUPPORTED_REWARD_SWITCH")
    if params["reward_choice"] not in arms:
        raise UnsupportedSequencePine("REWARD_CHOICE_NOT_FOUND")
    params["reward_multiple"]=float(arms[params["reward_choice"]])
    return {"pine_version":6,"supported_subset":SCOPE,
            "inputs":params,"signal_basis":"CLOSED_BAR",
            "order_fills":"ILLUSTRATIVE_NEXT_BAR_OPEN_STOP_FIRST_NOT_TV_PARITY",
            "tv_parity_validated":False}

def _rsi_wilder(close,n):
    result=[None]*len(close)
    if len(close)<=n:return result
    diffs=[close[i]-close[i-1] for i in range(1,len(close))]
    avg_gain=sum(max(x,0.0) for x in diffs[:n])/n
    avg_loss=sum(max(-x,0.0) for x in diffs[:n])/n
    for i in range(n,len(close)):
        if i>n:
            delta=diffs[i-1]
            avg_gain=(avg_gain*(n-1)+max(delta,0.0))/n
            avg_loss=(avg_loss*(n-1)+max(-delta,0.0))/n
        if avg_loss==0:
            result[i]=100.0 if avg_gain>0 else 50.0
        else:
            rs=avg_gain/avg_loss
            result[i]=100.0-100.0/(1.0+rs)
    return result

def _run_sequence(bars,spec):
    """Signals from source structure. Order fills only an illustrative model."""
    if not isinstance(bars,list) or len(bars)>5000:
        raise ValueError("OHLC_BARS_LIST_REQUIRED")
    values=[]
    for b in bars:
        if not isinstance(b,dict) or any(k not in b for k in ("time","open","high","low","close")):
            raise ValueError("OHLC_BAR_FIELDS_REQUIRED")
        row={k:float(b[k]) for k in ("open","high","low","close")}
        if any(not math.isfinite(v) for v in row.values()):
            raise ValueError("NONFINITE_OHLC")
        if row["high"]<max(row["open"],row["close"],row["low"]) or row["low"]>min(row["open"],row["close"]):
            raise ValueError("BAD_OHLC")
        row["time"]=str(b["time"])
        values.append(row)
    opts=spec["inputs"]
    n=opts["run_length"]
    opens=[b["open"] for b in values]
    highs=[b["high"] for b in values]
    lows=[b["low"] for b in values]
    closes=[b["close"] for b in values]
    rsi=_rsi_wilder(closes,opts["rsi_length"])
    long_setups=[False]*len(values)
    short_setups=[False]*len(values)
    signals=[]
    fills=[]
    exits=[]
    pending=None
    position=None
    tol=opts["tolerance_pct"]/100.0
    for i,b in enumerate(values):
        # Pine strategy.entry orders submitted at a close typically fill at
        # next bar open. This code does not emulate TV broker fill rules.
        if pending is not None:
            side=pending["direction"]
            fills.append({"bar_index":i,"time":b["time"],"direction":side,
                "fill_price":b["open"],"signal_index":pending["signal_index"],
                "stop":pending["stop"],"target":pending["target"]})
            position={**pending,"entry_index":i,"entry_price":b["open"]}
            pending=None
        if position is not None:
            side=position["direction"]
            hit_stop=(b["low"]<=position["stop"] if side=="long"
                      else b["high"]>=position["stop"])
            hit_target=(b["high"]>=position["target"] if side=="long"
                        else b["low"]<=position["target"])
            if hit_stop or hit_target:
                # Stop-first on an ambiguous OHLC bar is conservative but
                # is NOT equivalent to the TradingView bar magnifier.
                reason="STOP" if hit_stop else "TARGET"
                price=position["stop"] if hit_stop else position["target"]
                exits.append({"bar_index":i,"time":b["time"],
                    "direction":side,"reason":reason,"price":price,
                    "entry_index":position["entry_index"]})
                position=None
        if i<n:continue
        reversal_down=closes[i-n]<opens[i-n]
        reversal_up=closes[i-n]>opens[i-n]
        bullish=True
        bearish=True
        for back in range(n):
            j=i-back
            if closes[j]<=opens[j] or lows[j]<=lows[i-n]:
                bullish=False
            if closes[j]>=opens[j] or highs[j]>=highs[i-n]:
                bearish=False
            if back<n-1:
                if closes[j]<=closes[j-1]*(1-tol):bullish=False
                if closes[j]>=closes[j-1]*(1+tol):bearish=False
        current_rsi=rsi[i]
        previous_rsi=rsi[i-1] if i>0 else None
        rsi_long=(not opts["use_rsi_filter"] or
                  (current_rsi is not None and previous_rsi is not None
                   and current_rsi>opts["rsi_min_long"] and current_rsi>previous_rsi))
        rsi_short=(not opts["use_rsi_filter"] or
                   (current_rsi is not None and previous_rsi is not None
                    and current_rsi<opts["rsi_max_short"] and current_rsi<previous_rsi))
        want_long=bool(reversal_down and bullish and rsi_long)
        want_short=bool(reversal_up and bearish and rsi_short)
        long_setups[i]=want_long
        short_setups[i]=want_short
        if position is not None or pending is not None:continue
        direction=("long" if opts["enable_long"] and want_long else
                  "short" if opts["enable_short"] and want_short else None)
        if direction is None:continue
        stop=lows[i-n] if direction=="long" else highs[i-n]
        risk=(closes[i]-stop if direction=="long" else stop-closes[i])
        if risk<=0:continue
        target=closes[i]+risk*opts["reward_multiple"]*(1 if direction=="long" else -1)
        signal={"bar_index":i,"time":b["time"],"direction":direction,
                "signal_price":closes[i],"stop":stop,"target":target}
        signals.append(signal)
        pending={**signal,"signal_index":i}
    return {"series":{"rsiVal":rsi},
            "signals":{"longSetup":long_setups,"shortSetup":short_setups},
            "orders":signals,"trades":fills,"exits":exits,
            "trade_count":len(fills),"status":"SIGNALS_EXECUTED_NO_TV_PARITY",
            "execution_model":spec["order_fills"]}

def generate_sequence_python(spec):
    if not isinstance(spec,dict) or spec.get("supported_subset")!=SCOPE:
        raise UnsupportedSequencePine("SEQUENCE_SPEC_REQUIRED")
    # Inline trusted, local implementation. The Pine source is never executed
    # or interpolated into Python; only parsed primitives are represented.
    return ("# Pine v6 restricted RSI reversal sequence converter; no TradingView parity.\n"
            "import math\n"
            "SPEC = "+repr(spec)+"\n\n"+
            inspect.getsource(_rsi_wilder)+"\n"+
            inspect.getsource(_run_sequence)+"\n"+
            "def run_strategy(bars):\n"
            "    return _run_sequence(bars,SPEC)\n")
