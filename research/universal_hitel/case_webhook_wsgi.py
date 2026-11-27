"""Optional stock-side HITEL Universal webhook receiver (WSGI app).

A deployment must mount application at /api/stocktv/hitel-events and set
HITEL_EVENT_WEBHOOK_SECRET plus STOCKTV_EVENT_DB_PATH to durable storage.
This does not register a webhook at GitHub, deploy a server, or send to ChatGPT.
Only the stock service owns this code; upstream Universal is untouched.
"""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time

ENDPOINT = "/api/stocktv/hitel-events"
ALLOWED_EVENT_NAMES = {
    "project.started", "request.prepared", "request.accepted",
    "batch.verified", "project.pending", "project.paused",
    "project.blocked", "project.completed", "heartbeat",
}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
MAX_BODY = 24000
SKEW_SECONDS = 300


def verify(raw, headers, secret, now=None):
    if not secret:
        raise ValueError("Receiver secret not configured")
    if not isinstance(raw, bytes) or not (0 < len(raw) <= MAX_BODY):
        raise ValueError("Invalid event size")
    event_id = headers.get("X-HITEL-Event-ID", "")
    signature = headers.get("X-HITEL-Signature", "")
    raw_ts = headers.get("X-HITEL-Timestamp", "")
    if not HEX64.fullmatch(event_id) or not raw_ts.isdigit():
        raise ValueError("Invalid event headers")
    t = int(raw_ts)
    if abs((time.time() if now is None else now) - t) > SKEW_SECONDS:
        raise ValueError("Webhook timestamp out of range")
    mac = hmac.new(secret.encode(), raw_ts.encode() + b"." + raw,
                   hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, "sha256=" + mac):
        raise ValueError("Webhook HMAC mismatch")
    p = json.loads(raw)
    if not isinstance(p, dict) or p.get("schema") != "hitel.progress.v1":
        raise ValueError("Unknown event schema")
    if p.get("event_id") != event_id:
        raise ValueError("Event identifier mismatch")
    if p.get("event") not in ALLOWED_EVENT_NAMES:
        raise ValueError("Unknown event name")
    if p.get("provider") != "hitel" or not str(
            p.get("project_id", "")).startswith("stocktv-cases-"):
        raise ValueError("Not an approved TradingView evidence project")
    if not isinstance(p.get("verified_ai_completed"), int):
        raise ValueError("Missing verified AI count")
    return p


def save(db_path, payload):
    if not db_path or db_path == ":memory:":
        raise RuntimeError("A persistent STOCKTV_EVENT_DB_PATH is required")
    with sqlite3.connect(db_path, timeout=15) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS events
                      (event_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                       event_name TEXT NOT NULL, occurred_at TEXT NOT NULL,
                       verified_count INTEGER NOT NULL, raw_payload TEXT NOT NULL)""")
        row = (payload["event_id"], payload["project_id"], payload["event"],
               str(payload.get("occurred_at", "")),
               payload["verified_ai_completed"],
               json.dumps(payload, ensure_ascii=False, sort_keys=True))
        cursor = db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)", row)
        db.commit()
        return cursor.rowcount == 1


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD")
    path = environ.get("PATH_INFO", "")
    if method != "POST" or path != ENDPOINT:
        start_response("404 Not Found", [("Content-Type", "application/json")])
        return [b'{"error":"not_found"}']
    try:
        n = int(environ.get("CONTENT_LENGTH", "0"))
        if n <= 0 or n > MAX_BODY:
            raise ValueError("Invalid Content-Length")
        stream = environ.get("wsgi.input")
        raw = stream.read(n)
        if len(raw) != n:
            raise ValueError("Incomplete webhook body")
        headers = {
            "X-HITEL-Event-ID": environ.get("HTTP_X_HITEL_EVENT_ID", ""),
            "X-HITEL-Timestamp": environ.get("HTTP_X_HITEL_TIMESTAMP", ""),
            "X-HITEL-Signature": environ.get("HTTP_X_HITEL_SIGNATURE", ""),
        }
        payload = verify(raw, headers, os.getenv("HITEL_EVENT_WEBHOOK_SECRET"))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        start_response("401 Unauthorized", [("Content-Type", "application/json")])
        return [b'{"error":"invalid_event"}']
    try:
        first = save(os.environ.get("STOCKTV_EVENT_DB_PATH", ""), payload)
    except (sqlite3.Error, RuntimeError):
        start_response("503 Service Unavailable", [("Content-Type", "application/json")])
        return [b'{"error":"persistence_unavailable"}']
    start_response("202 Accepted", [("Content-Type", "application/json")])
    return [json.dumps({"accepted": True, "duplicate": not first,
                        "event_id": payload["event_id"]}).encode()]


if __name__ == "__main__":
    raise SystemExit("Mount WSGI application in authorized existing stock service; no public debug server")
