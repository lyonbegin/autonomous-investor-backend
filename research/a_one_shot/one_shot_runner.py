#!/usr/bin/env python3
"""Exactly one A-original -> exactly one HITEL ChatGPT research message -> one final JSON."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hitel_a_one_source as transport

CONTRACT_DIR = Path(__file__).resolve().parent
ROOM_NAME = "STOCK-KG-A-ONE-SHOT-20261119"
EXPECTED_A_COUNT = 1814
MAX_PROMPT = 19500

def digest(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def read_manifest(path, expected=EXPECTED_A_COUNT):
    path = Path(path)
    if not path.is_file():
        raise RuntimeError("OFFICIAL_A_MANIFEST_MISSING: do not invent A #1..#1814")
    rows = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]
    if len(rows) != expected:
        raise RuntimeError(f"OFFICIAL_A_COUNT_NOT_VERIFIED: expected={expected}, got={len(rows)}")
    ids = set()
    for pos, row in enumerate(rows, 1):
        if row.get("group") != "A" or row.get("a_order") != pos or row.get("official_a_source_verified") is not True:
            raise RuntimeError(f"OFFICIAL_A_ORDER_NOT_VERIFIED: row={pos}")
        sid = row.get("source_id", "")
        if not re.fullmatch(r"[A-Za-z0-9]{8}", sid) or sid in ids:
            raise RuntimeError(f"BAD_OR_DUPLICATE_SOURCE_ID: row={pos}")
        if row.get("source_type") not in ("strategy", "indicator") or not str(row.get("url","")).startswith("https://www.tradingview.com/script/"):
            raise RuntimeError(f"INVALID_TRADINGVIEW_METADATA: row={pos}")
        ids.add(sid)
    return rows

def compose_prompt(source):
    instructions = (CONTRACT_DIR/"ONE_SHOT_CONTRACT.md").read_text("utf-8")
    schema = json.loads((CONTRACT_DIR/"result_schema.json").read_text("utf-8"))
    # No claim of verified Pine if a source code string is absent or the hash differs.
    source = dict(source)
    pine = source.get("pine_source") or ""
    sha = source.get("pine_source_sha256")
    if pine and sha and digest(pine) != sha:
        raise RuntimeError("PINE_SHA256_MISMATCH")
    source["pine_verified_by_input"] = bool(pine and sha and digest(pine) == sha)
    prompt = (
        "연구 대상은 이미 확정된 A그룹 원본 단 한 건입니다. 질문을 중간에 나누지 마십시오. "
        "제공된 문서가 아닌 내용을 지어내지 마십시오. 내부 검증이 실패하면 그래프를 완전히 다시 작성하십시오. "
        "최종에는 지정 JSON 객체 한 개만 반환하십시오.\n\n"
        "[전체 연구 지시서]\n" + instructions + "\n\n"
        "[검증할 최종 JSON Schema]\n" +
        json.dumps(schema, ensure_ascii=False, separators=(",",":")) + "\n\n"
        "[해당 A 원본 + 실제 제공된 기존 전략/관계/온톨로지 문맥]\n" +
        json.dumps(source, ensure_ascii=False, separators=(",",":")) +
        "\n[마지막 확인] 전체 Pine 미확보 시 완료 선언 금지. 별도 세션 독립 블라인드 검증은 "
        "수행되지 않았으므로 independent_blind_verified=false. 모든 파생 사례별 최종 그래프, "
        "복원 및 비교·실패 수정회차를 누락하지 마십시오."
    )
    if len(prompt) > MAX_PROMPT:
        raise RuntimeError(f"PROMPT_TOO_LARGE_FOR_ONE_HITEL_REQUEST length={len(prompt)} limit={MAX_PROMPT}")
    return prompt

def schema_errors(value, schema):
    errors = []
    def visit(data, shape, path="result"):
        if "const" in shape and data != shape["const"]:
            errors.append(path+":const")
        if "enum" in shape and data not in shape["enum"]:
            errors.append(path+":enum")
        ty = shape.get("type")
        if ty:
            types = ty if isinstance(ty,list) else [ty]
            matches = {"object":lambda x:isinstance(x,dict),"array":lambda x:isinstance(x,list),
                       "string":lambda x:isinstance(x,str),"integer":lambda x:type(x)==int,
                       "boolean":lambda x:type(x)==bool,"null":lambda x:x is None}
            if not any(matches[t](data) for t in types):
                errors.append(path+":type")
                return
        if isinstance(data,dict):
            missing = set(shape.get("required",[]))-set(data)
            if missing: errors.append(path+":missing:"+",".join(sorted(missing)))
            fields=shape.get("properties",{})
            if shape.get("additionalProperties") is False and set(data)-set(fields):
                errors.append(path+":extra")
            for key in set(data)&set(fields):
                visit(data[key],fields[key],path+"."+key)
        if isinstance(data,list) and "items" in shape:
            for i,v in enumerate(data):
                visit(v,shape["items"],f"{path}[{i}]")
        if isinstance(data,(int,float)) and "minimum" in shape and data < shape["minimum"]:
            errors.append(path+":minimum")
        if isinstance(data,str) and "minLength" in shape and len(data)<shape["minLength"]:
            errors.append(path+":minLength")
    visit(value,schema)
    return errors

def check_final_reply(result, src):
    schema = json.loads((CONTRACT_DIR/"result_schema.json").read_text("utf-8"))
    errors = schema_errors(result,schema)
    if result.get("source_id") != src["source_id"] or result.get("a_order") != src["a_order"] or result.get("group") != "A":
        errors.append("REPLY_SOURCE_ID_ORDER_GROUP_MISMATCH")
    discovery=result.get("case_discovery") or {}
    cases=discovery.get("cases") or []
    summary=result.get("summary") or {}
    if not isinstance(cases,list) or not isinstance(summary,dict) or summary.get("total_cases") != len(cases) or discovery.get("cases_discovered") != len(cases):
        errors.append("CASE_COUNT_MISMATCH")
        cases=cases if isinstance(cases,list) else []
    passed=blocked=failed=0
    unique=set()
    for i,case in enumerate(cases):
        if not isinstance(case,dict):
            errors.append(f"CASE_{i}_NOT_OBJECT")
            continue
        cid=case.get("case_id")
        if not cid or cid in unique:errors.append(f"CASE_{i}_ID_INVALID")
        unique.add(cid)
        v=case.get("internal_verdict")
        passed+=(v=="SELF_CHECK_PASS")
        blocked+=(v=="BLOCKED")
        failed+=(v=="FAIL")
        graph=case.get("final_graph") or {}
        nodes=graph.get("nodes") or []
        edges=graph.get("edges") or []
        names=[x.get("id") for x in nodes if isinstance(x,dict)]
        if len(names)!=len(nodes) or len(names)!=len(set(names)) or not names or not edges:
            errors.append(f"CASE_{i}_EMPTY_OR_BROKEN_GRAPH")
        else:
            for edge in edges:
                if not isinstance(edge,dict) or edge.get("source") not in names or edge.get("target") not in names or not edge.get("relation"):
                    errors.append(f"CASE_{i}_DANGLING_EDGE")
                    break
        comparison=case.get("final_comparison") or {}
        if v=="SELF_CHECK_PASS":
            if case.get("unresolved") or not case.get("rounds") or case["rounds"][-1].get("verdict")!="SELF_CHECK_PASS":
                errors.append(f"CASE_{i}_FALSE_PASS_HISTORY")
            if comparison.get("source_coverage_pass") is not True or comparison.get("self_check_pass") is not True or not comparison.get("checks"):
                errors.append(f"CASE_{i}_FALSE_PASS_COMPARISON")
            if not case.get("factual_evidence") or not case.get("fact_register"):
                errors.append(f"CASE_{i}_MISSING_FACT_EVIDENCE")
            for item in comparison.get("checks",[]):
                if item.get("match") is not True:errors.append(f"CASE_{i}_CHECK_NOT_MATCHED")
    if (summary.get("internally_passed"),summary.get("blocked"),summary.get("incomplete")) != (passed,blocked,failed):
        errors.append("CASE_SUMMARY_COUNTS_MISMATCH")
    pine=src.get("pine_source") or ""
    pine_valid=bool(pine and src.get("pine_source_sha256")==digest(pine)
                    and src.get("pine_provenance_verified") is True)
    if not pine_valid:errors.append("PINE_FULL_SOURCE_UNVERIFIED")
    source_verification=result.get("source_verification") or {}
    if not pine_valid and source_verification.get("pine_verified"):
        errors.append("FALSE_PINE_VERIFICATION_CLAIM")
    if result.get("independent_blind_verified") is not False:
        errors.append("FALSE_INDEPENDENT_BLIND_CLAIM")
    if not bool(src.get("official_a_source_verified")):
        errors.append("OFFICIAL_A_CLASSIFICATION_NOT_PROVEN")
    for name in ("prior_87_catalog_excerpt","prior_12_catalog_excerpt","strategy_indicator_edges","ontology_definitions"):
        if name not in src:errors.append("MISSING_RESEARCH_CONTEXT:"+name)
    passed_all = bool(cases) and passed==len(cases) and not errors and summary.get("overall")=="INTERNAL_COMPLETE" and source_verification.get("pine_verified") is True and source_verification.get("pine_sha256")==src.get("pine_source_sha256")
    return {"status":"INTERNAL_COMPLETE" if passed_all else "HOLD_NOT_VERIFIED",
            "can_advance":bool(passed_all),"verification_level":"SAME_REQUEST_SELF_CHECK_NOT_INDEPENDENT",
            "schema_issues":errors,"cases":len(cases),"self_check_passed":passed}

def run(manifest, position, out, expected_count=EXPECTED_A_COUNT, dry_run=False):
    sources=read_manifest(manifest,expected_count)
    if position<1 or position>len(sources):raise RuntimeError("A_ORDER_OUT_OF_RANGE")
    src=sources[position-1]
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    prompt=compose_prompt(src)
    prompt_sha=digest(prompt)
    status_path=out/"state.json"
    prev=json.loads(status_path.read_text("utf-8")) if status_path.exists() else {}
    if prev and (prev.get("prompt_sha256")!=prompt_sha or prev.get("source_id")!=src["source_id"]):
        raise RuntimeError("RESTORED_CHECKPOINT_WRONG_SOURCE")
    state={**prev,"source_id":src["source_id"],"a_order":position,"group":"A",
           "prompt_sha256":prompt_sha,"next_source_allowed":False}
    transport.save(status_path,state)
    if dry_run:
        (out/"prompt.txt").write_text(prompt,encoding="utf-8")
        state["stage"]="DRY_RUN_NO_AI_REQUEST";transport.save(status_path,state)
        return state

    # ONE request, ONE final reply. POST only once; every later request is GET.
    # Save the raw result *before* JSON parse, ensuring malformed JSON is still
    # recoverable without another AI request.
    from time import monotonic, sleep
    import urllib.error
    room_name = ROOM_NAME
    state["request_id"] = "stock-a-oneshot-" + digest(room_name+"|"+src["source_id"]+"|"+prompt_sha)[:40]
    (out/"prompt.txt").write_text(prompt,encoding="utf-8")
    transport.save(status_path,state)
    if state.get("stage") in ("SUBMITTING_UNCERTAIN","FAILED","INVALID_JSON","BLOCKED"):
        raise RuntimeError("PREVIOUS_ATTEMPT_AMBIGUOUS_OR_FAILED_DO_NOT_REPEAT")
    if state.get("stage") == "VALIDATED":
        return state
    if not state.get("room_id"):
        room_id = transport.open_named_room(room_name,out)
        state["room_id"] = room_id
        transport.save(status_path,state)
    room_id=state["room_id"]
    if not state.get("job_id"):
        state["stage"]="SUBMITTING_UNCERTAIN"
        transport.save(status_path,state)
        code,accepted=transport.post("/integrations/v1/public/chat",{
            "room_id":room_id,"text":prompt,"request_id":state["request_id"]})
        if code != 202 or not accepted.get("job_id") or accepted.get("room_id") != room_id:
            state["stage"]="SUBMISSION_AMBIGUOUS"
            transport.save(status_path,state)
            raise RuntimeError("ONE_SHOT_CHAT_NOT_ACCEPTED_OR_ROOM_CHANGED")
        state["job_id"]=accepted["job_id"]
        state["stage"]="POLLING"
        transport.save(status_path,state)
    deadline=monotonic()+1200
    while monotonic()<deadline:
        try:
            status,reply=transport.get("/integrations/v1/public/jobs/"+state["job_id"])
        except (urllib.error.URLError, TimeoutError):
            sleep(5)
            continue
        if status != 200 or reply.get("job_id") != state["job_id"] or reply.get("room_id") != room_id:
            raise RuntimeError("ONE_SHOT_RESULT_JOB_OR_ROOM_MISMATCH")
        if reply.get("status")=="failed":
            state["stage"]="FAILED"
            state["last_job_error"]=str(reply.get("error",""))[:500]
            transport.save(status_path,state)
            raise RuntimeError("ONE_SHOT_FINAL_JOB_FAILED "+state["last_job_error"])
        if reply.get("status")=="completed":
            raw=reply.get("result_text")
            if not isinstance(raw,str) or not raw.strip():
                state["stage"]="INVALID_JSON"
                transport.save(status_path,state)
                raise RuntimeError("COMPLETED_BUT_EMPTY_RESULT_TEXT")
            (out/"result.raw.txt").write_text(raw,encoding="utf-8")
            state["stage"]="RAW_FINAL_REPLY_PRESERVED"
            transport.save(status_path,state)
            try:
                response=json.loads(raw)
                if not isinstance(response,dict):
                    raise ValueError("FINAL_JSON_OBJECT_REQUIRED")
            except Exception:
                state["stage"]="INVALID_JSON"
                transport.save(status_path,state)
                raise
            transport.save(out/"result.json",response)
            verdict=check_final_reply(response,src)
            transport.save(out/"validation.json",verdict)
            state.update({"stage":"VALIDATED","status":verdict["status"],
                          "next_source_allowed":verdict["can_advance"],"can_advance":verdict["can_advance"],
                          "case_count":verdict["cases"]})
            transport.save(status_path,state)
            return state
        sleep(5)
    state["stage"]="POLL_TIMEOUT_JOB_PRESERVED"
    transport.save(status_path,state)
    raise TimeoutError("ONE_SHOT_JOB_UNFINISHED_PRESERVE_ID "+state["job_id"])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",default="research/a_one_shot/OFFICIAL_A_MANIFEST.jsonl")
    p.add_argument("--position",type=int,required=True)
    p.add_argument("--out",default="a-one-shot-output")
    p.add_argument("--dry-run",action="store_true")
    args=p.parse_args()
    try:
        result=run(args.manifest,args.position,args.out,dry_run=args.dry_run)
        print(json.dumps(result,ensure_ascii=False))
    except Exception as exc:
        out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
        state_path=out/"state.json"
        state=json.loads(state_path.read_text("utf-8")) if state_path.exists() else {}
        state.update({"stage":"BLOCKED_PRESERVE_CHECKPOINT","error_type":type(exc).__name__,
                      "error":str(exc)[:500],"next_source_allowed":False})
        transport.save(state_path,state)
        raise

if __name__=="__main__":
    main()
