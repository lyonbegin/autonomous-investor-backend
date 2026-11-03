"""Execute PyneComp-generated @pyne Python with the PyneCore ScriptRunner.

Only a dedicated bounded subprocess executes generated code, not the n8n/studio
server process. Receives REAL OHLCV from the existing market-data provider.
Exports UTC bar-keyed price/plot/closed-trade events for the existing chart
parity comparator. It does NOT assert TradingView numerical equivalence.
"""
import csv,io,json,math,os,re,resource,subprocess,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone

MAX_BARS=15000
MAX_SOURCE_BYTES=3*1024*1024
MAX_RUNTIME=60

class PyneCoreRuntimeError(ValueError):pass

def _safe_bars(data):
    if not isinstance(data,list) or not 2<=len(data)<=MAX_BARS:
        raise PyneCoreRuntimeError("PYNECORE_INVALID_BAR_COUNT")
    result=[]
    last=None
    for bar in data:
        if not isinstance(bar,dict):raise PyneCoreRuntimeError("PYNECORE_INVALID_BAR")
        try:
            stamp=int(float(bar["timestamp"] if "timestamp" in bar else bar["time"]))
            if abs(stamp)<10**11:stamp*=1000
            row={"time":stamp}
            for key in ("open","high","low","close"):
                row[key]=float(bar[key])
                if not math.isfinite(row[key]):raise ValueError()
            row["volume"]=float(bar.get("volume") or 0)
            if not math.isfinite(row["volume"]) or row["volume"]<0:raise ValueError()
            if row["high"]<max(row["open"],row["close"],row["low"]) or row["low"]>min(row["open"],row["close"],row["high"]):
                raise ValueError()
            if last is not None and stamp<=last:raise ValueError()
        except (KeyError,TypeError,ValueError,OverflowError):
            raise PyneCoreRuntimeError("PYNECORE_BAD_OHLCV_OR_TIME_ORDER") from None
        result.append(row);last=stamp
    return result

