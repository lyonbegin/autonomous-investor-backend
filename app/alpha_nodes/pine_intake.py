"""WF-01 immutable Pine source intake; no scraping, conversion, or order routing."""
import hashlib
import hmac
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from app.alpha_nodes.api import require_auth

router = APIRouter(prefix="/api/v1/alpha/pine", tags=["Pine source intake"], dependencies=[Depends(require_auth)])
_LOCK = threading.Lock()

class PineIntake(BaseModel):
    source_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,80}$")
    script_type: str = Field(pattern=r"^(indicator|strategy|library)$")
    pine_version: int = Field(ge=1, le=6)
    source_code: str = Field(min_length=10, max_length=300000)
    author: str = Field(min_length=1, max_length=200)
    source_url: str | None = Field(default=None, max_length=2048)
    rights_evidence: str = Field(min_length=10, max_length=4000)

def _connection():
    path = os.getenv("PINE_INTAKE_DB", "/data/pine-intake.sqlite3")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS pine_sources (
        source_id TEXT NOT NULL, version INTEGER NOT NULL,
        sha256 TEXT NOT NULL, script_type TEXT NOT NULL,
        pine_version INTEGER NOT NULL, source_code TEXT NOT NULL,
        source_url TEXT, author TEXT NOT NULL,
        rights_evidence TEXT NOT NULL, rights_state TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(source_id,version), UNIQUE(source_id,sha256))""")
    db.execute("""CREATE TABLE IF NOT EXISTS pine_rights_reviews (
        source_id TEXT NOT NULL, version INTEGER NOT NULL,
        decision TEXT NOT NULL, reviewer TEXT NOT NULL,
        reason TEXT NOT NULL, reviewed_at TEXT NOT NULL,
        PRIMARY KEY(source_id, version))""")
    db.commit()
    return db

def _public(row, duplicate=False):
    return {"source_id": row["source_id"], "version": row["version"],
            "sha256": row["sha256"], "script_type": row["script_type"],
            "pine_version": row["pine_version"], "rights_state": row["rights_state"],
            "conversion_allowed": row["rights_state"] == "APPROVED", "paper_allowed": False,
            "created_at": row["created_at"], "duplicate": duplicate}

def register_source(payload: PineIntake):
    if payload.source_url:
        url = urlparse(payload.source_url)
        if url.scheme != "https" or not url.netloc or url.username or url.password:
            raise ValueError("source_url must be an HTTPS URL without credentials")
    code = payload.source_code.replace("\r\n", "\n")
    if f"//@version={payload.pine_version}" not in code:
        raise ValueError("Pine language version directive missing or mismatched")
    if f"{payload.script_type}(" not in code.replace(" ", ""):
        raise ValueError("declared script_type does not match source declaration")
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    with _LOCK:
        with _connection() as db:
            previous = db.execute("SELECT * FROM pine_sources WHERE source_id=? AND sha256=?",
                                  (payload.source_id, digest)).fetchone()
            if previous:
                return _public(previous, True)
            version = db.execute("SELECT COALESCE(MAX(version),0)+1 FROM pine_sources WHERE source_id=?",
                                 (payload.source_id,)).fetchone()[0]
            db.execute("""INSERT INTO pine_sources (source_id,version,sha256,script_type,pine_version,
                source_code,source_url,author,rights_evidence,rights_state,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (payload.source_id,version,digest,payload.script_type,payload.pine_version,
                 code,payload.source_url,payload.author,payload.rights_evidence,
                 "PENDING_REVIEW",datetime.now(timezone.utc).isoformat()))
            row = db.execute("SELECT * FROM pine_sources WHERE source_id=? AND version=?",
                             (payload.source_id,version)).fetchone()
            return _public(row)

@router.post("/sources", status_code=201)
def register(payload: PineIntake):
    try:
        return register_source(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/sources/{source_id}/versions/{version}")
def get_version(source_id: str, version: int):
    with _connection() as db:
        row = db.execute("SELECT * FROM pine_sources WHERE source_id=? AND version=?",
                         (source_id,version)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Source version not found")
        return _public(row)

class RightsReview(BaseModel):
    decision: str = Field(pattern=r"^(APPROVED|REJECTED)$")
    reviewer: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=10, max_length=2000)

def _require_reviewer(x_pine_reviewer_key: str | None = Header(None)) -> None:
    expected = os.getenv("PINE_RIGHTS_REVIEW_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Rights review disabled")
    if not x_pine_reviewer_key or not hmac.compare_digest(expected, x_pine_reviewer_key):
        raise HTTPException(status_code=403, detail="Reviewer permission required")

@router.post("/sources/{source_id}/versions/{version}/rights-review",
             dependencies=[Depends(_require_reviewer)])
def review_rights(source_id: str, version: int, request: RightsReview):
    with _LOCK:
        with _connection() as db:
            row = db.execute("SELECT * FROM pine_sources WHERE source_id=? AND version=?",
                             (source_id, version)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Source version not found")
            previous = db.execute("SELECT decision FROM pine_rights_reviews WHERE source_id=? AND version=?",
                                  (source_id, version)).fetchone()
            if previous is not None:
                raise HTTPException(status_code=409, detail="Rights decision already finalized")
            now = datetime.now(timezone.utc).isoformat()
            db.execute("INSERT INTO pine_rights_reviews VALUES (?,?,?,?,?,?)",
                       (source_id,version,request.decision,request.reviewer,request.reason,now))
            db.execute("UPDATE pine_sources SET rights_state=? WHERE source_id=? AND version=?",
                       (request.decision,source_id,version))
            updated = db.execute("SELECT * FROM pine_sources WHERE source_id=? AND version=?",
                                 (source_id,version)).fetchone()
            return _public(updated)

@router.get("/sources/{source_id}/versions/{version}/conversion-input")
def conversion_input(source_id: str, version: int):
    with _connection() as db:
        row = db.execute("SELECT * FROM pine_sources WHERE source_id=? AND version=?",
                         (source_id,version)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Source version not found")
        if row["rights_state"] != "APPROVED":
            raise HTTPException(status_code=403, detail="Source rights not approved")
        return {"source_id":row["source_id"], "version":row["version"],
                "sha256":row["sha256"], "pine_version":row["pine_version"],
                "script_type":row["script_type"], "source_code":row["source_code"]}
