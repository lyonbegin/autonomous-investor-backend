"""Persistent strategy registry, exclusive paper agent assignment and independent audit.

Source:
- F01 imports cached/collected *actual upstream* TradingView script metadata.
- A protected/inaccessible/indicator source is never eligible for assignment.
- F03 uses SQLite BEGIN IMMEDIATE + unique indexes to prevent duplicate claims.
- F05 ingests execution observations independently of the scenario simulator,
  marks mismatches, and atomically halts new assignments on critical findings.

This module never calls NautilusTrader execution/order APIs, never asserts
a source is Pine-compatible, and never approves a strategy automatically.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from fastapi import HTTPException

from app.alpha_nodes import services

EVENTS = (
    "StrategyDiscovered", "StrategyVersionCreated", "StrategyEligibilityApproved",
    "StrategySuspended", "StrategyAssigned", "AgentHeartbeat", "AgentReleased",
    "ExecutionObserved", "AuditFindingCreated", "SourceSyncFailed",
)
ASSIGNABLE = ("APPROVED",)
ACTIVE_STATES = ("ACTIVE", "HALTED")
OBSERVATION_TYPES = {"SignalGenerated", "OrderIntent", "OrderSubmitted",
                     "OrderFilled", "PositionChanged", "AgentHeartbeat"}
CRITICAL_KINDS = {"unapproved_order", "version_mismatch", "unknown_assignment", "stale_epoch"}


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _dbpath() -> Path:
    return Path(os.getenv("STRATEGY_OPERATIONS_DB_PATH", "/tmp/investment_ops.sqlite3")).resolve()


@contextmanager
def db(*, write: bool = False) -> Iterator[sqlite3.Connection]:
    path = _dbpath()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""CREATE TABLE IF NOT EXISTS strategy_registry(
            strategy_id TEXT PRIMARY KEY, source_kind TEXT NOT NULL,
            title TEXT NOT NULL, author TEXT NOT NULL, script_type TEXT NOT NULL,
            script_access TEXT NOT NULL, latest_version_id TEXT,
            first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS strategy_versions(
            version_id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL,
            source_version TEXT NOT NULL, source_sha256 TEXT,
            metadata_sha256 TEXT NOT NULL,
            source_access TEXT NOT NULL, eligibility TEXT NOT NULL,
            review_evidence TEXT, reviewed_by TEXT,
            created_at TEXT NOT NULL, source_available INTEGER NOT NULL,
            FOREIGN KEY(strategy_id) REFERENCES strategy_registry(strategy_id));
        CREATE INDEX IF NOT EXISTS idx_version_strategy ON strategy_versions(strategy_id);
        CREATE TABLE IF NOT EXISTS strategy_source_artifacts(
            version_id TEXT PRIMARY KEY, source_text TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            FOREIGN KEY(version_id) REFERENCES strategy_versions(version_id));
        CREATE TABLE IF NOT EXISTS agents(
            agent_id TEXT PRIMARY KEY, status TEXT NOT NULL,
            execution_mode TEXT NOT NULL, market_scope TEXT NOT NULL,
            updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assignments(
            assignment_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL, version_id TEXT NOT NULL,
            slot_key TEXT NOT NULL, epoch INTEGER NOT NULL,
            state TEXT NOT NULL, lease_expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL, ended_at TEXT,
            FOREIGN KEY(agent_id) REFERENCES agents(agent_id),
            FOREIGN KEY(version_id) REFERENCES strategy_versions(version_id));
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_active_agent
          ON assignments(agent_id) WHERE state IN ('ACTIVE','HALTED');
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_active_slot
          ON assignments(slot_key) WHERE state IN ('ACTIVE','HALTED');
        CREATE TABLE IF NOT EXISTS assignment_epochs(
            slot_key TEXT PRIMARY KEY, last_epoch INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS observed_events(
            event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
            assignment_id TEXT, version_id TEXT, epoch INTEGER,
            payload_json TEXT NOT NULL, observed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_findings(
            finding_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, assignment_id TEXT,
            severity TEXT NOT NULL, code TEXT NOT NULL, details TEXT NOT NULL,
            created_at TEXT NOT NULL, UNIQUE(event_id,code));
        CREATE TABLE IF NOT EXISTS ops_events(
            seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
            flow_id TEXT NOT NULL, payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sync_runs(
            run_id TEXT PRIMARY KEY, state TEXT NOT NULL,
            scanned INTEGER NOT NULL, added INTEGER NOT NULL,
            source_errors INTEGER NOT NULL, created_at TEXT NOT NULL,
            completed_at TEXT NOT NULL);
        """)
        if write:
            con.execute("BEGIN IMMEDIATE")
        yield con
        if write:
            con.commit()
    except Exception:
        if write and con.in_transaction:
            con.rollback()
        raise
    finally:
        con.close()


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _emit(con: sqlite3.Connection, kind: str, flow: str, data: dict) -> None:
    con.execute("INSERT INTO ops_events(kind,flow_id,payload_json,created_at) VALUES(?,?,?,?)",
                (kind,flow,_json(data),_utc()))


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def read_events(after: int = 0, limit: int = 100) -> dict:
    with db() as con:
        rows=con.execute("SELECT * FROM ops_events WHERE seq>? ORDER BY seq LIMIT ?",(after,limit)).fetchall()
        last=con.execute("SELECT COALESCE(MAX(seq),0) FROM ops_events").fetchone()[0]
    return {"events":[{"seq":x["seq"],"type":x["kind"],"flow":x["flow_id"],
                       "created_at":x["created_at"],"payload":json.loads(x["payload_json"])}
                      for x in rows],
            "last_seq":int(last)}


