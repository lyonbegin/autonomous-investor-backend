#!/usr/bin/env python3
"""Exactly one native HITEL ChatGPT WebSocket request per ten TradingView originals.
The next group is forbidden until the previous result is validated and committed.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys
from pathlib import Path
from urllib.request import urlopen

ROOT=Path("research/serial10")
SCHEMA="TV-TRADE-EVIDENCE-10-v2"
ROOM_PREFIX="HITEL-STOCKTV-RESEARCH-WS20261121-B"
BASE="https://hitel-integration-api-production.up.railway.app/integrations/v1/public"
PENDING={"sending","running","unverified"}
TYPES={"EXECUTED_TRADE","MARKET_TRANSACTION_EVENT","HISTORICAL_DATA_BACKTEST"}

def checksum(s):return hashlib.sha256(s.encode("utf-8")).hexdigest()
def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,path)

def originals():
    m=json.loads((ROOT/"source_manifest.json").read_text(encoding="utf-8"))
    if (m.get("original_count"),m.get("batch_size"),m.get("expected_batches"))!=(4428,10,443):
        raise ValueError("SOURCE_MANIFEST_CHANGED")
    rows=[]
    for p in m["chunk_files"]:
        rows.extend(json.loads(line) for line in Path(p).read_text(encoding="utf-8").split("\n") if line.strip())
    if len(rows)!=4428:raise ValueError("SOURCE_COUNT_MISMATCH")
    ids=[]
    for i,row in enumerate(rows,1):
        sid=row.get("id")
        if row.get("order")!=i or not isinstance(sid,str) or not re.fullmatch("[A-Za-z0-9]{8}",sid):
            raise ValueError("SOURCE_ORDER_OR_ID_"+str(i))
        if not row.get("url","").startswith("https://www.tradingview.com/script/"+sid):
            raise ValueError("SOURCE_URL_"+str(i))
        if not isinstance(row.get("title"),str) or not isinstance(row.get("description_preview"),str):
            raise ValueError("SOURCE_METADATA_"+str(i))
        ids.append(sid)
    if len(set(ids))!=4428 or ids[:3]!=["02yfhjiz","03zgCMqx","04erUlJM"] or ids[-1]!="zzLiSsEc":
        raise ValueError("SOURCE_DUPLICATE_OR_CHANGED")
    return rows

def group(rows,batch):
    if not 1<=batch<=443:raise ValueError("BATCH_INVALID")
    return rows[(batch-1)*10:batch*10]

def room_name(batch):return ROOM_PREFIX+f"{batch:04d}"

def question(group_rows,batch):
    src=[{"source_order":r["order"],"script_id":r["id"],"title":r["title"],"url":r["url"],
          "author":r["author"],"description_preview":r["description_preview"][:850],
          "full_pine_verified":False} for r in group_rows]
    prompt=(
        "실제 금융거래 사례 조사입니다. TradingView Strategy 원본 %d개, 순번 %d~%d 각각을 "
        "별도 검색하고 이번 질문에 대한 JSON 한 개만 반환하십시오.\n원본:%s\n"
        "우선순위: (1) 거래소·브로커·공시로 실체결이 입증되는 거래, "
        "(2) 자산·기간·가격·거래당사자 및 경제 구조를 확인할 수 있는 실제 거래 사건, "
        "(3) 실제 시장가격 데이터로 날짜별 진입·청산·성과를 확인할 수 있는 실증 백테스트입니다. "
        "기술지표 설명이나 키워드만 비슷한 논문·초록은 제외하십시오. 원문을 읽지 못했다면 "
        "FULL_TEXT로 표시하지 말고 수치와 문헌 절을 만들지 마십시오. "
        "각 사례는 원문 제목·발행기관·접근 URL·자산군·실거래/모의 유형·기간·체결 또는 "
        "진입청산 근거·손익/거래비용·경제적 거래 메커니즘·근거 페이지/절을 포함하십시오. "
        "10개 원본 모두를 source_results에 넣으십시오. 실제 사례 0개여도 cases 빈 배열로 "
        "보고하고 억지 후보는 exclusions에 넣으십시오. 검색 한계를 적으십시오. "
        "주식·ETF·코인과 선물·금·외환·옵션을 혼동하지 마십시오. "
        "지식그래프·Pine 변환·코드 구현·새 백테스트는 수행하지 마십시오.\n"
        "필수 단일 JSON:"
        '{"schema":"TV-TRADE-EVIDENCE-10-v2","batch_number":%d,"research_only":true,'
        '"source_results":[{"source_order":1,"script_id":"원본ID","title":"원본제목",'
        '"research_status":"SEARCHED|PARTIAL|NO_WEB_ACCESS","search_queries":["검색어"],'
        '"cases":[{"case_type":"EXECUTED_TRADE|MARKET_TRANSACTION_EVENT|HISTORICAL_DATA_BACKTEST",'
        '"title":"원문제목","publisher":"발행기관","document_url":"https://실제URL",'
        '"instrument":"거래대상","trade_period":"기간 또는 미확인",'
        '"transaction_evidence":"실체결/실제자료 근거",'
        '"entry_exit":"진입청산 또는 미확인","reported_numbers":"수치 또는 미확인",'
        '"economic_mechanism":"실제 거래구조",'
        '"evidence_location":"원문표/절 또는 미확인",'
        '"access_level":"FULL_TEXT|ABSTRACT_ONLY|PUBLIC_SUMMARY",'
        '"relationship_to_source":"원본과의 연결","limitations":"증거 한계"}],'
        '"exclusions":[{"title":"제외 후보","reason":"제외 이유"}],'
        '"limitations":"검색 또는 원문 열람 한계"}]}. '
        "source_order=1은 자리표시자입니다. 실제 순번·원본 ID·제목을 그대로 사용하고 "
        "JSON 이외 텍스트를 반환하지 마십시오."
    )%(len(group_rows),group_rows[0]["order"],group_rows[-1]["order"],
         json.dumps(src,ensure_ascii=False,separators=(",",":")),batch)
    if len(prompt)>24000:raise ValueError("PROMPT_EXCEEDS_SERVER_LIMIT")
    return prompt

def validate(raw,group_rows,batch):
    if not isinstance(raw,str) or not raw.strip():raise ValueError("EMPTY_REPLY")
    s=raw.strip()
    fence=chr(96)*3
    if s.startswith(fence):
        lines=s.splitlines()
        if len(lines)<3 or not lines[-1].strip().startswith(fence):
            raise ValueError("INCOMPLETE_FENCED_REPLY")
        s="\n".join(lines[1:-1]).strip()
    obj=json.loads(s)
    if not isinstance(obj,dict) or obj.get("schema")!=SCHEMA or obj.get("batch_number")!=batch or obj.get("research_only") is not True:
        raise ValueError("WRONG_BATCH_SCHEMA")
    answers=obj.get("source_results")
    if not isinstance(answers,list) or len(answers)!=len(group_rows):
        raise ValueError("MISSING_SOURCE_RESULTS")
    for src,ans in zip(group_rows,answers):
        if not isinstance(ans,dict) or (ans.get("source_order"),ans.get("script_id"),ans.get("title"))!=(src["order"],src["id"],src["title"]):
            raise ValueError("SOURCE_SCOPE_MISMATCH_"+src["id"])
        if ans.get("research_status") not in ("SEARCHED","PARTIAL","NO_WEB_ACCESS"):
            raise ValueError("INVALID_SOURCE_STATUS")
        if not isinstance(ans.get("search_queries"),list) or not isinstance(ans.get("exclusions"),list):
            raise ValueError("MISSING_RESEARCH_PROVENANCE")
        cases=ans.get("cases")
        if not isinstance(cases,list) or (ans["research_status"]=="NO_WEB_ACCESS" and cases):
            raise ValueError("BAD_CASE_LIST")
        for c in cases:
            if not isinstance(c,dict) or c.get("case_type") not in TYPES or c.get("access_level") not in ("FULL_TEXT","ABSTRACT_ONLY","PUBLIC_SUMMARY"):
                raise ValueError("BAD_CASE_TYPE_OR_ACCESS")
            for k in ("title","publisher","document_url","instrument","trade_period","transaction_evidence",
                      "entry_exit","reported_numbers","economic_mechanism","evidence_location",
                      "relationship_to_source","limitations"):
                if not isinstance(c.get(k),str) or not c[k].strip():
                    raise ValueError("CASE_FIELD_MISSING_"+k)
            if not c["document_url"].startswith("https://"):
                raise ValueError("CASE_DOCUMENT_URL_INVALID")
    return obj

def verify_previous(rows,batch):
    if batch==1:return
    p=ROOT/"results"/f"batch_{batch-1:04d}.json"
    if not p.exists():raise RuntimeError("PREVIOUS_BATCH_NOT_PERSISTED_NO_NEXT_SEND")
    validate(p.read_text(encoding="utf-8"),group(rows,batch-1),batch-1)
    print("PREVIOUS_BATCH_PERSISTED_AND_VALIDATED",batch-1,flush=True)

def preflight():
    with urlopen(BASE+"/status",timeout=15) as res: status=json.load(res)
    public={k:status.get(k) for k in ("worker_connected","worker_heartbeat_recent",
      "worker_bootstrap_ready","worker_available_for_new_job","worker_active_jobs_count","worker_capacity")}
    print("HITEL_WORKER_PREFLIGHT",json.dumps(public,ensure_ascii=False),flush=True)
    if status.get("worker_available_for_new_job") is not True:
        raise RuntimeError("WORKER_NOT_READY_NO_CHAT_SEND")

def validate_capacity_failure_without_chat_send(state):
    """Only a verified worker-tab allocation rejection permits a fresh recovery room.
    Generic timeout, dropped socket, or ambiguous answer can NEVER authorize resending.
    """
    jid=state.get("job_id")
    if not isinstance(jid,str) or not jid.startswith("job_"):
        raise RuntimeError("NO_PREVIOUS_JOB_ID_FOR_SAFE_RECOVERY")
    if state.get("status")!="unverified" or state.get("error_code")!="web2api_failed":
        raise RuntimeError("PREVIOUS_JOB_NOT_PROVEN_CAPACITY_FAILURE")
    with urlopen(BASE+"/jobs/"+jid,timeout=20) as resp:
        old=json.load(resp)
    if (old.get("job_id"),old.get("room_id"),old.get("request_id"))!=(
            jid,state.get("room_id"),state.get("request_id")):
        raise RuntimeError("REMOTE_REQUEST_SCOPE_MISMATCH_ABORT")
    if not (old.get("status")=="failed" and old.get("stage")=="web2api_failed"
            and old.get("error")=="ROOM_TAB_CAPACITY_EXCEEDED"
            and old.get("result_ready") is not True
            and old.get("chatgpt_send_confirmed") is not True
            and old.get("assistant_reply_observed") is not True):
        raise RuntimeError("NO_PROOF_REQUEST_FAILED_BEFORE_ANY_CHAT_SEND")
    return {k:old.get(k) for k in (
        "job_id","room_id","request_id","status","stage","error",
        "chatgpt_send_confirmed","assistant_reply_observed","result_ready")}

def execute(batch,out,client,dry_run=False,recover_capacity=False):
    rows=originals()
    verify_previous(rows,batch)
    selected=group(rows,batch)
    prompt=question(selected,batch)
    name=room_name(batch)
    print("SINGLE_BATCH_SCOPE",json.dumps({"batch":batch,"room_name":name,
       "source_first":selected[0]["order"],"source_last":selected[-1]["order"],
       "source_ids":[x["id"] for x in selected],"prompt_chars":len(prompt)},ensure_ascii=False),flush=True)
    if dry_run:return
    if not client.is_file():raise FileNotFoundError("OFFICIAL_HITEL_CLIENT_MISSING")
    done=ROOT/"results"/f"batch_{batch:04d}.json"
    if done.exists():
        validate(done.read_text(encoding="utf-8"),selected,batch)
        print("RESULT_ALREADY_COMMITTED_NO_SEND",batch,flush=True)
        return
    folder=out/f"batch_{batch:04d}"
    folder.mkdir(parents=True,exist_ok=True)
    intent_path=folder/"intent.json";state_path=folder/"client_state.json"
    intent={"batch":batch,"room_name":name,
            "source_ids":[x["id"] for x in selected],
            "prompt_sha256":checksum(prompt),"transport":"HITEL_PUBLIC_WEBSOCKET"}
    if intent_path.exists():
        if json.loads(intent_path.read_text(encoding="utf-8"))!=intent:
            raise RuntimeError("CHECKPOINT_IDENTITY_MISMATCH")
    else:atomic(intent_path,intent)
    (folder/"prompt.txt").write_text(prompt,encoding="utf-8")
    # An explicit manual recovery may change the room ONLY if the server proves
    # a terminal ROOM_TAB_CAPACITY_EXCEEDED before any ChatGPT send. Preserve
    # the original job/client_state.json and immutable recovery audit.
    recovery_state=folder/"client_state_capacity_recovery1.json"
    recovery_proof=folder/"capacity_recovery1_verified.json"
    if recover_capacity and not recovery_proof.exists():
        initial=json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        proof=validate_capacity_failure_without_chat_send(initial)
        atomic(recovery_proof,proof)
        print("PROVEN_NO_MODEL_SEND_CAPACITY_FAILURE_RECOVERY_ALLOWED",proof["job_id"],flush=True)
    if recovery_proof.exists():
        if not (folder/"client_state.json").exists():
            raise RuntimeError("RECOVERY_PROOF_WITHOUT_ORIGINAL_CHECKPOINT")
        name=room_name(batch)+"-CAPACITY-RECOVERY1"
        state_path=recovery_state
    state=json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if state and (state.get("room_name")!=name or state.get("text_sha256") not in (None,checksum(prompt))):
        raise RuntimeError("SAVED_CLIENT_STATE_WRONG_ROOM_OR_PROMPT")
    if state.get("status")=="completed":
        answer=state.get("answer")
        print("RECOVER_ALREADY_COMPLETED_NATIVE_REPLY_NO_SEND",batch,flush=True)
    else:
        if state.get("status") in PENDING:
            command=[sys.executable,str(client),"--state",str(state_path),"--resume"]
            print("SAME_REQUEST_READ_ONLY_RESUME",batch,state.get("job_id"),flush=True)
        elif state:
            raise RuntimeError("PREVIOUS_STATE_UNRESOLVED_NO_NEW_SEND")
        else:
            preflight()
            command=[sys.executable,str(client),"--room",name,"--state",str(state_path),"--text",prompt]
            print("NEW_WEBSOCKET_CHAT_SEND_ONE_BATCH",batch,name,flush=True)
        result=subprocess.run(command,stdout=subprocess.DEVNULL,check=False)
        if result.returncode:
            recent=json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
            print("HITEL_NATIVE_REPLY_NOT_VERIFIED",json.dumps({
                "status":recent.get("status"),"job_id":recent.get("job_id"),
                "room_id":recent.get("room_id"),"error_code":recent.get("error_code")},ensure_ascii=False),flush=True)
            raise RuntimeError("NATIVE_CLIENT_NOT_COMPLETED_NO_NEXT_BATCH")
        state=json.loads(state_path.read_text(encoding="utf-8"))
        answer=state.get("answer")
    if state.get("status")!="completed" or not isinstance(answer,str) or checksum(answer)!=state.get("sha256"):
        raise RuntimeError("NATIVE_REPLY_SHA256_NOT_VERIFIED")
    (folder/"result.raw.txt").write_text(answer,encoding="utf-8")
    parsed=validate(answer,selected,batch)
    atomic(folder/"result.json",parsed)
    counts=[len(x["cases"]) for x in parsed["source_results"]]
    atomic(folder/"summary.json",{
      "batch":batch,"source_count":len(selected),"first":selected[0]["order"],
      "last":selected[-1]["order"],"case_counts":counts,"total_cases":sum(counts),
      "zero_case_sources":sum(n==0 for n in counts),"job_id":state.get("job_id"),
      "room_id":state.get("room_id"),"request_id":state.get("request_id"),
      "reply_sha256":state["sha256"],
      "verification":"native_sha256_and_source_order","independently_confirmed_real_trades":False})
    print("BATCH_NATIVE_REPLY_SHA256_AND_SOURCE_SCOPE_VERIFIED",batch,"cases",sum(counts),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--batch",type=int,required=True)
    p.add_argument("--out",default="stock-ws10-checkpoints")
    p.add_argument("--client",default="hitel-client/tools/hitel_chat.py")
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--recover-capacity-no-send",action="store_true",help="Explicitly create a new room ONLY after verifying remote worker rejected the previous job before ChatGPT send")
    p.add_argument("--verify-file")
    a=p.parse_args()
    if not 1<=a.batch<=443:raise ValueError("BATCH_INVALID")
    if a.verify_file:
        validate(Path(a.verify_file).read_text(encoding="utf-8"),
                 group(originals(),a.batch),a.batch)
        print("PERSISTED_TEN_BATCH_IDENTITY_VALIDATED",a.batch,flush=True)
    else:execute(a.batch,Path(a.out),Path(a.client),a.dry_run,a.recover_capacity_no_send)

if __name__=="__main__":main()
