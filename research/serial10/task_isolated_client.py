#!/usr/bin/env python3
"""HITEL stock-tv task-isolated transport for the existing 4,428 Strategy corpus.

One request contains ten source records, never ten parallel questions.
This reuses ws_ten_runner.question/validate, not a new research engine.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import ws_ten_runner as source

TASK_ID = "stock-tv"
ROOT = "https://hitel-integration-api-production.up.railway.app"
API = "/integrations/v1/public"
SUBMIT_PATH = API + "/isolated/tasks/stock-tv/chat"
AUDIENCE = "urn:lyonbegin:procureflow:hitel-isolated-task-submit"
RESULT_ROOT = Path(os.environ.get("STOCK_TV_RESULT_DIR", "research/serial10/fresh_runs/isolated_stock_tv_r3/results"))
DEFAULT_OUT = Path("stock-tv-isolated-r3-checkpoints")
MAX_RESULT_BYTES = 2_000_000


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def atomic(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def get(path: str):
    req = urllib.request.Request(ROOT + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response)


def signed_oidc():
    url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not url.startswith("https://") or not token:
        raise RuntimeError("SIGNED_GITHUB_WORKFLOW_REQUIRED_NO_SEND")
    separator = "&" if "?" in url else "?"
    req = urllib.request.Request(
        url + separator + "audience=" + urllib.parse.quote(AUDIENCE, safe=""),
        headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as response:
        key = json.load(response).get("value")
    if not isinstance(key, str) or len(key) < 50:
        raise RuntimeError("OIDC_SIGNING_FAILED_NO_SEND")
    return key


def post_isolated(payload):
    token = signed_oidc()
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        ROOT + SUBMIT_PATH,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "X-HITEL-Producer-OIDC": token})
    with urllib.request.urlopen(req, timeout=55) as response:
        if response.status != 202:
            raise RuntimeError("TASK_SUBMISSION_NOT_ACCEPTED")
        return json.load(response)


def identity(batch, selected, prompt):
    # New reset epoch gets a genuinely new Railway room and immutable request.
    # R3 remains the test/backward-compatible default; no old job is replayed.
    epoch = os.environ.get("STOCK_TV_EPOCH", "r3").strip().lower()
    if epoch not in ("r3", "r4"):
        raise RuntimeError("INVALID_STOCK_TV_EPOCH")
    return {
        "task_id": TASK_ID,
        "batch_number": batch,
        "source_ids": [r["id"] for r in selected],
        "room_name": f"TV-STRATEGY-{epoch.upper()}-{batch:04d}",
        "request_id": f"stock-tv-{epoch}-{batch:04d}-{digest(prompt)[:40]}",
        "prompt_sha256": digest(prompt),
    }


def verify_previous(rows, batch):
    if batch == 1:
        return
    previous = RESULT_ROOT / f"batch_{batch-1:04d}.json"
    summary = RESULT_ROOT / f"batch_{batch-1:04d}.summary.json"
    if not previous.is_file() or not summary.is_file():
        raise RuntimeError("PREVIOUS_TEN_NOT_REMOTELY_COMMITTED")
    raw = previous.read_text(encoding="utf-8")
    source.validate(raw, source.group(rows, batch - 1), batch - 1)
    receipt = json.loads(summary.read_text(encoding="utf-8"))
    if receipt.get("batch") != batch - 1 or receipt.get("source_count") != len(source.group(rows,batch-1)):
        raise RuntimeError("PREVIOUS_RECEIPT_IDENTITY_MISMATCH")
    if receipt.get("result_sha256") != digest(raw):
        raise RuntimeError("PREVIOUS_RECEIPT_CHECKSUM_MISMATCH")


def resolve_immutable_request(state):
    """Read-only GET finds an already submitted job after an ambiguous POST."""
    try:
        d = get(API + "/requests/" + state["request_id"])
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if d.get("request_id") != state["request_id"] or not str(d.get("job_id", "")).startswith("job_"):
        raise RuntimeError("IMMUTABLE_LOOKUP_WRONG_REQUEST")
    if state.get("job_id") and state["job_id"] != d["job_id"]:
        raise RuntimeError("IMMUTABLE_JOB_CHANGED")
    return d


def read_reply(job_id, meta):
    direct = meta.get("result_text")
    if isinstance(direct, str):
        raw = direct
    else:
        result = bytearray()
        while True:
            chunk = get(API + "/jobs/" + job_id + "/result?offset=" + str(len(result)) + "&limit=65536")
            if chunk.get("job_id") != job_id or chunk.get("offset") != len(result):
                raise RuntimeError("RESULT_CHUNK_ID_OR_OFFSET_CHANGED")
            block = base64.b64decode(chunk["content_base64"], validate=True)
            if not block or len(block) != chunk.get("bytes_returned"):
                raise RuntimeError("RESULT_CHUNK_CORRUPT")
            result.extend(block)
            if len(result) > MAX_RESULT_BYTES:
                raise RuntimeError("RESULT_TOO_LARGE")
            if chunk.get("complete") is True:
                break
        raw = result.decode("utf-8")
    if len(raw.encode("utf-8")) != meta.get("result_length_bytes"):
        raise RuntimeError("RESULT_BYTE_LENGTH_MISMATCH")
    if digest(raw) != meta.get("result_sha256"):
        raise RuntimeError("RESULT_HASH_MISMATCH")
    return raw


def execute(batch, out, poll_seconds=10, max_seconds=15600, resume_only=False, dry_run=False):
    rows = source.originals()
    selected = source.group(rows, batch)
    prompt = source.question(selected, batch)
    identity_record = identity(batch, selected, prompt)
    print("ONE_QUESTION_TEN_STRATEGIES", json.dumps({
        "batch": batch, "first": selected[0]["order"], "last": selected[-1]["order"],
        "source_ids": identity_record["source_ids"], "prompt_chars": len(prompt),
        "task_id": TASK_ID}, ensure_ascii=False), flush=True)
    if dry_run:
        return
    verify_previous(rows, batch)
    committed = RESULT_ROOT / f"batch_{batch:04d}.json"
    if committed.exists():
        source.validate(committed.read_text(encoding="utf-8"), selected, batch)
        print("ALREADY_SAVED_NO_NEW_SEND", batch, flush=True)
        return
    folder = out / f"batch_{batch:04d}"
    state_file = folder / "client_state.json"
    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if any(state.get(k) != v for k, v in identity_record.items()):
            raise RuntimeError("PREVIOUS_CHECKPOINT_IDENTITY_CHANGED")
    else:
        if resume_only:
            raise RuntimeError("RESUME_REQUIRES_PREVIOUS_CHECKPOINT")
        state = {**identity_record, "phase": "RESERVED", "post_attempted": False}
        atomic(state_file, state)

    if not state.get("job_id"):
        previous = resolve_immutable_request(state)
        if previous:
            state["job_id"] = previous["job_id"]
            state["room_id"] = previous["room_id"]
            state["phase"] = "ACCEPTED"
            atomic(state_file, state)
        elif resume_only or state.get("post_attempted"):
            raise RuntimeError("UNKNOWN_DELIVERY_NO_SECOND_QUESTION")
        else:
            # Durable marker BEFORE POST. An ambiguous response must never generate a new request_id.
            state["phase"] = "SUBMITTING"
            state["post_attempted"] = True
            atomic(state_file, state)
            payload = {"request_id": state["request_id"],
                       "room_name": state["room_name"], "text": prompt}
            try:
                reply = post_isolated(payload)
            except urllib.error.HTTPError as exc:
                # These responses are rejected before a task job is created.
                # Preserve proof and stop instead of treating them as an ambiguous send.
                if exc.code in (401, 403, 404, 422):
                    state["phase"] = "PRODUCER_REJECTED_NO_JOB"
                    state["error_http_status"] = exc.code
                    atomic(state_file, state)
                    raise RuntimeError("PRODUCER_AUTH_OR_API_REJECTED_NO_JOB") from None
                state["phase"] = "UNKNOWN_DELIVERY"
                state["last_http_status"] = exc.code
                atomic(state_file, state)
                raise RuntimeError("POST_OUTCOME_UNKNOWN_RESOLVE_BY_GET_ONLY") from None
            except Exception as exc:
                state["phase"] = "UNKNOWN_DELIVERY"
                state["last_error_class"] = type(exc).__name__
                atomic(state_file, state)
                raise RuntimeError("POST_OUTCOME_UNKNOWN_RESOLVE_BY_GET_ONLY") from None
            if (reply.get("accepted") is not True or reply.get("task_id") != TASK_ID
                    or reply.get("request_id") != state["request_id"]
                    or not str(reply.get("job_id", "")).startswith("job_")):
                state["phase"] = "UNKNOWN_DELIVERY"
                atomic(state_file, state)
                raise RuntimeError("TASK_PRODUCER_REPLY_SCOPE_MISMATCH")
            state["job_id"] = reply["job_id"]
            state["room_id"] = reply.get("room_id")
            state["phase"] = "ACCEPTED"
            atomic(state_file, state)
            print("STOCK_TV_TASK_ACCEPTED", state["job_id"], flush=True)

    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        try:
            job = get(API + "/jobs/" + state["job_id"])
        except (urllib.error.URLError, TimeoutError):
            time.sleep(poll_seconds)
            continue
        if job.get("job_id") != state["job_id"] or job.get("request_id") != state["request_id"]:
            raise RuntimeError("JOB_RESULT_SCOPE_MISMATCH")
        if state.get("room_id") and job.get("room_id") != state["room_id"]:
            raise RuntimeError("JOB_RESULT_ROOM_MISMATCH")
        status = job.get("status")
        if status == "completed" and job.get("result_ready") is True:
            raw = read_reply(state["job_id"], job)
            parsed = source.validate(raw, selected, batch)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "result.raw.txt").write_text(raw, encoding="utf-8")
            atomic(folder / "result.json", parsed)
            answer = (folder / "result.json").read_text(encoding="utf-8")
            atomic(folder / "summary.json", {
                "task_id": TASK_ID, "batch": batch,
                "first": selected[0]["order"], "last": selected[-1]["order"],
                "source_count": len(selected),
                "case_counts": [len(x["cases"]) for x in parsed["source_results"]],
                "total_cases": sum(len(x["cases"]) for x in parsed["source_results"]),
                "job_id": state["job_id"], "room_id": job.get("room_id"),
                "request_id": state["request_id"],
                "reply_sha256": digest(raw), "result_sha256": digest(answer),
                "validation": "server_verified_reply_sha256_and_all_original_source_ids",
                "independently_verified_trade_facts": False})
            state["phase"] = "VERIFIED_LOCALLY"
            atomic(state_file, state)
            print("STOCK_TV_FULL_TEN_VERIFIED", batch, flush=True)
            return
        if status == "failed":
            state["phase"] = "TERMINAL_FAILED"
            state["error_code"] = job.get("error_code")
            atomic(state_file, state)
            raise RuntimeError("TASK_JOB_TERMINAL_FAILURE_NO_NEXT_TEN")
        # queued/running/unknown/stalled remain read-only observations.
        time.sleep(poll_seconds)
    state["phase"] = "WAITING_GET_ONLY"
    atomic(state_file, state)
    raise RuntimeError("TIMED_OUT_EXISTING_JOB_SAFE_TO_RESUME_GET_ONLY")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batch", type=int, required=True)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--poll-seconds", type=int, default=10)
    p.add_argument("--max-seconds", type=int, default=15600)
    p.add_argument("--resume-only", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verify-file")
    args = p.parse_args()
    if not 1 <= args.batch <= 443:
        raise ValueError("BATCH_OUT_OF_RANGE")
    if args.verify_file:
        rows = source.originals()
        source.validate(Path(args.verify_file).read_text(encoding="utf-8"),
                        source.group(rows, args.batch), args.batch)
        print("FULL_TEN_RESEARCH_JSON_VALIDATED", args.batch, flush=True)
        return
    execute(args.batch, args.out, args.poll_seconds, args.max_seconds, args.resume_only, args.dry_run)


if __name__ == "__main__":
    main()
