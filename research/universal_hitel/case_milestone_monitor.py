#!/usr/bin/env python3
"""Read-only HITEL Universal API progress monitor for TradingView case collection.

One-shot process.  It does NOT run continuously, receive webhooks or notify
ChatGPT.  Receivers/Work tasks must invoke it when a real event arrives.
Only case-only provider=hitel work counts toward the 50-script milestones.
"""
import argparse
import json
import sys

try:
    from . import stocktv_universal_client as api
    from .validate_case_catalog import check_record
except ImportError:
    import stocktv_universal_client as api
    from validate_case_catalog import check_record

SOURCE_TOTAL = 4428
REPORT_INTERVAL = 50
SUPPORTED_EVENTS = (
    "project.started", "request.prepared", "request.accepted",
    "batch.verified", "project.pending", "project.paused",
    "project.blocked", "project.completed", "heartbeat",
)

def snapshot(read_content, project_ids, previous_milestone=0):
    """Return audit snapshot; never send notifications or change upstream state."""
    if previous_milestone < 0 or previous_milestone % REPORT_INTERVAL:
        raise ValueError("last milestone must be multiple of 50")
    ids = set()
    papers = cases = internal_cases = candidates = 0
    alerts = []
    events = []
    examined = set()
    pending_expansions = []
    for pid in project_ids:
        if pid in examined:
            continue
        examined.add(pid)
        _, project_bytes = read_content("universal/projects/" + pid + "/project.json")
        if project_bytes is None:
            alerts.append({"project_id": pid, "status": "NOT_REGISTERED"})
            continue
        project = json.loads(project_bytes)
        if project.get("project_id") != pid:
            raise ValueError("Project ID mismatch: " + pid)
        if project.get("provider") != "hitel":
            continue  # mock never counts
        if not {"papers_json", "cases_json", "paper_case_count"}.issubset(project.get("fields", {})):
            continue  # legacy strategy-research projects never count
        _, state_bytes = read_content("universal/state/" + pid + "/state.json")
        if state_bytes is None:
            alerts.append({"project_id": pid, "status": "NOT_STARTED"})
            continue
        state = json.loads(state_bytes)
        if state.get("provider") != "hitel":
            raise ValueError("State provider mismatch")
        if state.get("total") != len(project.get("records", [])):
            raise ValueError("Total does not match input project")
        verified = state.get("verified_ai_completed", 0)
        results = state.get("results", [])
        if verified != len(results):
            raise ValueError("Verified AI count mismatch in " + pid)
        expected = {x["record_id"] for x in project["records"]}
        seen_this = set()
        for row in results:
            rid = row["record_id"]
            if rid not in expected or rid in seen_this:
                raise ValueError("Unknown or duplicate record_id in " + pid)
            seen_this.add(rid)
            details = check_record(row)
            if details["has_more"]:
                pending_expansions.append({"project_id": pid, "record_id": rid,
                                           "reason": "CONTINUATION_REQUIRED"})
                continue
            if rid in ids:
                # Multiple research passes for one source must not inflate counts.
                continue
            ids.add(rid)
            papers += details["papers"]
            cases += details["cases"]
            internal_cases += details["paper_internal_cases"]
            candidates += details["candidates"]
        state_status = state.get("status")
        if state_status in ("blocked", "paused") or state.get("error"):
            alerts.append({"project_id": pid, "status": state_status,
                           "error": state.get("error", ""),
                           "no_progress": state.get("no_progress", 0)})
        _, event_bytes = read_content("universal/state/" + pid + "/events.json")
        if event_bytes:
            ledger = json.loads(event_bytes)
            for item in ledger.get("events", []):
                payload = item.get("payload", {})
                if payload.get("project_id") != pid:
                    continue
                events.append({"project_id": pid, "event": payload.get("event"),
                               "event_id": payload.get("event_id"),
                               "verified": payload.get("verified_ai_completed"),
                               "delivery": item.get("delivery"),
                               "run_url": payload.get("run_url")})

    n = len(ids)
    last = n // REPORT_INTERVAL * REPORT_INTERVAL
    reached = list(range(previous_milestone + REPORT_INTERVAL, last + 1, REPORT_INTERVAL))
    return {
        "scope": "TradingView original Strategy; confirmed unique record_id only",
        "total_source_records": SOURCE_TOTAL, "completed_unique_scripts": n,
        "percent": round(n * 100 / SOURCE_TOTAL, 3),
        "paper_count": papers, "case_count": cases,
        "paper_internal_case_count": internal_cases, "candidate_count": candidates,
        "last_reached_milestone": last, "new_milestones": reached,
        "pending_continuations": pending_expansions,
        "alerts": alerts, "recent_events": events[-30:],
        "automatic_chat_delivery": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", action="append", required=True,
                        help="Tracked case-only project ID, repeat per project")
    parser.add_argument("--last-reported", type=int, default=0,
                        help="Last user-confirmed milestone (0, 50, 100...)")
    args = parser.parse_args()
    output = snapshot(api.get_content, args.project_id, args.last_reported)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if output["alerts"]:
        print("ATTENTION: project errors or unstarted projects; see JSON", file=sys.stderr)


if __name__ == "__main__":
    main()
