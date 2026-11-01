#!/usr/bin/env python3
"""Execute actual Railway WF01 nodes, one at a time, without author/hash auditing."""
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
RESULTS=[]

def request(opener,method,path,data=None):
    headers={"Accept":"application/json","User-Agent":"WF01-real-node-probe/2"}
    payload=None
    if data is not None:
        payload=json.dumps(data).encode("utf-8")
        headers["Content-Type"]="application/json"
    headers["X-Studio-Node-Run"]="APPROVED"
    req=urllib.request.Request(BASE+path,method=method,data=payload,headers=headers)
    try:
        with opener.open(req,timeout=35) as response:
            return response.status,json.load(response)
    except urllib.error.HTTPError as exc:
        try: body=json.loads(exc.read())
        except ValueError: body={"error":"HTTP_"+str(exc.code)}
        return exc.code,body

def url(endpoint,node):
    return endpoint+"?"+urllib.parse.urlencode({"workflow":WORKFLOW,"node_id":node})

def check(condition,message):
    if not condition:
        raise AssertionError(message)

def run():
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    health_status,health=request(opener,"GET","/api/studio/health")
    check(health_status==200 and health.get("projectAdapterConnected") is True,
          "PROJECT_ADAPTER_OFFLINE")
    parent=None
    for step in ["01","02","03","04","05","06","07","11","15","16"]:
        node=PREFIX+step
        if step=="01":
            params={"workflow":WORKFLOW,"node_id":node,
                    "input_json":{"ui_selection":KIND,"requested_detail_limit":1,"max_pages":3}}
            api="/api/studio/node01/execute"
        else:
            check(parent is not None,"MISSING_UPSTREAM")
            st,transfer=request(opener,"GET",url("/api/studio/nodes/transfers",node))
            check(st==200,"CANNOT_READ_EDGE")
            transfers=[t for t in transfer.get("transfers",[])
                       if t["source_run_id"]==parent["run_id"]]
            check(len(transfers)==1 and transfers[0]["output_json"]==parent["output_json"],
                  f"N{step} DID NOT RECEIVE PREVIOUS OUTPUT")
            params={"workflow":WORKFLOW,"node_id":node,"source_run_id":parent["run_id"]}
            api="/api/studio/nodes/execute"
        code,data=request(opener,"POST",api,params)
        st,history=request(opener,"GET",url("/api/studio/nodes/history",node))
        check(st==200,"CANNOT_READ_NODE_HISTORY")
        matching=[r for r in history.get("executions",[]) if r.get("run_id")==data.get("run_id")]
        check(len(matching)==1,f"N{step} RUN NOT IN SQLITE HISTORY: run={data.get('run_id')!r}, history_status={st}, keys={list(history)}, recent_runs={[x.get('run_id') for x in history.get('executions',[])[:5]]}")
        record=matching[0]
        check(record["input_json"]==data["input_json"] and
              record["output_json"]==data["output_json"],f"N{step} DB IO MISMATCH")
        if parent:
            check(data["upstream_run_id"]==parent["run_id"] and
                  data["input_json"]==parent["output_json"],
                  f"N{step} INPUT != PRIOR OUTPUT")
        RESULTS.append({"node":"N"+step,"http":code,"status":data.get("status"),
                        "run_id":data.get("run_id"),"error":data.get("error")})
        print("NODE_RESULT",json.dumps(RESULTS[-1],ensure_ascii=False),flush=True)
        if KIND=="library" and step=="03":
            check(code==422 and data["status"]=="FAILED",
                  "LIBRARY_MUST_REPORT_REAL_PROVIDER_UNAVAILABLE")
            return "LIBRARY_CATALOG_NOT_AVAILABLE"
        check(code==200 and data.get("status")=="SUCCESS",
              f"N{step} EXECUTION_FAILED: {data.get('error') or code}")
        result=data["output_json"]
        if step=="03":
            check(result["count"]>0 and result.get("catalog_is_live") is False,
                  "NO_REAL_CATALOG_OR_FALSE_LIVE_STATUS")
        if step=="05":
            check(result["checked_count"]>0,"DB_COMPARE_NOT_RUN")
        if step=="07":
            check(result.get("_studio_active_ports")==[0],
                  "NO_NEW_CANDIDATE_TO_COLLECT")
        if step=="11":
            check(result.get("pine_source_acquired") is True and
                  "strategy(" in result["pine_code"],
                  "PINE_TEXT_NOT_ACQUIRED")
            check("pine_source_sha256" not in result and
                  "author" not in result["candidate"],
                  "UNNECESSARY_AUTHOR_OR_HASH_GATE_REMAINS")
        if step=="15":
            check(result.get("source_saved") is True,"PINE_NOT_STORED_IN_SQLITE")
        if step=="16":
            check(result["status"]=="PINE_SAVED_CONVERSION_PENDING" and
                  result["paper_enabled"] is False and
                  result["conversion_validated"] is False,
                  "UNVERIFIED_CONVERSION_OR_TRADING_CLAIM")
            print("WF01_PINE_SOURCE_SAVED_REAL_RUN",result["source_id"],
                  result["version_key"],flush=True)
        parent=data
    return "PINE_SAVED_CONVERSION_PENDING"

if __name__=="__main__":
    try:
        result=run()
        print(json.dumps({"result":result,"runs":RESULTS},ensure_ascii=False,indent=2),flush=True)
    except Exception as exc:
        print("WF01_REAL_CHAIN_FAILED",type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(1)
