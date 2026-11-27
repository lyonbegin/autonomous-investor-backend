#!/usr/bin/env python3
"""HITEL Universal event API consumer (no modifications to remote framework).

Safe notification configuration only changes project.notifications through
documented GitHub Contents API.  Webhook endpoint and secret must be
provisioned by the framework operator; this consumer does not pretend to
receive webhooks or notify ChatGPT.
"""
import argparse
import base64
import json

try:
    from . import stocktv_universal_client as api
except ImportError:
    import stocktv_universal_client as api

EVENTS = [
    "project.started", "request.prepared", "request.accepted",
    "batch.verified", "project.pending", "project.paused",
    "project.blocked", "project.completed", "heartbeat",
]


def notifications(channel, pr_number=None, heartbeat_seconds=60):
    if channel not in ("none", "webhook", "github_pr"):
        raise ValueError("Invalid HITEL channel")
    if not isinstance(heartbeat_seconds, int) or not 30 <= heartbeat_seconds <= 3600:
        raise ValueError("Heartbeat interval must be 30..3600 seconds")
    if channel == "github_pr" and (not isinstance(pr_number, int) or pr_number < 1):
        raise ValueError("Approved open PR number is required")
    item = {"channel": channel, "heartbeat_seconds": heartbeat_seconds,
            "events": EVENTS}
    if channel == "github_pr":
        item["pr_number"] = pr_number
    return item


def configure(project_id, channel, pr_number=None, heartbeat_seconds=60,
              apply=False, acknowledge_receiver_ready=False):
    if not api.PROJECT_ID.fullmatch(project_id):
        raise ValueError("Invalid project_id")
    meta, raw = api.get_content("universal/projects/" + project_id + "/project.json")
    if meta is None:
        raise RuntimeError("Project not registered")
    p = json.loads(raw)
    if p.get("project_id") != project_id:
        raise RuntimeError("Project identity mismatch")
    config = notifications(channel, pr_number, heartbeat_seconds)
    if channel != "none" and not acknowledge_receiver_ready:
        raise RuntimeError("External receiver/PR allowlist must be confirmed before enable")
    changed = p.get("notifications") != config
    if not apply:
        return {"project_id": project_id, "would_change": changed,
                "notification_settings": config, "applied": False}
    if not changed:
        return {"project_id": project_id, "already_configured": True, "applied": False}
    # Universal excludes notifications from immutable definition hash; touch
    # no other project fields. Use blob SHA to reject concurrent updates.
    p["notifications"] = config
    result_code, response = api.request(
        "PUT", "/contents/universal/projects/" + project_id + "/project.json",
        {"message": "Configure approved TradingView case progress events " + project_id,
         "branch": api.BRANCH, "sha": meta["sha"],
         "content": base64.b64encode((api.canonical(p) + "\n").encode()).decode()})
    if result_code != 200:
        raise RuntimeError("GitHub Contents notification update failed")
    return {"project_id": project_id, "applied": True,
            "commit_sha": response["commit"]["sha"], "notification_settings": config,
            "delivery_verified": False}


def events(project_id):
    if not api.PROJECT_ID.fullmatch(project_id):
        raise ValueError("Invalid project_id")
    _, raw = api.get_content("universal/state/" + project_id + "/events.json")
    if raw is None:
        return {"project_id": project_id, "events": [], "status": "NO_EVENTS_YET"}
    ledger = json.loads(raw)
    if ledger.get("project_id") != project_id:
        raise ValueError("Event ledger project mismatch")
    result = []
    seen = set()
    for item in ledger.get("events", []):
        payload = item.get("payload", {})
        event_id = payload.get("event_id")
        if not event_id or event_id in seen or payload.get("project_id") != project_id:
            continue
        seen.add(event_id)
        result.append({"event_id": event_id, "sequence": payload.get("sequence"),
                       "event": payload.get("event"),
                       "verified_ai_completed": payload.get("verified_ai_completed"),
                       "delivery": item.get("delivery"),
                       "run_url": payload.get("run_url"),
                       "occurred_at": payload.get("occurred_at")})
    return {"project_id": project_id, "events": result,
            "confirmed_deliveries": sum(e["delivery"] == "accepted" for e in result),
            "actual_chat_notifications_verified": False}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="op", required=True)
    c = sub.add_parser("configure", help="GET/CAS-PUT only project.notifications")
    c.add_argument("--project-id", required=True)
    c.add_argument("--channel", choices=("none", "webhook", "github_pr"), default="none")
    c.add_argument("--pr-number", type=int)
    c.add_argument("--heartbeat-seconds", type=int, default=60)
    c.add_argument("--apply", action="store_true")
    c.add_argument("--acknowledge-receiver-ready", action="store_true")
    e = sub.add_parser("events", help="Read event ledger with delivery evidence")
    e.add_argument("--project-id", required=True)
    args = p.parse_args()
    if args.op == "configure":
        result = configure(args.project_id, args.channel, args.pr_number,
                           args.heartbeat_seconds, args.apply,
                           args.acknowledge_receiver_ready)
    else:
        result = events(args.project_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
