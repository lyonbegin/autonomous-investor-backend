#!/usr/bin/env python3
"""Live WF02 node-by-node test against actual Railway SQLite, no fake Pine."""
import http.cookiejar
import json
import os
import sys
import time
import urllib.parse
import urllib.error
import urllib.request

BASE=os.environ.get("STUDIO_BASE","https://investment-n8n-native-editor-production.up.railway.app").rstrip("/")
WORKFLOW="operations/WF02-pine-to-python.json"
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

def call(method,path,data=None,root=False):
    headers={"Accept":"application/json","User-Agent":"WF02-real-pine-probe/1",
             "X-Studio-Node-Run":"N01" if root else "APPROVED"}
    body=None
    if data is not None:
        body=json.dumps(data).encode()
        headers["Content-Type"]="application/json"
    req=urllib.request.Request(BASE+path,method=method,headers=headers,data=body)
    for attempt in range(3):
        try:
            with opener.open(req,timeout=25) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:
            if method=="GET" and e.code in (429,502,503,504) and attempt<2:
                time.sleep(1+attempt)
                continue
            try: return e.code,json.load(e)
            except ValueError:return e.code,{"error":"INVALID_HTTP_JSON"}
        except (OSError,TimeoutError) as e:
            if method!="GET" or attempt==2:raise
            time.sleep(1+attempt)

def check(ok,message):
    if not ok:raise AssertionError(message)

def query(endpoint,node):
    return endpoint+"?"+urllib.parse.urlencode({"workflow":WORKFLOW,"node_id":node})

def stage(node,source_run_id=None):
    if source_run_id is None:
        selector={"ui_selection":"strategy","requested_detail_limit":1}
        if os.environ.get("WF02_SOURCE_ID"):
            selector["source_id"]=os.environ["WF02_SOURCE_ID"]
            selector["version_key"]=os.environ.get("WF02_VERSION_KEY","1.0")
        params={"workflow":WORKFLOW,"node_id":node,"input_json":selector}
        code,obj=call("POST","/api/studio/node01/execute",params,root=True)
    else:
        st,edges=call("GET",query("/api/studio/nodes/transfers",node))
        check(st==200,"NO_EDGE_API")
        matches=[t for t in edges.get("transfers",[]) if t.get("source_run_id")==source_run_id]
        check(len(matches)==1,"PREVIOUS_NODE_OUTPUT_NOT_READY")
        params={"workflow":WORKFLOW,"node_id":node,"source_run_id":source_run_id}
        code,obj=call("POST","/api/studio/nodes/execute",params)
        check(obj.get("input_json")==matches[0]["output_json"],"INPUT_NOT_PREVIOUS_OUTPUT")
    check(code==200 and obj.get("status")=="SUCCESS",
        f"{node} HTTP {code}: {str(obj.get('error') or obj.get('error_code') or obj)[:250]}")
    st,hist=call("GET",query("/api/studio/nodes/history",node))
    check(st==200 and any(x.get("run_id")==obj["run_id"] and x.get("output_json")==obj["output_json"]
       for x in hist.get("executions",[])),"DB_EXECUTION_OUTPUT_NOT_RECORDED")
    result=obj["output_json"]
    report={"node":node,"run_id":obj["run_id"],"http":code,"status":result.get("status")}
    if result.get("unsupported_reason"): report["unsupported_reason"]=result["unsupported_reason"]
    if result.get("source_id"):report["source_id"]=result["source_id"]
    if result.get("version_key"):report["version_key"]=result["version_key"]
    print("WF02_NODE",json.dumps(report,ensure_ascii=False),flush=True)
    return obj

def main():
    first=stage("wf02-01")
    check(first["output_json"]["pine_code"].strip(),"REAL_DB_PINE_EMPTY")
    if os.environ.get("WF02_SOURCE_ID"):
        check(first["output_json"]["source_id"]==os.environ["WF02_SOURCE_ID"],"UNEXPECTED_STORED_STRATEGY")
    second=stage("wf02-02",first["run_id"])
    result=second["output_json"]
    check(result.get("status") in ("PYTHON_GENERATED","UNSUPPORTED_PINE"),"UNEXPECTED_RESULT")
    if result["status"]=="PYTHON_GENERATED":
        check("def run_strategy" in result.get("python_code",""),"PYTHON_SOURCE_NOT_GENERATED")
        if os.environ.get("WF02_EXPECT_SCOPE"):
            check(result.get("converter_scope")==os.environ["WF02_EXPECT_SCOPE"],
                  "WRONG_COMPILER_PATH_OR_INCOMPLETE_STRATEGY")
            opts=result.get("strategy_spec",{}).get("inputs",{})
            check(opts.get("run_length")==5 and opts.get("rsi_length")==14
                  and opts.get("enable_long") is True
                  and opts.get("enable_short") is False
                  and opts.get("reward_multiple")==1.5,
                  "ACTUAL_SCRIPT_INPUT_DEFAULTS_NOT_PARSED")
    else:
        check(result.get("python_code") is None and result.get("unsupported_reason"),
              "UNSUPPORTED_SCRIPT_FAKED_AS_PYTHON")
    last=stage("wf02-03",second["run_id"])
    check(last["output_json"]["paper_enabled"] is False and
          last["output_json"]["tradingview_chart_validated"] is False,
          "FALSE_TRADING_OR_PARITY_APPROVAL")
    if result["status"]=="UNSUPPORTED_PINE":
        print("WF02_REAL_SOURCE_UNSUPPORTED_NOT_CONVERTED",result["unsupported_reason"])
        return 3 if os.environ.get("WF02_REQUIRE_REAL_CONVERSION")=="1" else 0
    print("WF02_REAL_PINE_PYTHON_GENERATED_REQUIRES_TV_PARITY")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception as e:
        print("WF02_LIVE_FAILED",type(e).__name__,str(e),file=sys.stderr,flush=True)
        sys.exit(1)
