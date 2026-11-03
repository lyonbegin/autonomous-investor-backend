"""Compare real DDDS Vela chart plots vs real compiled DDDS Python on EXACT
300 price bars observed at deployed OUR SITE. No TV published-trades claims.
"""
import json,math,os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"editor-adapter"))
from investment_ddds_parity import DDDS_SOURCE_SHA,DDDS_SOURCE_ID
from investment_shared_bars_compare import execute_shared_bars

ROOT=Path(os.environ.get("DDDS_SITE_COMPARE_DIR","/tmp/ddds-site-vela-pyne-300"))
def main():
    raw=json.loads((ROOT/"same-300-real-site-bars.json").read_text())
    vela=json.loads((ROOT/"same-300-vela-plots.json").read_text())
    if (vela["script_id"]!=DDDS_SOURCE_ID or
        vela["source_hash"]!=DDDS_SOURCE_SHA or
        vela["provenance"]!="VELA_PINETS_CHART_CONTROL" or
        not vela["complete"] or vela["forming"] or
        len(raw)!=len(vela["bars"]) or len(raw)!=300):
        raise RuntimeError("DDDS_REAL_VELA_ORIGINAL_SOURCE_NOT_VERIFIED")
    bars=[]
    for index,(a,b) in enumerate(zip(raw,vela["bars"])):
        if (a["timestamp"]!=b["time_ms"] or
            any(float(a[k])!=float(b[k]) for k in ("open","high","low","close","volume"))):
            raise RuntimeError("DDDS_REAL_VELA_BAR_MISMATCH_"+str(index))
        bars.append({"time_ms":a["timestamp"],**{k:a[k] for k in
                     ("open","high","low","close","volume")}})
    result=execute_shared_bars({
       "source_id":DDDS_SOURCE_ID,
       "pine_source_sha256":DDDS_SOURCE_SHA,
       "symbol":"NASDAQ:AMZN","timeframe":"120","acknowledge_mpl":True,
       "bars":bars
    })
    if result["time_ms"]!=[x["time_ms"] for x in bars] or result["close"]!=[float(x["close"]) for x in bars]:
        raise RuntimeError("DDDS_SAME_DATA_PYTHON_OUTPUT_NOT_ALIGNED")
    summary={}
    total,agree,differ=0,0,0
    for name in ("Decycler","Price anchor","Lower band","Upper band","Stop","Target"):
        if name not in vela["plot_names"]:continue
        n=eq=neq=0;maxdiff=0;sample=[]
        for ix,row in enumerate(vela["bars"]):
            x=row.get("plots",{}).get(name)
            y=result["plots"][name][ix]
            if not isinstance(x,(int,float)) or not isinstance(y,(int,float)) or (
               not math.isfinite(x) or not math.isfinite(y)):
                continue
            diff=abs(float(x)-float(y))
            tol=max(.0001,max(abs(x),abs(y))*.00001)
            n+=1;maxdiff=max(maxdiff,diff)
            if diff<=tol:eq+=1
            else:
                neq+=1
                if len(sample)<3:sample.append({"time_ms":row["time_ms"],
                    "vela":x,"python":y,"absolute_difference":diff})
        summary[name]={"common_numeric_points":n,"within_tolerance":eq,
                       "mismatching":neq,"max_abs_difference":maxdiff,
                       "samples":sample}
        total+=n;agree+=eq;differ+=neq
    report={
       "status":"ACTUAL_DDDS_VELA_AND_PYTHON_SAME_300_SITE_BARS_COMPARED",
       "source_id":DDDS_SOURCE_ID,
       "source_sha256":DDDS_SOURCE_SHA,
       "python_sha256":result["python_sha256"],
       "market_data":"OUR_DEPLOYED_SITE_CHART_API",
       "symbol":"NASDAQ:AMZN","timeframe":"2h",
       "exact_market_bars":300,
       "input_ohlcv_sha256":result["input_ohlcv_sha256"],
       "common_numeric_points":total,
       "matching_points":agree,"mismatching_points":differ,
       "by_indicator":summary,
       "official_tradingview_published_chart_verified":False,
       "published_299_trades_compared":False,
       "paper_enabled":False,"live_orders_enabled":False
    }
    (ROOT/"actual-ddds-vela-vs-python-300-numeric-comparison.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("REAL_DDDS_VELA_PYTHON_300_COMPARE "+json.dumps(report,ensure_ascii=False))
    if total==0:raise RuntimeError("NO_REAL_COMMON_DDDS_PLOT_POINTS_FOR_COMPARISON")
if __name__=="__main__":main()