def _safe_symbol(symbol,tf):
    if not isinstance(symbol,str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{3,70}",symbol):
        raise PyneCoreRuntimeError("PYNECORE_SYMBOL_INVALID")
    if not isinstance(tf,str) or not re.fullmatch(r"(?:[1-9]\d{0,3}|[1-9]\d*[mhdwMDW]?)",tf):
        raise PyneCoreRuntimeError("PYNECORE_TIMEFRAME_INVALID")
    return symbol,tf

def run_generated(python_source,bars,*,symbol,timeframe,inputs=None,settings=None):
    """Run compiler output in a child with strict limits and stripped secrets.

    Does not fetch data, evaluate raw Pine, or silently substitute cached RSI.
    Dependencies must be link-verified prior to calling this function.
    """
    if not isinstance(python_source,str) or not 1<=len(python_source.encode())<=MAX_SOURCE_BYTES:
        raise PyneCoreRuntimeError("PYNECORE_GENERATED_SOURCE_INVALID")
    if "@pyne" not in python_source[:4096]:
        raise PyneCoreRuntimeError("PYNECORE_MAGIC_HEADER_REQUIRED")
    values=_safe_bars(bars)
    symbol,timeframe=_safe_symbol(symbol,timeframe)
    if inputs is not None and not isinstance(inputs,dict):
        raise PyneCoreRuntimeError("PYNECORE_INPUTS_INVALID")
    if settings is not None and not isinstance(settings,dict):
        raise PyneCoreRuntimeError("PYNECORE_SETTINGS_INVALID")
    with tempfile.TemporaryDirectory(prefix="investment-pynecore-") as directory:
        folder=Path(directory)
        (folder/"compiled.py").write_text(python_source,encoding="utf-8")
        (folder/"run.json").write_text(json.dumps({
            "bars":values,"symbol":symbol,"timeframe":timeframe,
            "inputs":inputs or {},"settings":settings or {}},ensure_ascii=False),encoding="utf-8")
        environment={"PATH":os.environ.get("PATH","/usr/bin:/bin"),
              "HOME":directory,"PYNE_SAVE_SCRIPT_TOML":"0",
              "PYTHONUNBUFFERED":"1","OMP_NUM_THREADS":"1"}
        def limits():
            resource.setrlimit(resource.RLIMIT_CPU,(MAX_RUNTIME,MAX_RUNTIME+2))
            resource.setrlimit(resource.RLIMIT_AS,(1500*1024*1024,1500*1024*1024))
            resource.setrlimit(resource.RLIMIT_FSIZE,(30*1024*1024,30*1024*1024))
        try:
            result=subprocess.run([sys.executable,"-I",str(Path(__file__).resolve()),
                "--worker",str(folder)],timeout=MAX_RUNTIME+5,
                cwd=directory,env=environment,capture_output=True,text=True,
                preexec_fn=limits,check=False)
        except subprocess.TimeoutExpired:
            raise PyneCoreRuntimeError("PYNECORE_RUN_TIME_LIMIT_EXCEEDED") from None
        if result.returncode!=0:
            # Only a short diagnostic; generated code never reaches gateway logs.
            error_file=folder/"error.json"
            message="PYNECORE_WORKER_FAILED"
            if error_file.exists():
                try:message=json.loads(error_file.read_text()).get("error","PYNECORE_WORKER_FAILED")
                except (OSError,ValueError):pass
            raise PyneCoreRuntimeError(message) from None
        out=folder/"output.json"
        if not out.exists():raise PyneCoreRuntimeError("PYNECORE_WORKER_NO_OUTPUT")
        payload=json.loads(out.read_text(encoding="utf-8"))
        if payload.get("bars_processed")!=len(values) or not payload.get("plot_csv"):
            raise PyneCoreRuntimeError("PYNECORE_OUTPUT_INCOMPLETE")
        return payload

def _worker(folder):
    import traceback
    from pynecore.core.script_runner import ScriptRunner
    from pynecore.core.syminfo import SymInfo
    from pynecore.types.ohlcv import OHLCV
    data=json.loads((folder/"run.json").read_text())
    sym=data["symbol"]
    prefix,ticker=(sym.split(":",1) if ":" in sym else ("UNKNOWN",sym))
    tf=data["timeframe"].lower()
    if tf.endswith("h"):period=str(int(tf[:-1])*60)
    elif tf.endswith("m"):period=tf[:-1]
    elif tf.endswith("d"):period="D"
    elif tf.endswith("w"):period="W"
    else:period=data["timeframe"]
    syminfo=SymInfo(prefix=prefix,ticker=ticker,currency="USD",basecurrency="",
       description=ticker,period=period,type="stock" if prefix=="NASDAQ" else "crypto",
       mintick=0.01,pricescale=100,minmove=1,pointvalue=1.0,mincontract=1.0,
       timezone="UTC",volumetype="base",
       opening_hours=[],session_starts=[],session_ends=[])
    original=data["bars"]
    candles=[OHLCV(timestamp=r["time"],open=r["open"],high=r["high"],
        low=r["low"],close=r["close"],volume=r["volume"]) for r in original]
    runner=ScriptRunner(script_path=folder/"compiled.py",
        ohlcv_iter=candles,syminfo=syminfo,
        plot_path=folder/"pynecore_plots_raw.csv",
        strat_path=folder/"pynecore_stats_raw.csv",
        trade_path=folder/"pynecore_trades_raw.csv",
        inputs=data["inputs"],settings=data["settings"])
    output_rows=[];trade_rows=[]
    for record in runner.run_iter():
        candle,plots=record[0],record[1]
        new_trades=record[2] if len(record)>2 else []
        row={"time":candle.timestamp,"open":candle.open,
             "high":candle.high,"low":candle.low,"close":candle.close}
        for name,value in plots.items():
            if value is None:row[str(name)]=""
            elif isinstance(value,(int,float)) and math.isfinite(value):
                row[str(name)]=value
            else:row[str(name)]=""
        output_rows.append(row)
        for trade in new_trades:
            trade_rows.append({k:getattr(trade,k,None) for k in
                ("entry_id","exit_id","size","entry_time","exit_time",
                 "entry_price","exit_price","profit","profit_percent","commission")})
    fields=list(dict.fromkeys([key for row in output_rows for key in row]))
    csv_buffer=io.StringIO()
    writer=csv.DictWriter(csv_buffer,fieldnames=fields,extrasaction="ignore")
    writer.writeheader()
    writer.writerows(output_rows)
    (folder/"output.json").write_text(json.dumps({
        "status":"PYNECORE_EXECUTED_NOT_TV_VALIDATED",
        "bars_processed":len(output_rows),"trade_count":len(trade_rows),
        "plot_columns":[x for x in fields if x not in ("time","open","high","low","close")],
        "plot_csv":csv_buffer.getvalue(),"closed_trades":trade_rows[:1000],
        "tradingview_parity_verified":False
    },ensure_ascii=False,allow_nan=False),encoding="utf-8")

if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1]!="--worker":raise SystemExit(2)
    directory=Path(sys.argv[2])
    try:_worker(directory)
    except Exception as exc:
        (directory/"error.json").write_text(json.dumps({
            "error":"PYNECORE_RUN_ERROR_"+type(exc).__name__+"_"+str(exc)[:180]
        }))
        raise SystemExit(1)
