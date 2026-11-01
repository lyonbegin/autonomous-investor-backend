#!/usr/bin/env python3
"""Actually execute one Railway node at a time and compare real DB I/O.

No mock output, fake provider, synthetic catalog or skipped node execution.
Stops at N03 when the approved catalog endpoint is missing/unavailable.
"""
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE=os.environ.get("STUDIO_BASE","https://investment-n8n-native-editor-production.up.railway.app").rstrip("/")
KIND=os.environ.get("WF01_KIND","strategy")
if KIND not in ("strategy","library"):raise RuntimeError("UNSUPPORTED_KIND")
WORKFLOW=f"operations/WF01-latest-{KIND}-one.json"
PREFIX=f"wf01-{KIND}-"
RECORDED=[]

def check(condition,message):
    if not condition:raise AssertionError(message)

def client():
    cookies=http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

def call(opener,method,path,data=None,extra=None):
    body=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
    headers={"Accept":"application/json","User-Agent":"WF01-real-node-probe/1",
             **({"Content-Type":"application/json"} if data is not None else {}),
             **(extra or {})}
    req=urllib.request.Request(BASE+path,data=body,headers=headers,method=method)
    started=time.monotonic()
    try:
        response=opener.open(req,timeout=30)
        status=response.status
        raw=response.read(2000000)
    except urllib.error.HTTPError as exc:
        status=exc.code;raw=exc.read(2000000)
    elapsed=round((time.monotonic()-started)*1000,2)
    try:payload=json.loads(raw)
    except ValueError:payload={"raw":raw.decode(errors="replace")}
    return status,payload,elapsed

def query(path,node):
    return path+"?"+urllib.parse.urlencode({"workflow":WORKFLOW,"node_id":node})

def last_history(opener,node):
    status,payload,_=call(opener,"GET",query("/api/studio/nodes/history",node))
    check(status==200,f"GET HISTORY {node} returned {status}: {payload}")
    return payload["executions"]

def transfer(opener,target,source_run_id):
    status,payload,_=call(opener,"GET",query("/api/studio/nodes/transfers",target))
    check(status==200,f"GET TRANSFERS {target} returned {status}: {payload}")
    matches=[x for x in payload["transfers"] if x["source_run_id"]==source_run_id]
    check(len(matches)==1,f"NO UNIQUE TRANSFER to {target} from {source_run_id}")
    return matches[0]

