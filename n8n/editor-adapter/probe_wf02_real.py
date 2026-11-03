#!/usr/bin/env python3
"""Run six real WF02 nodes sequentially against Railway with exact DB Pine.

No old SMA/EMA/RSI converter fallback. Without PYNESYS_API_KEY the only valid
live result is explicit blocked status; no fabricated PyneComp output.
"""
import http.cookiejar,json,os,sys,time,urllib.parse,urllib.error,urllib.request
BASE=os.environ.get("STUDIO_BASE","https://investment-n8n-native-editor-production.up.railway.app").rstrip("/")
FLOW="operations/WF02-pine-to-python.json"
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def request_json(method,path,data=None,root=False):
    headers={"Accept":"application/json","User-Agent":"PyneComp-WF02-probe/1",
             "X-Studio-Node-Run":"N01" if root else "APPROVED"}
    body=None
    if data is not None:body=json.dumps(data).encode();headers["Content-Type"]="application/json"
    req=urllib.request.Request(BASE+path,data=body,method=method,headers=headers)
    for attempt in range(4):
        try:
            with opener.open(req,timeout=60) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:
            try:return e.code,json.load(e)
            except ValueError:return e.code,{"error":"INVALID_HTTP_JSON"}
        except (OSError,TimeoutError):
            if method!="GET" or attempt==3:raise
            time.sleep(attempt+1)
def execute(node,previous=None):
    if previous:
        args={"workflow":FLOW,"node_id":node,"source_run_id":previous}
        api="/api/studio/nodes/execute"
    else:
        args={"workflow":FLOW,"node_id":node,"input_json":{
            "ui_selection":"strategy","requested_detail_limit":1,
            "source_id":os.environ.get("WF02_SOURCE_ID","PUB;67a1548c0960450086a19d5b0ef1d467"),
            "version_key":os.environ.get("WF02_VERSION_KEY","1.0")}}
        api="/api/studio/node01/execute"
    status,response=request_json("POST",api,args,root=previous is None)
    if status!=200 or response.get("status")!="SUCCESS":
        raise RuntimeError(f"NODE_EXECUTION_FAILED {node} HTTP {status} "+
                           str(response.get("error") or response.get("error_code"))[:190])
    out=response["output_json"]
    print("WF02_REAL_NODE",node,"business_status",out.get("status"),
          "run",response["run_id"],flush=True)
    return response
def main():
    src=request_json("GET","/api/studio/workflows/"+FLOW)[1]
    nodes=src["workflow"]["nodes"]
    if len(nodes)!=6:raise AssertionError("WF02_IS_NOT_SIX_PYNECOMP_NODES")
    previous=None;last=None
    for i in range(1,7):
        last=execute("wf02-%02d"%i,previous)
        previous=last["run_id"]
    result=last["output_json"]
    expected="PYNECOMP_API_KEY_MISSING"
    if os.environ.get("WF02_EXPECT_CONFIGURED")=="1":
        if result.get("status") not in ("PYNECOMP_GENERATED_UNVALIDATED",
                "PINNED_LIBRARY_SOURCE_MISSING","PYNECOMP_AUTH_DENIED","PYNECOMP_QUOTA_EXCEEDED"):
            raise AssertionError("UNEXPECTED_PYNECOMP_STATUS "+str(result.get("status")))
    elif result.get("status")!=expected:
        raise AssertionError("MISSING_API_KEY_MUST_BLOCK_NOT_CONVERT "+str(result.get("status")))
    if result.get("conversion_validated") is not False or result.get("paper_enabled") is not False:
        raise AssertionError("FALSE_CONVERSION_PARITY_OR_TRADING_APPROVAL")
    if result.get("status")==expected and result.get("python_code") is not None:
        raise AssertionError("LEGACY_GENERATED_CODE_LEAKED")
    print("WF02_PYNECOMP_6_REAL_NODES_CONFIRMED_"+result["status"],flush=True)
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("WF02_LIVE_FAILED",type(exc).__name__,str(exc)[:300],file=sys.stderr,flush=True)
        sys.exit(1)
