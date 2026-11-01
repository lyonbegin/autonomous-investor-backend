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
        source=c["output_json"].get("catalog_source")
        check(c["status"]=="SUCCESS" and source in (
              "AUTHORIZED_EXTERNAL_FEED","PYNE_GITHUB_CC_BY_4_METADATA_SNAPSHOT"),
              f"N03 UNTRUSTED CATALOG SOURCE {c}")
        check(h3[0]["output_json"]==c["output_json"],"N03 DB OUTPUT MISMATCH")
        check(isinstance(c["output_json"]["items"],list) and len(c["output_json"]["items"])>0,
              "N03 EMPTY STRATEGY CATALOG IS NOT A SUCCESS")
        if source=="PYNE_GITHUB_CC_BY_4_METADATA_SNAPSHOT":
            check(c["output_json"]["catalog_is_live"] is False,
                  "HISTORICAL MANIFEST FALSELY CLAIMED LIVE TRADINGVIEW")
            check(c["output_json"]["pine_source_acquired"] is False,
                  "N03 MANIFEST FALSELY CLAIMED TO HAVE PINE CODE")
            check(c["output_json"]["manifest_sha256"] and
                  all(v["source_url"].startswith("https://www.tradingview.com/script/")
                      for v in c["output_json"]["items"]),
                  "MANIFEST PROVENANCE OR STRATEGY LINKS INVALID")
        t34=transfer(opener,n4,c["run_id"])
        check(t34["output_json"]==c["output_json"],"N03→N04 TRANSFER MISMATCH")
        state="N03_REAL_METADATA_SUCCESS_N04_INPUT_READY"
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
    if status==200:
        n5=PREFIX+"05"
        status4,d,ms4=call(opener,"POST","/api/studio/nodes/execute",
            {"workflow":WORKFLOW,"node_id":n4,"source_run_id":c["run_id"]},
            {"X-Studio-Node-Run":"APPROVED"})
        check(status4==200 and d.get("status")=="SUCCESS",f"N04 FAILED HTTP {status4}: {d}")
        check(d["upstream_run_id"]==c["run_id"],"N04 SOURCE EXECUTION ID MISMATCH")
        check(d["input_json"]==c["output_json"] and
              d["upstream_output_json"]==c["output_json"],
              "N04 ACTUAL INPUT != N03 ACTUAL OUTPUT")
        for key,value in c["output_json"].items():
            check(d["output_json"].get(key)==value,f"N04 DROPPED N03 FIELD: {key}")
        out4=d["output_json"]
        check(len(out4["candidates"])==out4["candidate_count"] and
              out4["candidate_count"]==c["output_json"]["count"],
              "N04 CANDIDATES COUNT NOT PRESERVED")
        check(out4["validated_catalog_is_snapshot"] is True and
              out4["latest_tradingview_checked"] is False and
              out4["next_page"]==2 and out4["max_pages"]==3,
              "N04 STALE OR FALSE LIVE PAGINATION")
        check(all(x["source_id"] and x["source_url"] and x["version_key"]
                  for x in out4["candidates"]), "N04 INVALID REAL CANDIDATES")
        h4=last_history(opener,n4)
        check(h4[0]["run_id"]==d["run_id"] and
              h4[0]["upstream_run_id"]==c["run_id"] and
              h4[0]["input_json"]==d["input_json"] and
              h4[0]["output_json"]==d["output_json"],
              "N04 DATABASE INPUT/OUTPUT OR LINEAGE MISMATCH")
        t45=transfer(opener,n5,d["run_id"])
        check(t45["output_json"]==d["output_json"] and t45["status"]=="READY",
              "N04→N05 FULL OUTPUT NOT READY")
        RECORDED.append({"node":"N04","status":"SUCCESS","http":status4,
             "run_id":d["run_id"],"upstream_run_id":c["run_id"],
             "input":d["input_json"],"output":d["output_json"],
             "elapsed_ms":ms4})
        state="N04_REAL_VALIDATION_SUCCESS_N05_INPUT_READY"
        print("N04 EXECUTED AND STORED",d["run_id"],"validated",out4["candidate_count"],"N05 READY",flush=True)
        n6=PREFIX+"06"
        status5,e,ms5=call(opener,"POST","/api/studio/nodes/execute",
            {"workflow":WORKFLOW,"node_id":n5,"source_run_id":d["run_id"]},
            {"X-Studio-Node-Run":"APPROVED"})
        check(status5==200 and e.get("status")=="SUCCESS",f"N05 FAILED HTTP {status5}: {e}")
        check(e["upstream_run_id"]==d["run_id"] and
              e["input_json"]==d["output_json"] and
              e["upstream_output_json"]==d["output_json"],
              "N05 DID NOT ACTUALLY RECEIVE N04 FULL OUTPUT")
        out5=e["output_json"]
        check(out5["registry_source"]=="project_owned_sqlite_pine_versions"
              and out5["source_registry_checked"] is True,
              "N05 NOT CHECKED AGAINST PROJECT SQLITE")
        check(out5["checked_count"]==d["output_json"]["candidate_count"] and
              out5["new_count"]+out5["imported_count"]==out5["checked_count"],
              "N05 DB CANDIDATE COUNTS MISMATCH")
        check(all(x["imported"] is False for x in out5["items"]),
              "N05 INVALID SOURCE: METADATA HASH WAS FALSELY MARKED AS STORED PINE")
        for key,value in d["output_json"].items():
            if key!="items":
                check(out5.get(key)==value,f"N05 DROPPED N04 FIELD {key}")
        check(out5["catalog_items"]==d["output_json"]["items"],
              "N05 LOST ORIGINAL SOURCE CATALOG ITEMS")
        h5=last_history(opener,n5)
        check(h5[0]["run_id"]==e["run_id"] and
              h5[0]["upstream_run_id"]==d["run_id"] and
              h5[0]["input_json"]==e["input_json"] and
              h5[0]["output_json"]==out5,
              "N05 REAL SQLITE INPUT/OUTPUT NOT PERSISTED")
        t56=transfer(opener,n6,e["run_id"])
        check(t56["output_json"]==out5 and t56["status"]=="READY",
              "N05→N06 ACTUAL OUTPUT NOT READY")
        RECORDED.append({"node":"N05","status":"SUCCESS","http":status5,
            "run_id":e["run_id"],"upstream_run_id":d["run_id"],
            "input":e["input_json"],"output":out5,"elapsed_ms":ms5})
        state="N05_REAL_REGISTRY_SUCCESS_N06_INPUT_READY"
        print("N05 EXECUTED AND STORED",e["run_id"],
              "registry checked",out5["checked_count"],"new",out5["new_count"],"N06 READY",flush=True)
        n7=PREFIX+"07"
        status6,g,ms6=call(opener,"POST","/api/studio/nodes/execute",
            {"workflow":WORKFLOW,"node_id":n6,"source_run_id":e["run_id"]},
            {"X-Studio-Node-Run":"APPROVED"})
        check(status6==200 and g.get("status")=="SUCCESS",f"N06 FAILED HTTP {status6}: {g}")
        check(g["upstream_run_id"]==e["run_id"] and
              g["input_json"]==out5 and
              g["upstream_output_json"]==out5,
              "N06 ACTUAL INPUT DID NOT MATCH N05 OUTPUT")
        out6=g["output_json"]
        for key,val in out5.items():
            check(out6.get(key)==val,f"N06 LOST UPSTREAM FIELD {key}")
        check(out6["has_candidate"] is True and
              out6["selected_candidate_count"]==1 and
              out6["candidate"]["source_id"]==out5["items"][0]["source_id"] and
              out6["pine_source_acquired"] is False,
              "N06 DID NOT SELECT EXACTLY ONE VALID UNIMPORTED METADATA CANDIDATE")
        h6=last_history(opener,n6)
        check(h6[0]["run_id"]==g["run_id"] and
              h6[0]["upstream_run_id"]==e["run_id"] and
              h6[0]["input_json"]==g["input_json"] and
              h6[0]["output_json"]==out6,
              "N06 SQLITE EXECUTION RECORD MISMATCH")
        t67=transfer(opener,n7,g["run_id"])
        check(t67["output_json"]==out6 and t67["status"]=="READY",
              "N06→N07 FULL OUTPUT NOT DELIVERED")
        RECORDED.append({"node":"N06","status":"SUCCESS","http":status6,
             "run_id":g["run_id"],"upstream_run_id":e["run_id"],
             "input":g["input_json"],"output":g["output_json"],"elapsed_ms":ms6})
        state="N06_ONE_REAL_CANDIDATE_SELECTED_N07_INPUT_READY"
        print("N06 EXECUTED ONE CANDIDATE",out6["candidate"]["source_id"],
              "N07 READY; SOURCE PINE NOT ACQUIRED",flush=True)
        n11=PREFIX+"11"
        n8=PREFIX+"08"
        status7,h,ms7=call(opener,"POST","/api/studio/nodes/execute",
             {"workflow":WORKFLOW,"node_id":n7,"source_run_id":g["run_id"]},
             {"X-Studio-Node-Run":"APPROVED"})
        check(status7==200 and h.get("status")=="SUCCESS",f"N07 IF EXECUTION FAILED: {status7} {h}")
        check(h["upstream_run_id"]==g["run_id"] and
              h["input_json"]==out6 and
              h["upstream_output_json"]==out6,
              "N07 ACTUAL IF INPUT != N06 OUTPUT")
        out7=h["output_json"]
        check(out7["_studio_active_ports"]==[0] and
              out7["condition_result"] is True and out7["has_candidate"] is True,
              "N07 WRONG TRUE/FALSE DECISION")
        h7=last_history(opener,n7)
        check(h7[0]["run_id"]==h["run_id"] and
              h7[0]["upstream_run_id"]==g["run_id"] and
              h7[0]["input_json"]==h["input_json"] and
              h7[0]["output_json"]==out7,
              "N07 SQLITE INPUT/OUTPUT OR PREDECESSOR RECORD MISMATCH")
        yes=transfer(opener,n11,h["run_id"])
        check(yes["output_json"]==out7 and yes["source_port"]==0,
              "TRUE BRANCH DID NOT DELIVER N07 OUTPUT TO N11")
        no_status,no_data,_=call(opener,"GET",query("/api/studio/nodes/transfers",n8))
        check(no_status==200 and not any(x["source_run_id"]==h["run_id"]
                    for x in no_data["transfers"]),
              "BUG: FALSE N08 BRANCH WAS ALSO MARKED READY")
        RECORDED.append({"node":"N07","status":"SUCCESS","http":status7,
              "run_id":h["run_id"],"upstream_run_id":g["run_id"],
              "input":h["input_json"],"output":out7,"elapsed_ms":ms7})
        state="N07_TRUE_BRANCH_N11_READY_FALSE_BRANCH_NOT_EXECUTED"
        print("N07 IF EXECUTED",h["run_id"],"TRUE→N11 READY, FALSE→N08 NOT READY",flush=True)
        n12=PREFIX+"12"
        status11,src,ms11=call(opener,"POST","/api/studio/nodes/execute",
            {"workflow":WORKFLOW,"node_id":n11,"source_run_id":h["run_id"]},
            {"X-Studio-Node-Run":"APPROVED"})
        check(status11 in (200,422),f"N11 SOURCE NODE HTTP {status11}: {src}")
        h11=last_history(opener,n11)
        check(h11[0]["run_id"]==src["run_id"] and
              h11[0]["upstream_run_id"]==h["run_id"] and
              h11[0]["input_json"]==out7,
              "N11 INPUT != ACTUAL SELECTED SOURCE OUTPUT")
        if status11==422:
            check(src["status"]=="FAILED" and
                  src["error"]=="N11_ORIGINAL_PINE_NOT_SUPPLIED" and
                  src["output_json"] is None,
                  "N11 DID NOT FAIL CLOSED FOR MISSING GENUINE PINE")
            st12,data12,_=call(opener,"GET",query("/api/studio/nodes/transfers",n12))
            check(st12==200 and not any(x["source_run_id"]==src["run_id"]
                for x in data12["transfers"]),
                "N12 RECEIVED DATA DESPITE N11 PINE SOURCE FAILURE")
            state="N11_BLOCKED_ORIGINAL_PINE_NOT_SUPPLIED_N12_NOT_EXECUTED"
        else:
            check(src["output_json"]["source_hash_verified"] is True and
                  src["output_json"]["pine_source_acquired"] is True,
                  "N11 FALSE PINE SOURCE SUCCESS")
            state="N11_GENUINE_SOURCE_HASH_VERIFIED_N12_INPUT_READY"
        RECORDED.append({"node":"N11","status":src["status"],"http":status11,
            "run_id":src["run_id"],"upstream_run_id":h["run_id"],
            "input":src["input_json"],"output":src["output_json"],
            "error":src.get("error"),"elapsed_ms":ms11})
        print("N11 SOURCE EXECUTION",state,src.get("error") or "HASH_VERIFIED",flush=True)
    return {"workflow":WORKFLOW,"result":state,"steps":RECORDED,
      "meaning":"N01,N02 real successes; N03 must be real approved feed or explicit FAILED, never synthetic."}

if __name__=="__main__":
    try:
        outcome=perform()
        print(json.dumps(outcome,ensure_ascii=False,indent=2),flush=True)
        # A safely rejected unauthorized or missing collector does NOT count
        # as successful end-to-end strategy collection.
        if os.environ.get("WF01_REQUIRE_N11_SUCCESS")=="1" and outcome["result"]!="N11_GENUINE_SOURCE_HASH_VERIFIED_N12_INPUT_READY":
            print("FIRST_STAGE_NOT_PASSED: N11 did not acquire actual matching Pine and therefore cannot pass to N12",file=sys.stderr,flush=True)
            sys.exit(3)
    except Exception as e:
        print("CHAIN_PROBE_FAILED",type(e).__name__,str(e),
              json.dumps(RECORDED,ensure_ascii=False),file=sys.stderr,flush=True)
        raise