def perform():
    opener=client()
    status,health,_=call(opener,"GET","/api/studio/health")
    check(status==200 and health.get("projectAdapterConnected") is True,
          "STUDIO PROJECT ADAPTER IS NOT AVAILABLE")
    init={"ui_selection":KIND,"requested_detail_limit":1,"max_pages":3}
    n1=PREFIX+"01";n2=PREFIX+"02";n3=PREFIX+"03";n4=PREFIX+"04"

    # N01: invoke server-side Python, no stubs.
    status,a,ms=call(opener,"POST","/api/studio/node01/execute",
        {"workflow":WORKFLOW,"node_id":n1,"input_json":init},
        {"X-Studio-Node-Run":"N01"})
    check(status==200 and a["status"]=="SUCCESS",f"N01 FAILED HTTP {status}: {a}")
    check(a["input_json"]==init,"N01 INPUT WAS ALTERED")
    check(a["output_json"]["kind"]==KIND and a["output_json"]["page"]==1,
          "N01 INCORRECT OUTPUT")
    check(a.get("tradingview_called") is False,"N01 FALSE COLLECTION CLAIM")
    h1=last_history(opener,n1)
    check(h1[0]["run_id"]==a["run_id"] and h1[0]["output_json"]==a["output_json"],
          "N01 SQLITE OUTPUT NOT MATCHING RESPONSE")
    RECORDED.append({"node":"N01","status":"SUCCESS","http":status,"run_id":a["run_id"],
         "input":a["input_json"],"output":a["output_json"],"elapsed_ms":ms})
    print("N01 EXECUTED AND STORED",a["run_id"],flush=True)

    # N01's EXACT persisted output is passed to N02 via source_run_id.
    t12=transfer(opener,n2,a["run_id"])
    check(t12["output_json"]==a["output_json"] and t12["status"]=="READY",
          "N01→N02 FULL OUTPUT TRANSFER NOT READY")
    status,b,ms=call(opener,"POST","/api/studio/nodes/execute",
        {"workflow":WORKFLOW,"node_id":n2,"source_run_id":a["run_id"]},
        {"X-Studio-Node-Run":"APPROVED"})
    check(status==200 and b["status"]=="SUCCESS",f"N02 FAILED HTTP {status}: {b}")
    check(b["upstream_output_json"]==a["output_json"],"N02 UPSTREAM OUTPUT MUTATED")
    for key,val in a["output_json"].items():
        check(b["input_json"][key]==val,f"N02 INPUT lost N01 FIELD {key}")
        check(b["output_json"][key]==val,f"N02 OUTPUT lost N01 FIELD {key}")
    check(b["output_json"]["page_size"]==50 and b["output_json"]["selected_count"]==0,
          "N02 FAILED TO ADD REAL CATALOG PARAMETERS")
    h2=last_history(opener,n2)
    check(h2[0]["run_id"]==b["run_id"] and
          h2[0]["upstream_run_id"]==a["run_id"] and
          h2[0]["input_json"]==b["input_json"] and
          h2[0]["output_json"]==b["output_json"],
          "N02 SQLITE DOES NOT MATCH ITS INPUT / OUTPUT / SOURCE RUN")
    RECORDED.append({"node":"N02","status":"SUCCESS","http":status,"run_id":b["run_id"],
         "upstream_run_id":a["run_id"],"input":b["input_json"],
         "output":b["output_json"],"elapsed_ms":ms})
    print("N02 EXECUTED USING N01 RUN",a["run_id"],"→",b["run_id"],flush=True)

    # N03 must EXECUTE and record either real catalog data or real error.
    t23=transfer(opener,n3,b["run_id"])
    check(t23["output_json"]==b["output_json"] and t23["status"]=="READY",
          "N02→N03 TRANSFER MISMATCH")
    status,c,ms=call(opener,"POST","/api/studio/nodes/execute",
        {"workflow":WORKFLOW,"node_id":n3,"source_run_id":b["run_id"]},
        {"X-Studio-Node-Run":"APPROVED"})
    check(status in (200,422),f"N03 NOT EXECUTED HTTP {status}: {c}")
    h3=last_history(opener,n3)
    check(h3 and h3[0]["run_id"]==c["run_id"] and
          h3[0]["upstream_run_id"]==b["run_id"],"N03 EXECUTION HISTORY MISSING")
    check(h3[0]["input_json"]==b["output_json"],
          "N03 ACTUAL SQLITE INPUT != N02 ACTUAL OUTPUT")
    if status==200:
        check(c["status"]=="SUCCESS" and c["output_json"]["catalog_source"]=="AUTHORIZED_EXTERNAL_FEED",
              f"N03 FALSE CATALOG SUCCESS {c}")
        check(h3[0]["output_json"]==c["output_json"],"N03 DB OUTPUT MISMATCH")
        check(isinstance(c["output_json"]["items"],list),"N03 MISSING REAL ITEMS ARRAY")
        t34=transfer(opener,n4,c["run_id"])
        check(t34["output_json"]==c["output_json"],"N03→N04 TRANSFER MISMATCH")
        state="N03_AUTHORIZED_REAL_FEED_SUCCESS_N04_NOT_EXECUTED"
    else:
        check(c["status"]=="FAILED" and c["output_json"] is None,
              "N03 ERROR MUST NOT REPORT SUCCESS")
        check(h3[0]["status"]=="FAILED","FAILED N03 WAS NOT PERSISTED")
        status4,data4,_=call(opener,"GET",query("/api/studio/nodes/transfers",n4))
        check(status4==200 and not any(t["workflow_run_id"]==a["run_id"]
             for t in data4["transfers"]), "FAILED N03 STILL OPENED N04")
        state="N03_BLOCKED_STOPPED_BEFORE_N04"
    RECORDED.append({"node":"N03","status":c["status"],"http":status,
      "run_id":c["run_id"],"upstream_run_id":b["run_id"],
      "input":c["input_json"],"output":c["output_json"],
      "error":c.get("error"),"elapsed_ms":ms})
    print("N03 EXECUTION",state,c.get("error") or c["output_json"].get("count"),flush=True)
    return {"workflow":WORKFLOW,"result":state,"steps":RECORDED,
      "meaning":"N01,N02 real successes; N03 must be real approved feed or explicit FAILED, never synthetic."}

if __name__=="__main__":
    try:
        print(json.dumps(perform(),ensure_ascii=False,indent=2),flush=True)
    except Exception as e:
        print("CHAIN_PROBE_FAILED",type(e).__name__,str(e),
              json.dumps(RECORDED,ensure_ascii=False),file=sys.stderr,flush=True)
        raise
