"""Find previously imported Pine by strategy ID/version, without hash matching.

Preserves old artifact tables read-only; new records live in a small payload
table. Identical strategy/version cannot be imported twice.
"""
import os
import sqlite3
from contextlib import closing

def db_path():
    return os.environ.get("STUDIO_DB_PATH","/data/studio.sqlite3")

def open_registry():
    db=sqlite3.connect(db_path(),timeout=12)
    db.row_factory=sqlite3.Row
    return db

def check_candidates(kind,candidates):
    if not isinstance(candidates,list) or len(candidates)>100:
        raise ValueError("N05_INVALID_CANDIDATES")
    with closing(open_registry()) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        checked=[]
        imported_count=0
        for item in candidates:
            if item.get("kind")!=kind:
                raise ValueError("N05_CANDIDATE_KIND_MISMATCH")
            key=(kind,item["source_id"],item["version_key"])
            present=False
            if "investment_pine_payloads" in tables:
                present=bool(db.execute("""SELECT 1 FROM investment_pine_payloads
                   WHERE kind=? AND source_id=? AND version_key=?""",key).fetchone())
            if not present and "investment_pine_source_artifacts" in tables:
                present=bool(db.execute("""SELECT 1 FROM investment_pine_source_artifacts
                   WHERE kind=? AND source_id=? AND version_key=?""",key).fetchone())
            imported_count+=int(present)
            checked.append({**item,"imported":present})
    return {"items":checked,"checked_count":len(checked),
        "imported_count":imported_count,"new_count":len(checked)-imported_count}