def strategy_list(status: str | None = None, limit: int = 100) -> dict:
    with db() as con:
        rows=con.execute("""SELECT r.*,v.eligibility,v.source_available,v.source_sha256,
                        v.source_version FROM strategy_registry r
                        LEFT JOIN strategy_versions v ON v.version_id=r.latest_version_id
                        ORDER BY r.last_seen_at DESC LIMIT ?""",(limit,)).fetchall()
    results=[dict(r) for r in rows if status is None or r["eligibility"]==status]
    return {"count":len(results),"items":results}


def agent_list() -> dict:
    with db() as con:
        agents=con.execute("SELECT * FROM agents ORDER BY agent_id").fetchall()
        assignments=con.execute("""SELECT * FROM assignments WHERE state IN ('ACTIVE','HALTED')
                                    ORDER BY created_at""").fetchall()
    return {"agents":[dict(a) for a in agents],"active_assignments":[dict(a) for a in assignments]}


def audit_list(limit: int = 100) -> dict:
    with db() as con:
        rows=con.execute("SELECT * FROM audit_findings ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    return {"count":len(rows),"items":[dict(x) for x in rows]}


def _normalize_script(item: dict) -> tuple[str, str, str, str, str, str]:
    source_id=str(item.get("script_id_part") or "").strip()
    if not source_id or len(source_id)>200:
        raise ValueError("missing/invalid script_id_part")
    title=str(item.get("name") or item.get("script_name") or source_id)[:250]
    author=str(item.get("author") or "")[:100]
    kind=str(item.get("script_type") or "").lower()[:60]
    access=str(item.get("script_access") or "unknown").lower()[:60]
    version=str(item.get("version") or "unknown")[:100]
    return source_id,title,author,kind,access,version


def ingest(item: dict, source_detail: dict | None = None) -> dict:
    """Import one upstream result without inventing permission or Pine support.

    Only content-hashed source is versioned; metadata-only records remain
    visible as INACCESSIBLE/PENDING, never accepted for agent assignment.
    """
    sid,title,author,kind,access,upstream_version=_normalize_script(item)
    source=source_detail.get("source") if isinstance(source_detail,dict) and source_detail.get("ok") is True else None
    if not isinstance(source,str) or not source.strip():
        source=None
    is_strategy="strateg" in kind
    source_sha=hashlib.sha256(source.encode()).hexdigest() if source else None
    metadata_hash=hashlib.sha256(_json([sid,title,author,kind,access,upstream_version]).encode()).hexdigest()
    # The immutable version key identifies SOURCE CONTENT and its upstream version.
    # Metadata-only version is distinct and never upgrades to eligible content.
    material=_json([sid,upstream_version,source_sha,metadata_hash if not source else None])
    version_id="tv-"+hashlib.sha256(material.encode()).hexdigest()[:28]
    eligible_status="PENDING_REVIEW" if source and is_strategy else "INELIGIBLE"
    now=_utc()
    with db(write=True) as con:
        existing=con.execute("SELECT latest_version_id FROM strategy_registry WHERE strategy_id=?",(sid,)).fetchone()
        created=con.execute("SELECT version_id FROM strategy_versions WHERE version_id=?",(version_id,)).fetchone() is None
        con.execute("""INSERT INTO strategy_registry
           (strategy_id,source_kind,title,author,script_type,script_access,latest_version_id,first_seen_at,last_seen_at)
           VALUES(?,?,?,?,?,?,?,?,?)
           ON CONFLICT(strategy_id) DO UPDATE SET
             title=excluded.title,author=excluded.author,script_type=excluded.script_type,
             script_access=excluded.script_access,last_seen_at=excluded.last_seen_at""",
            (sid,"tradingview",title,author,kind,access,version_id,now,now))
        if created:
            con.execute("""INSERT INTO strategy_versions
               (version_id,strategy_id,source_version,source_sha256,metadata_sha256,
               source_access,eligibility,created_at,source_available)
               VALUES(?,?,?,?,?,?,?,?,?)""",
               (version_id,sid,upstream_version,source_sha,metadata_hash,access,
                eligible_status,now,int(source is not None)))
            if source is not None:
                con.execute("INSERT INTO strategy_source_artifacts(version_id,source_text,sha256) VALUES(?,?,?)",
                            (version_id,source,source_sha))
            con.execute("UPDATE strategy_registry SET latest_version_id=? WHERE strategy_id=?",
                        (version_id,sid))
            _emit(con,"StrategyVersionCreated","F01",{
                "strategy_id":sid,"version_id":version_id,
                "source_present":bool(source),"eligibility":eligible_status,
                "origin":"tradingview", "next_flow":"F02"})
        elif existing is None:
            _emit(con,"StrategyDiscovered","F01",{"strategy_id":sid})
    return {"strategy_id":sid,"version_id":version_id,"created":created,
            "eligibility":eligible_status if created else "UNCHANGED",
            "source_present":bool(source)}


def sync(limit: int = 30, offset: int = 0, max_sources: int = 5) -> dict:
    """Real TradingView-service read; fails closed if upstream catalog is unavailable.

    No synthetic fallback, no automatic eligibility, no source bypass.
    """
    try:
        upstream=services.script_catalog(limit=limit,offset=offset,script_type="strategies")
    except (ValueError, RuntimeError, ConnectionError, TimeoutError, OSError) as exc:
        with db(write=True) as con:
            _emit(con,"SourceSyncFailed","F01",{"error_type":type(exc).__name__})
        raise HTTPException(status_code=502,detail=f"TradingView catalog unavailable: {type(exc).__name__}") from exc
    items=upstream.get("items")
    if not isinstance(items,list):
        raise HTTPException(status_code=502,detail="TradingView catalog missing items")
    added=0
    errors=[]
    results=[]
    for item in items[:limit]:
        if not isinstance(item,dict):
            errors.append({"id":None,"code":"INVALID_CATALOG_ITEM"})
            continue
        try:
            script_id=str(item.get("script_id_part") or "")
            # Source fetch is explicitly bounded to avoid scraping too many codes;
            # missing/preserved source remains ineligible, not silently accepted.
            source=None
            if len(results)<max_sources and script_id:
                try:
                    source=services.script_source(script_id,version="last")
                except (ValueError, RuntimeError, ConnectionError, OSError, TimeoutError):
                    errors.append({"id":script_id[:80],"code":"SOURCE_FETCH_FAILED"})
            outcome=ingest(item,source)
            added+=int(outcome["created"])
            results.append(outcome)
        except (TypeError, ValueError, sqlite3.Error) as exc:
            errors.append({"id":str(item.get("script_id_part") or "")[:80],"code":type(exc).__name__})
    run_id=uuid.uuid4().hex
    status="PARTIAL" if errors else "COMPLETED"
    with db(write=True) as con:
        con.execute("INSERT INTO sync_runs VALUES(?,?,?,?,?,?,?)",
                    (run_id,status,len(items[:limit]),added,len(errors),_utc(),_utc()))
    return {"sync_id":run_id,"state":status,"scanned":len(items[:limit]),"added":added,
            "source_errors":len(errors),"errors":errors[:30],"items":results,
            "catalog_total":upstream.get("total_count"),"mode":"REAL_UPSTREAM_METADATA"}


def approve(version_id: str, reviewer: str, evidence: dict) -> dict:
    # Human attestation is explicitly distinguishable from a validated engine result.
    required={"license_reviewed","pine_compiler_passed","independent_backtest_passed"}
    if not all(evidence.get(x) is True for x in required):
        raise HTTPException(status_code=422,detail="all review attestations required")
    if not isinstance(evidence.get("evidence_refs"),list) or not evidence["evidence_refs"]:
        raise HTTPException(status_code=422,detail="audit/backtest evidence_refs required")
    if len(reviewer.strip())<2:
        raise HTTPException(status_code=422,detail="reviewer identity required")
    with db(write=True) as con:
        v=con.execute("""SELECT v.*,r.script_type FROM strategy_versions v
             JOIN strategy_registry r ON v.strategy_id=r.strategy_id
             WHERE v.version_id=?""",(version_id,)).fetchone()
        if v is None:
            raise HTTPException(status_code=404,detail="version not found")
        if not v["source_available"] or "strateg" not in v["script_type"]:
            raise HTTPException(status_code=409,detail="not an executable public strategy")
        if v["eligibility"] == "SUSPENDED":
            raise HTTPException(status_code=409,detail="version suspended; cannot reapprove")
        con.execute("UPDATE strategy_versions SET eligibility='APPROVED',review_evidence=?,reviewed_by=? WHERE version_id=?",
                    (_json(evidence),reviewer,version_id))
        _emit(con,"StrategyEligibilityApproved","F02",{
            "version_id":version_id,"reviewer":reviewer,"evidence_refs":evidence["evidence_refs"]})
    return {"version_id":version_id,"eligibility":"APPROVED","reviewer":reviewer,
            "review_source":"HUMAN_ATTESTATION_NOT_VERIFIED_ENGINE"}


def register_agent(agent_id: str, market_scope: str = "US", mode: str = "paper") -> dict:
    if mode != "paper":
        raise HTTPException(status_code=422, detail="Only PAPER agents supported")
    if not agent_id or len(agent_id)>80:
        raise HTTPException(status_code=422,detail="agent_id invalid")
    with db(write=True) as con:
        row=con.execute("SELECT status FROM agents WHERE agent_id=?",(agent_id,)).fetchone()
        if row and row["status"]!="IDLE":
            raise HTTPException(status_code=409,detail="agent already assigned")
        con.execute("""INSERT INTO agents(agent_id,status,execution_mode,market_scope,updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(agent_id) DO UPDATE SET market_scope=excluded.market_scope,updated_at=excluded.updated_at""",
                    (agent_id,"IDLE",mode,market_scope,_utc()))
    return {"agent_id":agent_id,"status":"IDLE","execution_mode":"paper"}


def claim(agent_id: str, version_id: str, slot_key: str, lease_seconds: int = 90) -> dict:
    if not slot_key or len(slot_key)>120:
        raise HTTPException(status_code=422,detail="slot_key invalid")
    now=_utc()
    expires=(datetime.now(UTC)+timedelta(seconds=lease_seconds)).isoformat()
    with db(write=True) as con:
        a=con.execute("SELECT * FROM agents WHERE agent_id=?",(agent_id,)).fetchone()
        v=con.execute("SELECT * FROM strategy_versions WHERE version_id=?",(version_id,)).fetchone()
        if a is None or v is None:
            raise HTTPException(status_code=404,detail="agent or version not found")
        if a["status"]!="IDLE" or a["execution_mode"]!="paper":
            raise HTTPException(status_code=409,detail="agent is not idle paper worker")
        if v["eligibility"] not in ASSIGNABLE or not v["source_available"]:
            raise HTTPException(status_code=409,detail="version not approved/available")
        # Closed/expired leases are NOT automatically reclaimed. F10 must
        # reconcile any outstanding position/order and explicitly release.
        if con.execute("SELECT 1 FROM assignments WHERE slot_key=? AND state IN ('ACTIVE','HALTED')",
                       (slot_key,)).fetchone():
            raise HTTPException(status_code=409,detail="slot already occupied")
        epoch_row=con.execute("SELECT last_epoch FROM assignment_epochs WHERE slot_key=?",(slot_key,)).fetchone()
        epoch=int(epoch_row[0])+1 if epoch_row else 1
        con.execute("""INSERT INTO assignment_epochs(slot_key,last_epoch) VALUES(?,?)
           ON CONFLICT(slot_key) DO UPDATE SET last_epoch=excluded.last_epoch""",(slot_key,epoch))
        assignment_id="as-"+uuid.uuid4().hex
        con.execute("""INSERT INTO assignments
          (assignment_id,agent_id,strategy_id,version_id,slot_key,epoch,state,lease_expires_at,created_at)
          VALUES(?,?,?,?,?,?,?,?,?)""",
          (assignment_id,agent_id,v["strategy_id"],version_id,slot_key,epoch,"ACTIVE",expires,now))
        con.execute("UPDATE agents SET status='ASSIGNED',updated_at=? WHERE agent_id=?",(now,agent_id))
        result={"assignment_id":assignment_id,"agent_id":agent_id,"version_id":version_id,
                "strategy_id":v["strategy_id"],"slot_key":slot_key,"epoch":epoch,
                "state":"ACTIVE","execution_mode":"paper","lease_expires_at":expires}
        _emit(con,"StrategyAssigned","F03",{**result,"next_flow":"F04"})
        return result


def allocate_one() -> dict:
    """Atomic opportunistic claim: select an idle PAPER worker and approved,
    unassigned version. Races are resolved with BEGIN IMMEDIATE."""
    with db(write=True) as con:
        agents=con.execute("SELECT * FROM agents WHERE status='IDLE' AND execution_mode='paper' ORDER BY agent_id").fetchall()
        candidates=con.execute("""SELECT v.* FROM strategy_versions v
           JOIN strategy_registry r ON r.latest_version_id=v.version_id
           WHERE v.eligibility='APPROVED' AND v.source_available=1
           ORDER BY v.created_at, v.version_id""").fetchall()
        for agent in agents:
            for v in candidates:
                slot="paper:"+v["strategy_id"]
                if con.execute("SELECT 1 FROM assignments WHERE slot_key=? AND state IN ('ACTIVE','HALTED')",(slot,)).fetchone():
                    continue
                epoch_row=con.execute("SELECT last_epoch FROM assignment_epochs WHERE slot_key=?",(slot,)).fetchone()
                epoch=int(epoch_row[0])+1 if epoch_row else 1
                con.execute("""INSERT INTO assignment_epochs(slot_key,last_epoch) VALUES(?,?)
                   ON CONFLICT(slot_key) DO UPDATE SET last_epoch=excluded.last_epoch""",(slot,epoch))
                aid="as-"+uuid.uuid4().hex
                now=_utc()
                expires=(datetime.now(UTC)+timedelta(seconds=90)).isoformat()
                con.execute("""INSERT INTO assignments
                 (assignment_id,agent_id,strategy_id,version_id,slot_key,epoch,state,lease_expires_at,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?)""",
                            (aid,agent["agent_id"],v["strategy_id"],v["version_id"],slot,epoch,"ACTIVE",expires,now))
                con.execute("UPDATE agents SET status='ASSIGNED',updated_at=? WHERE agent_id=?",(now,agent["agent_id"]))
                result={"assignment_id":aid,"agent_id":agent["agent_id"],"strategy_id":v["strategy_id"],
                        "version_id":v["version_id"],"slot_key":slot,"epoch":epoch,"state":"ACTIVE",
                        "execution_mode":"paper","lease_expires_at":expires}
                _emit(con,"StrategyAssigned","F03",{**result,"next_flow":"F04"})
                return {"assigned":True,"assignment":result}
    return {"assigned":False,"reason":"no eligible approved version and idle agent pair"}


def heartbeat(assignment_id: str, epoch: int, lease_seconds: int = 90) -> dict:
    with db(write=True) as con:
        assignment=con.execute("SELECT * FROM assignments WHERE assignment_id=?",(assignment_id,)).fetchone()
        if assignment is None:
            raise HTTPException(status_code=404,detail="assignment not found")
        if assignment["epoch"]!=epoch or assignment["state"]!="ACTIVE":
            raise HTTPException(status_code=409,detail="stale epoch or halted assignment")
        if assignment["lease_expires_at"]<=_utc():
            raise HTTPException(status_code=409,detail="lease expired; F10 reconciliation required")
        expires=(datetime.now(UTC)+timedelta(seconds=lease_seconds)).isoformat()
        con.execute("UPDATE assignments SET lease_expires_at=? WHERE assignment_id=?",(expires,assignment_id))
        return {"assignment_id":assignment_id,"epoch":epoch,"lease_expires_at":expires}


def release(assignment_id: str, epoch: int, *, flat: bool, open_orders: int,
            reconciliation_ref: str) -> dict:
    if not flat or open_orders!=0 or len(reconciliation_ref.strip())<3:
        raise HTTPException(status_code=409,detail="F10 verified flat position, zero orders and reconciliation_ref required")
    with db(write=True) as con:
        a=con.execute("SELECT * FROM assignments WHERE assignment_id=?",(assignment_id,)).fetchone()
        if a is None:
            raise HTTPException(status_code=404,detail="assignment not found")
        if a["epoch"]!=epoch or a["state"] not in ACTIVE_STATES:
            raise HTTPException(status_code=409,detail="stale assignment or invalid state")
        now=_utc()
        con.execute("UPDATE assignments SET state='RELEASED',ended_at=? WHERE assignment_id=?",(now,assignment_id))
        con.execute("UPDATE agents SET status='IDLE',updated_at=? WHERE agent_id=?",(now,a["agent_id"]))
        _emit(con,"AgentReleased","F10",{"assignment_id":assignment_id,"epoch":epoch,
                                      "reconciliation_ref":reconciliation_ref})
    return {"assignment_id":assignment_id,"status":"RELEASED","agent_id":a["agent_id"]}


def observe(*, event_id: str, event_type: str, assignment_id: str,
            version_id: str, epoch: int, payload: dict) -> dict:
    """Independent audit intake. Never submits/cancels/updates real broker orders."""
    if event_type not in OBSERVATION_TYPES:
        raise HTTPException(status_code=422,detail="unsupported observation event")
    if len(event_id)<4 or len(event_id)>128:
        raise HTTPException(status_code=422,detail="invalid immutable event_id")
    now=_utc()
    findings=[]
    with db(write=True) as con:
        existed=con.execute("SELECT payload_json FROM observed_events WHERE event_id=?",(event_id,)).fetchone()
        if existed is not None:
            if existed["payload_json"]!=_json(payload):
                raise HTTPException(status_code=409,detail="event_id reused with changed payload")
            return {"event_id":event_id,"duplicate":True,"findings":[]}
        ass=con.execute("SELECT * FROM assignments WHERE assignment_id=?",(assignment_id,)).fetchone()
        if ass is None:
            findings.append(("CRITICAL","unknown_assignment","assignment is not registered"))
        else:
            if ass["version_id"]!=version_id:
                findings.append(("CRITICAL","version_mismatch","observed strategy version differs from pinned version"))
            if ass["epoch"]!=epoch:
                findings.append(("CRITICAL","stale_epoch","observed event fencing token differs from assignment"))
            if ass["state"]!="ACTIVE":
                findings.append(("CRITICAL","unapproved_order","assignment is not in ACTIVE state"))
            if ass["lease_expires_at"]<=now:
                findings.append(("CRITICAL","stale_epoch","assignment lease expired"))
            if event_type in {"OrderIntent","OrderSubmitted","OrderFilled"}:
                if payload.get("risk_approved") is not True:
                    findings.append(("CRITICAL","unapproved_order","missing explicit risk approval for order-related event"))
        con.execute("""INSERT INTO observed_events(event_id,event_type,assignment_id,version_id,epoch,payload_json,observed_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (event_id,event_type,assignment_id,version_id,epoch,_json(payload),now))
        _emit(con,"ExecutionObserved","F05",{
            "event_id":event_id,"event_type":event_type,"assignment_id":assignment_id,
            "version_id":version_id})
        for severity,code,details in findings:
            finding_id="af-"+uuid.uuid4().hex
            con.execute("""INSERT INTO audit_findings(finding_id,event_id,assignment_id,severity,code,details,created_at)
                           VALUES(?,?,?,?,?,?,?)""",
                        (finding_id,event_id,assignment_id,severity,code,details,now))
            _emit(con,"AuditFindingCreated","F05",{
                "finding_id":finding_id,"assignment_id":assignment_id,
                "severity":severity,"code":code,"next_flows":["F07","F09"]})
        if ass is not None and any(code in CRITICAL_KINDS for _,code,_ in findings):
            con.execute("UPDATE assignments SET state='HALTED' WHERE assignment_id=? AND state='ACTIVE'",
                        (assignment_id,))
            _emit(con,"StrategySuspended","F09",{
                "assignment_id":assignment_id,"reason":"critical_audit","new_intents_allowed":False})
    return {"event_id":event_id,"duplicate":False,
            "findings":[{"severity":severity,"code":code,"details":details}
                        for severity,code,details in findings],
            "assignment_state":"HALTED" if findings and ass is not None else ass["state"] if ass else None}


def audit_reconcile() -> dict:
    """Independent periodic F05 check, without direct broker dependencies."""
    count=0
    with db(write=True) as con:
        now=_utc()
        expired=con.execute("""SELECT * FROM assignments WHERE state='ACTIVE'
            AND lease_expires_at<=?""",(now,)).fetchall()
        for a in expired:
            fid="af-"+uuid.uuid4().hex
            virtual_event_id="lease-"+a["assignment_id"]+"-"+a["lease_expires_at"]
            found=con.execute("SELECT 1 FROM audit_findings WHERE event_id=? AND code='lease_expired'",
                              (virtual_event_id,)).fetchone()
            if found:
                continue
            con.execute("""INSERT INTO audit_findings VALUES(?,?,?,?,?,?,?)""",
                        (fid,virtual_event_id,a["assignment_id"],"CRITICAL","lease_expired",
                         "agent lease expired; F10 reconcile before release",now))
            con.execute("UPDATE assignments SET state='HALTED' WHERE assignment_id=?",(a["assignment_id"],))
            _emit(con,"AuditFindingCreated","F05",{
                "finding_id":fid,"assignment_id":a["assignment_id"],"code":"lease_expired",
                "severity":"CRITICAL","next_flows":["F09","F10"]})
            count+=1
    return {"checked":"active_agent_leases","halted":count,"source":"PERSISTED_ASSIGNMENTS_ONLY"}


def overview() -> dict:
    with db() as con:
        values={}
        for table in ("strategy_registry","strategy_versions","agents","assignments","observed_events","audit_findings","ops_events"):
            values[table]=con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        approved=con.execute("SELECT COUNT(*) FROM strategy_versions WHERE eligibility='APPROVED'").fetchone()[0]
        active=con.execute("SELECT COUNT(*) FROM assignments WHERE state='ACTIVE'").fetchone()[0]
    return {"counts":values,"approved_versions":approved,"active_assignments":active,
            "execution_mode":"paper_only","broker_connected":False,
            "source_kind":"real_tradingview_service_or_explicit_fixture",
            "n8n_workflows":["F01","F03","F05"]}
