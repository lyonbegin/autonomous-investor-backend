"""Save Pine code for subsequent Pine->Python conversion.

No author comparison, source URL ledger, or SHA field. Old DB tables remain
untouched to preserve users' existing imported source records.
"""
from contextlib import closing
from datetime import datetime, timezone
from investment_source_registry import open_registry

def save_verified_source(input_json,kind):
    candidate=input_json.get("candidate") or {}
    source_id=candidate.get("source_id")
    version=candidate.get("version_key")
    code=input_json.get("pine_code")
    if not source_id or not isinstance(version,str) or not isinstance(code,str) or not code.strip():
        raise ValueError("PINE_SOURCE_OR_ID_MISSING")
    created=datetime.now(timezone.utc).isoformat()
    with closing(open_registry()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS investment_pine_payloads (
          kind TEXT NOT NULL, source_id TEXT NOT NULL, version_key TEXT NOT NULL,
          pine_code TEXT NOT NULL, rights_state TEXT NOT NULL,
          saved_at TEXT NOT NULL, PRIMARY KEY(kind,source_id,version_key)
        )""")
        db.execute("BEGIN IMMEDIATE")
        try:
            row=db.execute("""SELECT pine_code FROM investment_pine_payloads
                WHERE kind=? AND source_id=? AND version_key=?""",
                (kind,source_id,version)).fetchone()
            if row and row["pine_code"]!=code:
                raise ValueError("PINE_VERSION_ALREADY_SAVED_WITH_DIFFERENT_CODE")
            if row:
                inserted=False
            else:
                # Never rewrite the historical source/version tables.
                db.execute("""INSERT INTO investment_pine_payloads
                    (kind,source_id,version_key,pine_code,rights_state,saved_at)
                    VALUES(?,?,?,?,?,?)""",
                    (kind,source_id,version,code,"PENDING_REVIEW",created))
                inserted=True
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {"source_saved":True,"source_created":inserted,"saved_count":int(inserted),
        "source_id":source_id,"version_key":version,
        "rights_state":"PENDING_REVIEW","conversion_validated":False,
        "tradingview_chart_validated":False}
