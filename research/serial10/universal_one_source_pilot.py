"""One-source live pilot using the existing, server-authorized stock-tv producer.
No automatic bulk handoff; immutable checkpoint is pushed before any POST.
"""
import hashlib,json,os,pathlib,subprocess,sys,time,urllib.error
ROOT=pathlib.Path.cwd()
LEGACY=ROOT/"legacy"
SOURCE=ROOT/"universal_source"/"universal"
sys.path.insert(0,str(LEGACY/"research/serial10"))
import task_isolated_client as transport
sys.path.insert(0,str(SOURCE))
import engine
PID="stocktv-cases-20261127-0001-p01-v2"
D=LEGACY/"research/serial10/fresh_runs/universal_one_source"
STATE=D/"state.json"
BRANCH="feature/stocktv-web2api-fresh-reset-20261121"
def git(*args):
    return subprocess.check_output(["git","-C",str(LEGACY),*args],text=True)
def persist(s):
    transport.atomic(STATE,s)
    git("add",str(D.relative_to(LEGACY)))
    if subprocess.run(["git","-C",str(LEGACY),"diff","--cached","--quiet"]).returncode:
        git("commit","-m","Preserve one-source stock-tv pilot "+s["status"])
        git("push","origin","HEAD:"+BRANCH)
def validate_nested(row):
    lists={}
    for k in ("papers_json","cases_json","candidate_cases_json","rejection_log_json","search_log_json"):
        v=json.loads(row[k])
        if not isinstance(v,list) or any(not isinstance(x,dict) for x in v):
            raise ValueError("invalid array "+k)
        lists[k]=v
    for key,field in (("papers_json","paper_count"),("cases_json","case_count"),("candidate_cases_json","candidate_count")):
        if row[field]!=len(lists[key]):raise ValueError("count mismatch "+field)
    papers=lists["papers_json"];cases=lists["cases_json"]
    ids=[x.get("paper_id") for x in papers]
    if any(not isinstance(x,str) or not x for x in ids) or len(set(ids))!=len(ids):raise ValueError("paper id")
    cids=[x.get("case_id") for x in cases]
    if any(not isinstance(x,str) or not x for x in cids) or len(set(cids))!=len(cids):raise ValueError("case id")
    for x in cases:
        parent=x.get("parent_paper_id")
        if parent and parent not in ids:raise ValueError("unknown parent")
        if not str(x.get("original_url","")).startswith("https://") or not x.get("evidence_location") or not x.get("evidence_kind"):raise ValueError("case evidence missing")
    if row["paper_case_count"]!=sum(bool(x.get("parent_paper_id")) for x in cases):raise ValueError("paper case count")
    if row["research_status"] not in ("SEARCH_EXECUTED_AND_ASSESSED","PARTIAL_SOURCE_ACCESS","SEARCH_NOT_EXECUTED"):raise ValueError("research status")
    return lists
def main():
    git("config","user.name","stocktv-universal-pilot[bot]")
    git("config","user.email","github-actions[bot]@users.noreply.github.com")
    p=json.loads((SOURCE/"projects"/PID/"project.json").read_text())
    assert p["provider"]=="hitel" and p["command"]=="start" and len(p["records"])==1 and p["records"][0]["record_id"]=="02yfhjiz"
    text=engine.prompt(p,p["records"])
    h=hashlib.sha256(text.encode()).hexdigest()
    s=json.loads(STATE.read_text()) if STATE.exists() else {"project_id":PID,"provider":"hitel","task_id":"stock-tv","request_id":"stock-tv-universal-pilot-"+h[:40],"room_name":"TV-UNIVERSAL-PILOT-"+h[:24],"prompt_sha256":h,"record_id":"02yfhjiz","status":"ready","attempted":False,"verified_ai_completed":0}
    assert s["prompt_sha256"]==h and s["task_id"]=="stock-tv"
    if s["status"] in ("needs_evidence_review","continuation_required","search_not_executed"):return
    j=transport.resolve_immutable_request(s)
    if j is None:
        if s["attempted"]:raise RuntimeError("Prior request uncertain; no new POST")
        health=transport.get(transport.API+"/isolated/tasks/stock-tv/status")
        if not health.get("worker_available_for_new_job"):raise RuntimeError("Existing stock-tv worker not available")
        s.update(status="request_prepared",attempted=True);persist(s)
        try:j=transport.post_isolated({"request_id":s["request_id"],"room_name":s["room_name"],"text":text})
        except urllib.error.HTTPError as exc:
            s.update(status="submit_http_error",http_status=exc.code);persist(s);raise
    if j.get("request_id")!=s["request_id"] or j.get("task_id")!="stock-tv" or not str(j.get("job_id","")).startswith("job_") or not str(j.get("room_id","")).startswith("room_"):raise RuntimeError("response identity")
    s.update(status="accepted",job_id=j["job_id"],room_id=j["room_id"]);persist(s)
    deadline=time.monotonic()+1000
    while time.monotonic()<deadline:
        r=transport.get(transport.API+"/jobs/"+s["job_id"])
        if any(r.get(k)!=s[k] for k in ("job_id","request_id","room_id")):raise RuntimeError("job identity")
        if r.get("status")=="completed":
            if not all(r.get(k) is True for k in ("result_ready","chatgpt_send_confirmed","assistant_reply_observed")):raise RuntimeError("completion proof")
            answer=transport.read_reply(s["job_id"],r)
            transport.atomic(D/"raw_result.json",{"answer":answer,"result_sha256":r["result_sha256"]})
            s.update(status="received",result_sha256=r["result_sha256"]);persist(s)
            rows=engine.check(answer,p["records"],p["fields"]);validate_nested(rows[0])
            transport.atomic(D/"results.json",{"provider":"hitel","results":rows,"verified_ai_completed":0,"note":"External source evidence has not yet been independently verified"})
            status="continuation_required" if rows[0]["has_more"] else ("needs_evidence_review" if rows[0]["research_status"]=="SEARCH_EXECUTED_AND_ASSESSED" else "search_not_executed")
            s.update(status=status);persist(s);return
        if r.get("status") not in ("queued","running","stalled"):s.update(status="terminal_unverified",remote_status=r.get("status"));persist(s);raise RuntimeError("terminal unverified")
        time.sleep(10)
    s.update(status="pending");persist(s)
if __name__=="__main__":main()
