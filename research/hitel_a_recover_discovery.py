#!/usr/bin/env python3
"""Resume exactly one A-group TradingView source after a restarted HITEL job.

A *new*, clearly-labelled recovery turn is sent to the ORIGINAL public room
only when the original job has definitely failed and its ChatGPT browser reply
cannot be retrieved using the public jobs API. It is not an identical replay.
All checkpoints and previous job IDs are preserved; no A/B reclassification.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hitel_a_one_source as kg

EXPECTED_ROOM = "STOCK-KG-A-RESEARCH-20261119-R3"
EXPECTED_ROOM_ID = "room_e43054eed81d46fba991b946ede92d1b"
ORIGINAL_JOB_ID = "job_60a34b62bf5f418fa44b202bc9461f42"
ORIGINAL_REQUEST_ID = "stock-a-kg-decf010fd3557bb8c55c7a242709ef7eab135cda"
ORIGINAL_JOB_FILE = "decf010fd3557bb8c55c7a24.json"

def checkpoint(out: Path, key: str, value):
    kg.save(out / key, value)

def run(src: dict, out: Path, per_stage_seconds: int, max_rounds: int) -> dict:
    if src.get("source_id") != "0LJUxO7T" or src.get("group") != "A":
        raise RuntimeError("ONLY_CONFIRMED_A_PILOT_0LJUxO7T")
    if src.get("official_a_order_verified") is not False or src.get("pine_source_status") != "NOT_VERIFIED":
        raise RuntimeError("SOURCE_PROVENANCE_CHANGED_REQUIRE_REVIEW")
    old_path = out / "jobs" / ORIGINAL_JOB_FILE
    if not old_path.exists():
        raise RuntimeError("ORIGINAL_JOB_CHECKPOINT_MISSING_REFUSE_NEW_SEND")
    old = json.loads(old_path.read_text("utf-8"))
    if (old.get("job_id") != ORIGINAL_JOB_ID
        or old.get("room_id") != EXPECTED_ROOM_ID
        or old.get("request_id") != ORIGINAL_REQUEST_ID
        or old.get("stage") != "0LJUxO7T-DISCOVER"):
        raise RuntimeError("ORIGINAL_JOB_IDENTITY_MISMATCH")
    previous_recovery = out / "recovery_status.json"
    prior = json.loads(previous_recovery.read_text("utf-8")) if previous_recovery.exists() else {}
    result = {
        "source_id": src["source_id"], "group": "A",
        "original_job_id": ORIGINAL_JOB_ID,
        "original_request_id": ORIGINAL_REQUEST_ID,
        "room_id": EXPECTED_ROOM_ID, "room_name": EXPECTED_ROOM,
        "next_source_allowed": False,
        "status": "CHECKING_ORIGINAL_JOB",
        "cases": [],
        "official_a_order_verified": False,
        "pine_full_verified": False,
        "source_completion_count": 0,
        "prior_recovery_status": prior.get("status"),
        "previous_recovery_job_id": prior.get("recovery_job_id"),
    }
    checkpoint(out, "recovery_status.json", result)
    code, obj = kg.get("/integrations/v1/public/jobs/" + ORIGINAL_JOB_ID)
    if code != 200 or obj.get("job_id") != ORIGINAL_JOB_ID:
        raise RuntimeError("ORIGINAL_JOB_NOT_VERIFIED")
    if obj.get("room_id") != EXPECTED_ROOM_ID or obj.get("room_name") != EXPECTED_ROOM:
        raise RuntimeError("ORIGINAL_JOB_ROOM_MISMATCH")
    result["original_job_api_status"] = obj.get("status")
    result["original_job_stage"] = obj.get("stage")
    result["original_job_error"] = obj.get("error")
    checkpoint(out,"recovery_status.json",result)

    if obj.get("status") == "completed":
        discovered = kg.parse_json(obj.get("result_text"))
        result["recovery_mode"] = "ORIGINAL_COMPLETED_FROM_API"
    elif obj.get("status") == "running" or obj.get("status") == "queued":
        result["status"] = "ORIGINAL_JOB_NOT_TERMINAL_DO_NOT_RESEND"
        checkpoint(out, "recovery_status.json", result)
        raise RuntimeError("ORIGINAL_JOB_STILL_RUNNING_NO_DUPLICATE_SEND")
    elif obj.get("status") == "failed":
        # Even a server_restarted failure does not prove the ChatGPT model never replied.
        # Public API cannot read conversation messages; ask for previous answer FIRST
        # in the same verified linked conversation, without repeating identical text.
        rooms_status, rooms_obj = kg.get("/integrations/v1/public/rooms")
        rows = rooms_obj.get("rooms", [])
        matched = [x for x in rows if x.get("room_id") == EXPECTED_ROOM_ID
                   and x.get("room_name") == EXPECTED_ROOM]
        if rooms_status != 200 or len(matched) != 1 or matched[0].get("conversation_linked") is not True:
            result["status"] = "NO_VERIFIED_LINK_TO_ORIGINAL_CONVERSATION"
            checkpoint(out, "recovery_status.json", result)
            raise RuntimeError("ORIGINAL_CONVERSATION_LINK_NOT_VERIFIED")
        result["duplicate_risk"] = "UNKNOWN_PREVIOUS_CHATGPT_REPLY_MAY_EXIST"
        result["recovery_mode"] = "DISTINCT_FOLLOWUP_IN_VERIFIED_ORIGINAL_ROOM"
        checkpoint(out, "recovery_status.json", result)
        facts_path = Path("research/sources/0LJUxO7T_published_description_facts.json")
        facts = json.loads(facts_path.read_text("utf-8"))
        prompt = (
            "[복구확인 2차: 기존 답변 우선] 기존 A그룹 0LJUxO7T 연구 방의 후속 요청입니다. "
            "새 A/B 분류를 하지 마십시오. 직전 연구 요청은 서버 재시작으로 API에서 failed가 되었으나 "
            앞선 복구 질문도 Web2API HTTP 500으로 API 회수에 실패했습니다. "
            "기존 대화의 앞선 질문/답변이 이미 존재한다면 새 후보를 다시 발굴하지 말고 해당 답변을 요약·복원하십시오. "
            "이 방의 직전 연구 답변이 이미 있다면 그 답변에서 사례 후보 결과를 복구하여 반환하십시오. "
            "답변이 없다면 제공된 TradingView 게시 설명의 검증 사실만으로 연구 후보 0~N개를 도출하십시오. "
            "Pine 원문이 제공되지 않았으므로 source_access_status는 PREVIEW_ONLY입니다. "
            "중복·근거 없는 사례를 만들지 말고 5~6개로 억지로 채우지 마십시오. "
            "검증하지 못한 87개 전략과 추가 12개와의 관계는 임의로 연결하지 말고 배열을 비워두십시오. "
            "이 단계는 후보 발굴일 뿐 그래프·가역 검증 성공으로 선언하지 마십시오. "
            "JSON 객체 하나만 반환하며 3000자 이내로 작성하십시오. "
            "스키마: "
            '{"source_id":"0LJUxO7T","source_access_status":"PREVIEW_ONLY",'
            '"verified_source_refs":[],"cases":[{"case_id":"0LJUxO7T-C01",'
            '"kind":"...", "economic_mechanism":"...", "factual_evidence":[],'
            '"research_assumptions":[], "related_87":[], "related_12":[]}],'
            '"blockers":[],"research_summary":"..."} '
            "게시 설명 기반 확인 사실: " + kg.as_json(facts.get("source_facts", []))
        )
        # kg.ask uses a deterministic request_id and checkpoints before the POST.
        discovered = kg.ask(EXPECTED_ROOM_ID, "0LJUxO7T-DISCOVERY-RECOVERY-FOLLOWUP-V2-HTTP500-DIAG",
                            prompt, out, per_stage_seconds)
    else:
        raise RuntimeError("ORIGINAL_JOB_UNRECOGNIZED_STATUS_" + str(obj.get("status")))

    if discovered.get("source_id") != src["source_id"]:
        raise RuntimeError("RECOVERY_DISCOVERY_SOURCE_MISMATCH")
    cases = discovered.get("cases")
    if not isinstance(cases, list):
        raise RuntimeError("DISCOVERY_CASES_MUST_BE_LIST")
    ids = [str(c.get("case_id", "")) for c in cases if isinstance(c, dict)]
    if len(ids) != len(cases) or not all(ids) or len(set(ids)) != len(ids):
        raise RuntimeError("DUPLICATE_OR_INVALID_CASE_IDENTIFIERS")
    checkpoint(out, "discovery.json", discovered)
    result["discovered_case_count"] = len(cases)
    result["status"] = "DISCOVERY_RECOVERED_CASES_NOT_YET_REPLAYED"
    checkpoint(out, "recovery_status.json", result)

    for i, case in enumerate(cases):
        case_id = case["case_id"]
        folder = out / "cases" / ("%02d_" % (i+1) + kg.re.sub(r"[^A-Za-z0-9_-]", "_", case_id))
        folder.mkdir(parents=True, exist_ok=True)
        progress_file = folder / "case_status.json"
        progress = json.loads(progress_file.read_text("utf-8")) if progress_file.exists() else {
            "case_id": case_id, "status":"REBUILD_REQUIRED", "rounds":[]
        }
        if progress.get("status") in ("MODEL_REPORTED_REVERSIBLE", "MODEL_REPORTED_REVERSIBLE_NOT_PINE_VERIFIED"):
            result["cases"].append(progress)
            checkpoint(out, "recovery_status.json", result)
            continue
        last_failure = None
        for prev in reversed(progress["rounds"]):
            cmp_file = folder / ("comparison_" + str(prev["round"]) + ".json")
            if cmp_file.exists():
                last_failure = json.loads(cmp_file.read_text("utf-8"))
                break
        first_round = len(progress["rounds"]) + 1
        for round_no in range(first_round, first_round + max_rounds):
            graph = kg.ask(EXPECTED_ROOM_ID, case_id + "-GRAPH-R" + str(round_no),
                           kg.graph_prompt(src, case, round_no, last_failure),
                           out, per_stage_seconds)
            checkpoint(out, str((folder / ("graph_round_" + str(round_no) + ".json")).relative_to(out)), graph)
            structurally_valid, reason = kg.validate_graph(graph)
            if not structurally_valid:
                last_failure = {"overall":"FAIL","failure_matrix":[{"reason":reason}]}
                progress["rounds"].append({"round":round_no,"status":"GRAPH_INVALID","reason":reason})
                checkpoint(out,str(progress_file.relative_to(out)),progress)
                continue
            blind_name = f"STOCK-KG-A-BLIND-0LJUxO7T-{i+1:03d}-R{round_no}"
            blind_id = kg.open_named_room(blind_name,out)
            replay = kg.ask(blind_id,case_id+"-BLIND-R"+str(round_no),
                            kg.blind_prompt(graph),out,per_stage_seconds)
            checkpoint(out,str((folder/("reconstructed_"+str(round_no)+".json")).relative_to(out)),replay)
            compare = kg.ask(EXPECTED_ROOM_ID,case_id+"-COMPARE-R"+str(round_no),
                             kg.compare_prompt(src,case,graph,replay),out,per_stage_seconds)
            checkpoint(out,str((folder/("comparison_"+str(round_no)+".json")).relative_to(out)),compare)
            judge_pass = (compare.get("source_fact_coverage")=="PASS"
                          and compare.get("independent_blind_replay")=="PASS"
                          and compare.get("overall")=="PASS"
                          and not compare.get("failure_matrix")
                          and not compare.get("unverified_source_facts"))
            progress["rounds"].append({"round":round_no,"status":"MODEL_REPORTED_PASS" if judge_pass else "FAIL"})
            if judge_pass:
                progress["status"]="MODEL_REPORTED_REVERSIBLE_NOT_PINE_VERIFIED"
                checkpoint(out,str(progress_file.relative_to(out)),progress)
                break
            last_failure = compare
            checkpoint(out,str(progress_file.relative_to(out)),progress)
        result["cases"].append(progress)
        checkpoint(out,"recovery_status.json",result)

    result["status"] = "PINE_SOURCE_UNVERIFIED_DO_NOT_ADVANCE"
    result["case_count"] = len(cases)
    result["case_reported_reversible"] = sum(
        x["status"].startswith("MODEL_REPORTED_REVERSIBLE") for x in result["cases"])
    result["case_full_pine_replay_verified"] = 0
    result["case_incomplete"] = len(cases)
    result["next_source_allowed"] = False
    checkpoint(out,"recovery_status.json",result)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="research/queue/a_one_source_pilot.json")
    p.add_argument("--out",default="a-hitel-kg-output")
    p.add_argument("--poll-seconds",type=int,default=1200)
    p.add_argument("--max-rounds",type=int,default=2)
    args=p.parse_args()
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    src=json.loads(Path(args.input).read_text("utf-8"))
    try:
        result=run(src,out,args.poll_seconds,args.max_rounds)
        print("A_SOURCE_RECOVERY_RESULT",kg.as_json(result),flush=True)
    except Exception as ex:
        existing=out/"recovery_status.json"
        result=json.loads(existing.read_text("utf-8")) if existing.exists() else {}
        result["status"]="BLOCKED_PRESERVED_CHECKPOINT"
        result["last_error_type"]=type(ex).__name__
        result["last_error"]=str(ex)[:500]
        result["next_source_allowed"]=False
        checkpoint(out,"recovery_status.json",result)
        raise

if __name__=="__main__":
    main()
