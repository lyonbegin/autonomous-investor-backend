"""Project-owned, real SQLite source-version check for WF01 N05.

N05 NEVER marks a strategy as imported based only on N03's metadata or
a reported SHA-256. Imported means the source itself was stored and verified
by a later intake step in this same project.
"""
import os
import sqlite3

def db_path():
    return os.environ.get("STUDIO_DB_PATH","/data/studio.sqlite3")

def open_registry():
    db=sqlite3.connect(db_path(),timeout=12)
    db.row_factory=sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS investment_pine_versions (
      kind TEXT NOT NULL,
      source_id TEXT NOT NULL,
      version_key TEXT NOT NULL,
      pine_sha256 TEXT NOT NULL,
      verified_source INTEGER NOT NULL DEFAULT 0,
      approved_for_conversion INTEGER NOT NULL DEFAULT 0,
      saved_at TEXT NOT NULL,
      PRIMARY KEY(kind,source_id,version_key)
    )""")
    return db

def check_candidates(kind,candidates):
    if not isinstance(candidates,list) or len(candidates)>100:
        raise ValueError("N05_CANDIDATES_NOT_VALIDATED")
    with open_registry() as db:
        checked=[];imported=0
        for candidate in candidates:
            if candidate.get("kind")!=kind:
                raise ValueError("N05_MIXED_SOURCE_KINDS")
            sid,version=candidate["source_id"],candidate["version_key"]
            row=db.execute("""SELECT pine_sha256,verified_source,approved_for_conversion
              FROM investment_pine_versions WHERE kind=? AND source_id=? AND version_key=?""",
              (kind,sid,version)).fetchone()
            # Metadata-only entries never mean Pine code is stored.
            verified=bool(row and row["verified_source"] and row["pine_sha256"])
            imported+=int(verified)
            checked.append({**candidate,"imported":verified,
              "registry_state":"VERIFIED_PINE" if verified else
                  "PINE_SOURCE_NOT_YET_STORED",
              "conversion_approved":bool(verified and row["approved_for_conversion"])})
    return {"items":checked,"checked_count":len(checked),
        "imported_count":imported,"new_count":len(checked)-imported,
        "registry_source":"project_owned_sqlite_pine_versions"}
