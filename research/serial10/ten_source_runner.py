#!/usr/bin/env python3
"""Strictly sequential ten-original TradingView real-trade literature search.
A batch has ONE ChatGPT HITEL POST. Zero matching trading cases is valid.
The next batch may start only after validated result.json is committed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hitel_a_one_source as transport

ROOT = Path("research/serial10")
MANIFEST = ROOT / "source_manifest.json"
TOTAL, SIZE = 4428, 10
SCHEMA = "TV-TRADE-EVIDENCE-10-v1"
API = "/integrations/v1/public"
MAX_PROMPT = 20000
POLL_SECONDS = 10
MAX_WAIT_S = 16800

def hash_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def save(path, data):
    transport.save(path, data)

def source_rows():
    info = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (info.get("original_count"), info.get("batch_size"), info.get("expected_batches")) != (4428, 10, 443):
        raise ValueError("SOURCE_MANIFEST_COUNT_OR_BATCH_INVALID")
    paths = [Path(p) for p in info.get("chunk_files", [])]
    if len(paths) != 9:
        raise ValueError("EXPECTED_NINE_SOURCE_FILES")
    rows = []
    for p in paths:
        if not p.exists():
            raise FileNotFoundError("MISSING_TRADINGVIEW_MASTER_CHUNK " + str(p))
        rows.extend(json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
    if len(rows) != TOTAL:
        raise ValueError("EXPECTED_4428_GOT_" + str(len(rows)))
    ids = []
    for i, row in enumerate(rows, 1):
        rid = row.get("id")
        if row.get("order") != i or not isinstance(rid, str) or len(rid) != 8:
            raise ValueError("SOURCE_ORDER_OR_ID_INVALID_" + str(i))
        if not str(row.get("url") or "").startswith("https://www.tradingview.com/script/" + rid):
            raise ValueError("SOURCE_URL_INVALID_" + str(i))
        if not isinstance(row.get("description_preview"), str):
            raise ValueError("MISSING_ORIGINAL_DESCRIPTION_" + str(i))
        ids.append(rid)
    if len(set(ids)) != TOTAL or ids[:3] != ["02yfhjiz", "03zgCMqx", "04erUlJM"] or ids[-1] != "zzLiSsEc":
        raise ValueError("SOURCE_MISSING_DUPLICATE_OR_REORDERED")
    return rows

def batch_rows(rows, batch_no):
    if not 1 <= batch_no <= (len(rows) + SIZE - 1) // SIZE:
        raise ValueError("INVALID_BATCH")
    start = (batch_no - 1) * SIZE
    return rows[start:start + SIZE]

def prompt_for(group, batch_no):
    src = [{
        "source_order": r["order"], "script_id": r["id"],
        "title": r["title"], "url": r["url"], "author": r["author"],
        "description_preview": r["description_preview"][:1100],
        "pine_full_verified": False
    } for r in group]
    question = (
        "실제 거래 사례를 찾는 전문 조사 AI에게 하나의 질문을 보냅니다. "
        "이번 질문의 TradingView Strategy 원본 %d개 모두를 각각 조사하고, "
        "해당 응답을 완성한 후 JSON 객체 하나만 반환하십시오. "
        "원본 순번 %d~%d (A/B 등급 확정 아님), 전체 Pine 코드는 미검증입니다. 원본 목록: %s\n"
        "가장 중요한 목적: 실제 실거래 사례·실제 경제적 거래 사건·실제 시장 데이터로 "
        "진입/청산이 재구성되는 백테스트를 찾는 것입니다. 지표 이름이 비슷한 일반 이론 논문은 제외하십시오. "
        "우선순위: 1) 거래소·브로커·공시로 체결을 입증할 수 있는 실거래, "
        "2) 가격·시간·주체·계약이 있는 실제 경제 거래 사건, "
        "3) 실물 시장 데이터/거래비용/매매 규칙을 명시한 구체적 실증 거래·백테스트. "
        "각 실제 사례의 출처 원문 제목·출판 기관·URL·자산명·기간·진입/청산·거래수/손익·"
        "경제적 수익손실 원인·논문 표/절·전문 접근 여부를 확보하십시오. "
        "논문 원문 미열람이면 절/수익률을 지어내지 말고 초록만 확인이라고 적으십시오. "
        "실제 체결과 모의 백테스트를 혼동하지 말고, 상품 현물·선물·외환·코인·옵션을 구별하십시오. "
        "결과 사례 개수를 강제하지 않습니다. 출처 확인되는 사례가 0건인 원본도 빈 cases 배열로 저장하십시오. "
        "하지만 원본 수만큼 source_results 항목은 빠짐없이 반환하십시오. "
        "근거 미확인 후보는 exclusions에 기록하십시오. "
        "지식그래프·전략구현·Pine 변환·새로운 가짜 백테스트는 수행하지 마십시오.\n"
        "최종 응답은 마크다운/코드펜스 없이 JSON 객체 1개만: "
        '{"schema":"TV-TRADE-EVIDENCE-10-v1","batch_number":%d,"source_results":['
        '{"source_order":1,"script_id":"원본8자리","title":"원본제목",'
        '"research_status":"SEARCHED|PARTIAL|NO_WEB_ACCESS","search_queries":["검색어"],'
        '"cases":[{"case_type":"EXECUTED_TRADE|MARKET_TRANSACTION_EVENT|HISTORICAL_DATA_BACKTEST",'
        '"title":"실제 논문/사례제목","publisher":"기관",'
        '"document_url":"https://실제URL","instrument":"자산/종목",'
        '"trade_period":"기간","transaction_evidence":"실제 거래·데이터 근거",'
        '"entry_exit":"진입/청산","reported_numbers":"실제 보고된 수치 또는 미확인",'
        '"economic_mechanism":"왜 수익·손실이 발생하는지",'
        '"evidence_location":"원문표/절/초록","access_level":"FULL_TEXT|ABSTRACT_ONLY|PUBLIC_SUMMARY",'
        '"relationship_to_source":"원본과 연결되는 거래구조",'
        '"limitations":"실체결/모의/원본과 다른점"}],'
        '"exclusions":[{"title":"후보","reason":"실거래·데이터 근거 부재 등"}],'
        '"limitations":"원문 검증 범위"}],"research_only":true}. '
        "위 JSON의 source_order=1은 예시일 뿐입니다. 실제 10개 원본의 ID·제목·순번을 원본 목록과 정확히 일치시키십시오. "
        "없는 거래 근거나 URL을 만들지 마십시오."
    ) % (len(group), group[0]["order"], group[-1]["order"],
         json.dumps(src, ensure_ascii=False, separators=(",", ":")), batch_no)
    if len(question) > MAX_PROMPT:
        raise ValueError("PROMPT_GT_HITEL_LIMIT_" + str(len(question)))
    return question

def parse_reply(raw, group, batch_no):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("EMPTY_AI_REPLY")
    data = raw.strip()
    fence = chr(96) * 3
    if data.startswith(fence):
        lines = data.splitlines()
        if len(lines) < 3 or lines[-1].strip() != fence:
            raise ValueError("INCOMPLETE_FENCED_JSON")
        data = "\n".join(lines[1:-1]).strip()
    reply = json.loads(data)
    if not isinstance(reply, dict) or reply.get("schema") != SCHEMA or \
            reply.get("batch_number") != batch_no or reply.get("research_only") is not True:
        raise ValueError("INVALID_SCHEMA_OR_BATCH")
    listed = reply.get("source_results")
    if not isinstance(listed, list) or len(listed) != len(group):
        raise ValueError("TEN_SOURCE_ROWS_NOT_RETURNED")
    for wanted, got in zip(group, listed):
        if not isinstance(got, dict) or got.get("source_order") != wanted["order"] or \
                got.get("script_id") != wanted["id"] or got.get("title") != wanted["title"]:
            raise ValueError("SOURCE_ID_TITLE_ORDER_MISMATCH_" + wanted["id"])
        if got.get("research_status") not in ("SEARCHED", "PARTIAL", "NO_WEB_ACCESS"):
            raise ValueError("BAD_RESEARCH_STATUS")
        cases = got.get("cases")
        if not isinstance(cases, list) or (got["research_status"] == "NO_WEB_ACCESS" and cases):
            raise ValueError("CASE_LIST_OR_SEARCH_STATUS_INVALID")
        for case in cases:
            if not isinstance(case, dict) or case.get("case_type") not in (
                "EXECUTED_TRADE", "MARKET_TRANSACTION_EVENT", "HISTORICAL_DATA_BACKTEST"):
                raise ValueError("BAD_TRADE_CASE_TYPE")
            if not str(case.get("title") or "").strip() or \
                    not str(case.get("document_url") or "").startswith("https://"):
                raise ValueError("CASE_TITLE_OR_DOCUMENT_URL_MISSING")
            if not str(case.get("transaction_evidence") or "").strip() or \
                    not str(case.get("economic_mechanism") or "").strip():
                raise ValueError("MISSING_TRADE_EVIDENCE_OR_MECHANISM")
            if case.get("access_level") not in ("FULL_TEXT", "ABSTRACT_ONLY", "PUBLIC_SUMMARY"):
                raise ValueError("CASE_SOURCE_ACCESS_UNVERIFIED")
    return reply

def result_summary(reply, group, batch_no, state):
    counts = [len(x["cases"]) for x in reply["source_results"]]
    return {
        "batch_number": batch_no,
        "source_first": group[0]["order"], "source_last": group[-1]["order"],
        "source_ids": [x["id"] for x in group],
        "source_count": len(group), "case_counts": counts,
        "total_cases": sum(counts), "zero_case_sources": sum(n == 0 for n in counts),
        "job_id": state.get("job_id"), "request_id": state.get("request_id"),
        "status": "AI_RESULT_SCHEMA_CHECK_PASSED",
        "independent_real_trade_proof_verified": False
    }

def execute(batch_no, root, dry_run=False, wait_seconds=MAX_WAIT_S):
    rows = source_rows()
    group = batch_rows(rows, batch_no)
    prompt = prompt_for(group, batch_no)
    if dry_run:
        print(json.dumps({"batch":batch_no,"originals":len(group),
            "ids":[x["id"] for x in group], "prompt_chars":len(prompt),
            "max_batches":443},ensure_ascii=False))
        return
    target = root / f"batch_{batch_no:04d}"
    target.mkdir(parents=True, exist_ok=True)
    already_committed = ROOT / "results" / f"batch_{batch_no:04d}.json"
    if already_committed.is_file():
        data = json.loads(already_committed.read_text(encoding="utf-8"))
        parse_reply(json.dumps(data,ensure_ascii=False),group,batch_no)
        save(target/"result.json",data)
        save(target/"summary.json",{"batch_number":batch_no,
            "already_committed":True,"total_cases":sum(len(x["cases"]) for x in data["source_results"])})
        print("ALREADY_COMMITTED_NO_POST",batch_no,flush=True)
        return
    room_name = f"TV-SERIAL10-REALCASE-20261120-B{batch_no:04d}"
    request_id = "tv-serial10-" + hash_text(room_name + "|" + prompt)[:45]
    state_path = target/"state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if state and (state.get("request_id") != request_id or
                  state.get("prompt_sha") != hash_text(prompt) or
                  state.get("batch_number") != batch_no):
        raise ValueError("CHECKPOINT_NOT_SAME_EXACT_REQUEST")
    state.update({"batch_number":batch_no,"source_ids":[x["id"] for x in group],
                  "request_id":request_id,"prompt_sha":hash_text(prompt),"room_name":room_name})
    save(state_path,state)
    (target/"prompt.txt").write_text(prompt,encoding="utf-8")
    if (target/"result.json").is_file():
        data=json.loads((target/"result.json").read_text(encoding="utf-8"))
        parse_reply(json.dumps(data,ensure_ascii=False),group,batch_no)
        print("CHECKPOINT_HAS_VERIFIED_RESULT_NO_POST",batch_no,flush=True)
        return
    if (target/"result.raw.txt").is_file():
        data=parse_reply((target/"result.raw.txt").read_text(encoding="utf-8"),group,batch_no)
        save(target/"result.json",data)
        save(target/"summary.json",result_summary(data,group,batch_no,state))
        state["phase"]="RESULT_VALIDATED"
        save(state_path,state)
        return
    if state.get("phase") in ("FAILED","STALLED","SUBMISSION_UNCERTAIN"):
        raise RuntimeError("PREVIOUS_TERMINAL_OR_UNCERTAIN_DO_NOT_REPOST")
    if not state.get("room_id"):
        state["room_id"]=transport.open_named_room(room_name,target)
        state["phase"]="ROOM_READY"
        save(state_path,state)
    if not state.get("job_id"):
        state["phase"]="SUBMISSION_UNCERTAIN"
        save(state_path,state)
        # Exactly one HTTP POST /chat; no automatic duplicate submissions.
        code,resp=transport.post(API+"/chat",{
            "room_id":state["room_id"],"request_id":request_id,"text":prompt
        })
        if code!=202 or not isinstance(resp.get("job_id"),str) or \
                resp.get("room_id")!=state["room_id"]:
            raise RuntimeError("HITEL_CHAT_NOT_ACKNOWLEDGED")
        state["job_id"]=resp["job_id"]
        state["phase"]="POLLING"
        save(state_path,state)
        print("TEN_ORIGINAL_ONE_CHAT_ACCEPTED",batch_no,state["job_id"],flush=True)
    else:
        print("SAME_SAVED_JOB_ID_NO_POST",batch_no,state["job_id"],flush=True)
    deadline=time.monotonic()+wait_seconds
    last=None
    while time.monotonic()<deadline:
        try:
            status_code,job=transport.get(API+"/jobs/"+state["job_id"])
        except (urllib.error.URLError,TimeoutError) as error:
            state["last_poll_error"]=type(error).__name__
            save(state_path,state)
            time.sleep(POLL_SECONDS)
            continue
        if status_code!=200 or job.get("job_id")!=state["job_id"] or \
                job.get("room_id") not in (None,state["room_id"]):
            raise RuntimeError("JOB_OR_ROOM_MISMATCH")
        status,stage=job.get("status"),job.get("stage")
        audit={"at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
               "batch_number":batch_no,"job_id":state["job_id"],
               "status":status,"stage":stage}
        with (target/"poll_audit.jsonl").open("a",encoding="utf-8") as fh:
            fh.write(json.dumps(audit,ensure_ascii=False)+"\n")
        state["last_poll"]=audit
        save(state_path,state)
        if (status,stage)!=last:
            print("HITEL_10_POLL",json.dumps(audit,ensure_ascii=False),flush=True)
            last=(status,stage)
        if status=="completed":
            raw=job.get("result_text")
            if not isinstance(raw,str) or not raw.strip():
                c,resp=transport.get(API+"/jobs/"+state["job_id"]+"/result")
                if c==200:
                    raw=resp.get("result_text") or resp.get("text") or resp.get("response_text")
            if not isinstance(raw,str) or not raw.strip():
                state["phase"]="COMPLETED_NO_RESULT_TEXT"
                save(state_path,state)
                raise RuntimeError("HITEL_COMPLETED_BUT_NO_RETRIEVABLE_TEXT")
            (target/"result.raw.txt").write_text(raw,encoding="utf-8")
            state["phase"]="RAW_PRESERVED"
            save(state_path,state)
            reply=parse_reply(raw,group,batch_no)
            save(target/"result.json",reply)
            save(target/"summary.json",result_summary(reply,group,batch_no,state))
            state["phase"]="RESULT_VALIDATED"
            save(state_path,state)
            print("BATCH_10_RESULT_SAVED",batch_no,
                  sum(len(x["cases"]) for x in reply["source_results"]),flush=True)
            return
        if status in ("stalled","failed","cancelled"):
            state["phase"]="STALLED" if status=="stalled" else "FAILED"
            state["error"]=str(job.get("error") or stage or "unknown")[:600]
            save(state_path,state)
            raise RuntimeError("HITEL_TERMINAL_"+str(status)+": "+state["error"])
        time.sleep(POLL_SECONDS)
    state["phase"]="POLL_TIMEOUT_SAME_JOB_ID"
    save(state_path,state)
    raise TimeoutError("HITEL_UNFINISHED_JOB_ID="+state["job_id"])

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--batch",type=int,required=True)
    parser.add_argument("--output-dir",default="serial10-checkpoints")
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--wait-seconds",type=int,default=MAX_WAIT_S)
    args=parser.parse_args()
    if not 1<=args.wait_seconds<=MAX_WAIT_S:
        raise ValueError("INVALID_WAIT_TIME")
    execute(args.batch,Path(args.output_dir),args.dry_run,args.wait_seconds)
