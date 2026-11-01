"""WF01 N15: idempotent SQLite storage for one hash-verified original Pine.

Pine is NOT marked conversion-ready or trading-ready. The original owner's
MPL-2.0 notice is retained, with explicit rights review pending.
No user source is executed, and source ID/version conflicts fail closed.
"""
import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime,timezone
from investment_source_registry import open_registry

def save_verified_source(input_json,kind):
    candidate=input_json["candidate"]
    code=input_json["pine_code"]
    source_id=candidate["source_id"]
    version=candidate["version_key"]
    digest=hashlib.sha256(code.encode("utf-8")).hexdigest()
    if digest!=candidate.get("source_sha256_reported") or digest!=input_json.get("pine_source_sha256"):
        raise ValueError("N15_PINE_SOURCE_SHA256_MISMATCH")
    if input_json.get("source_review_approved") is not False:
        raise ValueError("N15_RIGHTS_REVIEW_NOT_PENDING")
    if input_json.get("conversion_validated") is not False or input_json.get("tradingview_chart_validated") is not False:
        raise ValueError("N15_UNVERIFIED_CONVERSION_CLAIM")
    if input_json.get("source_available") is not True or input_json.get("source_integrity_checked") is not True:
        raise ValueError("N15_SOURCE_NOT_VALIDATED_BY_N12")
    if input_json.get("rights_state") not in ("MPL_2_0_REVIEW_REQUIRED","PENDING_REVIEW"):
        raise ValueError("N15_SOURCE_RIGHTS_UNEXPECTED")
    created=datetime.now(timezone.utc).isoformat()
    with closing(open_registry()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS investment_pine_source_artifacts (
          kind TEXT NOT NULL,
          source_id TEXT NOT NULL,
          version_key TEXT NOT NULL,
          pine_sha256 TEXT NOT NULL,
          pine_code TEXT NOT NULL,
          original_source_url TEXT NOT NULL,
          source_archive_url TEXT,
          author TEXT NOT NULL,
          pine_version TEXT NOT NULL,
          license_reported TEXT NOT NULL,
          rights_state TEXT NOT NULL,
          conversion_validated INTEGER NOT NULL DEFAULT 0,
          tradingview_chart_validated INTEGER NOT NULL DEFAULT 0,
          saved_at TEXT NOT NULL,
          PRIMARY KEY(kind,source_id,version_key)
        )""")
        try:
            db.execute("BEGIN IMMEDIATE")
            present=db.execute("""SELECT pine_sha256,pine_code FROM investment_pine_source_artifacts
                                   WHERE kind=? AND source_id=? AND version_key=?""",
                               (kind,source_id,version)).fetchone()
            if present:
                if present["pine_sha256"]!=digest or present["pine_code"]!=code:
                    raise ValueError("N15_EXISTING_SOURCE_VERSION_HAS_DIFFERENT_BYTES")
                inserted=False
            else:
                db.execute("""INSERT INTO investment_pine_source_artifacts
                   (kind,source_id,version_key,pine_sha256,pine_code,original_source_url,
                    source_archive_url,author,pine_version,license_reported,rights_state,
                    conversion_validated,tradingview_chart_validated,saved_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (kind,source_id,version,digest,code,candidate["source_url"],
                    input_json.get("source_archive_url"),
                    candidate["author"],str(candidate["pine_version"]),
                    candidate.get("source_license_reported","unknown"),
                    input_json["rights_state"],0,0,created))
                inserted=True
            version_row=db.execute("""SELECT pine_sha256,verified_source,approved_for_conversion
                FROM investment_pine_versions
                WHERE kind=? AND source_id=? AND version_key=?""",
                (kind,source_id,version)).fetchone()
            if version_row:
                if version_row["pine_sha256"]!=digest:
                    raise ValueError("N15_EXISTING_VERSION_REGISTRY_HASH_CONFLICT")
                db.execute("""UPDATE investment_pine_versions SET verified_source=1,
                    approved_for_conversion=0 WHERE kind=? AND source_id=? AND version_key=?""",
                    (kind,source_id,version))
            else:
                db.execute("""INSERT INTO investment_pine_versions
                   (kind,source_id,version_key,pine_sha256,verified_source,approved_for_conversion,saved_at)
                   VALUES(?,?,?,?,?,?,?)""",(kind,source_id,version,digest,1,0,created))
            db.commit()
        except Exception:
            db.rollback()
            raise
        row=db.execute("""SELECT pine_sha256,rights_state,conversion_validated,
            tradingview_chart_validated FROM investment_pine_source_artifacts
            WHERE kind=? AND source_id=? AND version_key=?""",
            (kind,source_id,version)).fetchone()
        if not row or row["pine_sha256"]!=digest:
            raise ValueError("N15_SQLITE_READBACK_MISMATCH")
    return {"source_saved":True,"source_created":inserted,
        "source_already_present":not inserted,"source_id":source_id,
        "version_key":version,"pine_source_sha256":digest,
        "source_storage":"investment_project_sqlite",
        "source_review_approved":False,"conversion_validated":False,
        "tradingview_chart_validated":False,
        "source_storage_verified_at":created}
