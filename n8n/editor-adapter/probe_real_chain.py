#!/usr/bin/env python3
"""Real WF01 node-by-node collection, including no-new-Pine page traversal."""
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE=os.getenv("STUDIO_BASE","https://investment-n8n-native-editor-production.up.railway.app").rstrip("/")
KIND=os.getenv("WF01_KIND","strategy")
WORKFLOW=f"operations/WF01-latest-{KIND}-one.json"
PREFIX=f"wf01-{KIND}-"
STEPS=[]
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

def call(method,path,data=None):
    body=json.dumps(data).encode() if data is not None else None
    headers={"Accept":"application/json","User-Agent":"WF01-real-page-probe/2",
             "X-Studio-Node-Run":"N01" if path.endswith("/node01/execute") else "APPROVED"}
    if body is not None:headers["Content-Type"]="application/json"
    for retry in range(5):
        req=urllib.request.Request(BASE+path,method=method,data=body,headers=headers)
        try:
            with opener.open(req,timeout=30) as resp:return resp.status,json.load(resp)
        except urllib.error.HTTPError as exc:
            if method=="GET" and exc.code in (502,503,504) and retry<4:
                time.sleep(1+retry);continue
            try:return exc.code,json.load(exc)
            except ValueError:return exc.code,{"error":"UNREADABLE_HTTP_RESPONSE"}
        except (OSError,TimeoutError):
            if method!="GET" or retry==4:raise
            time.sleep(1+retry)

def ensure(flag,msg):
    if not flag:raise AssertionError(msg)

def url(endpoint,node):
    return endpoint+"?"+urllib.parse.urlencode({"workflow":WORKFLOW,"node_id":node})

def execute(suffix,parent=None):
    node=PREFIX+suffix
    if parent is None:
        ensure(suffix=="01","ONLY_N01_ROOT")
        data={"workflow":WORKFLOW,"node_id":node,
              "input_json":{"ui_selection":KIND,"requested_detail_limit":1,"max_pages":3}}
        status,result=call("POST","/api/studio/node01/execute",data)
    else:
        status,edges=call("GET",url("/api/studio/nodes/transfers",node))
        ensure(status==200,"EDGE_READ_FAILED_"+node)
        incoming=[e for e in edges.get("transfers",[]) if e["source_run_id"]==parent["run_id"]]
        ensure(len(incoming)==1 and incoming[0]["output_json"]==parent["output_json"],
               "UPSTREAM_OUTPUT_NOT_DELIVERED_"+node)
        status,result=call("POST","/api/studio/nodes/execute",
                    {"workflow":WORKFLOW,"node_id":node,"source_run_id":parent["run_id"]})
    ensure(result.get("run_id"),"NO_RUN_ID_"+node+":"+str(result)[:180])
    hs,hist=call("GET",url("/api/studio/nodes/history",node))
    ensure(hs==200 and any(
        h["run_id"]==result["run_id"] and h["output_json"]==result.get("output_json")
        for h in hist.get("executions",[])),"HISTORY_MISMATCH_"+node)
    if parent is not None:
        ensure(result["input_json"]==parent["output_json"] and
               result["upstream_run_id"]==parent["run_id"],"BAD_INPUT_"+node)
    report={"node":"N"+suffix,"status":result.get("status"),"http":status,
            "run_id":result["run_id"],"error":result.get("error")}
    STEPS.append(report)
    print("WF01_NODE",json.dumps(report),flush=True)
    return status,result

def run():
    _,a=execute("01")
    _,b=execute("02",a)
    previous=b
    for page in range(1,4):
        st,c=execute("03",previous)
        if KIND=="library":
            ensure(st==422 and c["status"]=="FAILED" and
                   c["error"]=="LICENSED_MANIFEST_STRATEGIES_ONLY",
                   "LIBRARY_FEED_MUST_NOT_BE_FAKED")
            print("WF01_LIBRARY_NOT_AVAILABLE",flush=True)
            return "LIBRARY_FEED_NOT_AVAILABLE"
        ensure(st==200 and c["status"]=="SUCCESS" and
            c["output_json"]["count"]>0,"NO_REAL_CATALOG")
        _,d=execute("04",c)
        _,e=execute("05",d)
        _,g=execute("06",e)
        _,h=execute("07",g)
        out=h["output_json"]
        if out["has_candidate"]:
            ensure(out["_studio_active_ports"]==[0],"N07_TRUE_PORT_MISSING")
            status,src=execute("11",h)
            ensure(status==200 and src["output_json"]["pine_source_acquired"] is True,
                   "N11_ACTUAL_PINE_NOT_ACQUIRED")
            _,saved=execute("15",src)
            ensure(saved["output_json"]["source_saved"] is True,
                   "N15_SQLITE_SOURCE_NOT_STORED")
            _,done=execute("16",saved)
            ensure(done["output_json"]["status"]=="PINE_SAVED_CONVERSION_PENDING" and
                   done["output_json"]["paper_enabled"] is False,
                   "N16_FALSE_CONVERSION_OR_TRADE_CLAIM")
            print("WF01_PINE_SOURCE_SAVED_REAL_RUN",
                  done["output_json"]["source_id"],flush=True)
            return "PINE_SAVED_CONVERSION_PENDING"
        ensure(out["_studio_active_ports"]==[1],"N07_FALSE_PORT_MISSING")
        _,n8=execute("08",h)
        more=n8["output_json"]["next_page_available"]
        if more:
            ensure(n8["output_json"]["_studio_active_ports"]==[0],"N08_TRUE_PORT_MISSING")
            _,previous=execute("09",n8)
            ensure(previous["output_json"]["page"]==page+1,"N09_PAGE_ADVANCE_FAILED")
            continue
        ensure(n8["output_json"]["_studio_active_ports"]==[1],"N08_FALSE_PORT_MISSING")
        _,terminal=execute("10",n8)
        ensure(terminal["output_json"]["status"]=="NO_FETCHABLE_NEW_PINE" and
               terminal["output_json"]["saved_count"]==0,"N10_FALSE_SAVING_CLAIM")
        print("WF01_NO_FETCHABLE_NEW_PINE",flush=True)
        return "NO_FETCHABLE_NEW_PINE"
    raise AssertionError("WF01_PAGE_LIMIT_NOT_ENFORCED")

if __name__=="__main__":
    try:
        result=run()
        print(json.dumps({"result":result,"steps":STEPS},ensure_ascii=False,indent=2))
    except Exception as exc:
        print("WF01_REAL_CHAIN_FAILED",type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(1)
