"""Investment Postgres domain DB bootstrap and non-destructive legacy sync.

Existing n8n Postgres DB and studio SQLite are never rewritten or dropped.
Postgres cluster gets a separate 'autonomous_investment' DATABASE.
Objects are saved to the current editor persistent volume and referenced by SHA.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit,urlunsplit
from datetime import datetime,timezone

DBNAME="autonomous_investment"
ARTIFACT_ROOT=Path(os.getenv("INVESTMENT_ARTIFACT_ROOT","/data/investment-artifacts"))
SQL_PATH=Path(__file__).resolve().parent/"schema_v1.sql"
SQLITE_PATH=Path(os.getenv("STUDIO_DB_PATH","/data/studio.sqlite3"))

def _pg():
    import psycopg
    return psycopg

def postgres_url():
    root=os.getenv("INVESTMENT_DATABASE_URL","")
    if not root:raise RuntimeError("INVESTMENT_DATABASE_URL_MISSING")
    u=urlsplit(root)
    if u.scheme not in ("postgres","postgresql") or not u.hostname:
        raise RuntimeError("INVALID_INVESTMENT_DATABASE_URL")
    return urlunsplit((u.scheme,u.netloc,"/"+DBNAME,u.query,""))

def connect():
    return _pg().connect(postgres_url(),connect_timeout=12)

def schema_health():
    try:
        with connect() as db:
            rows=db.execute("""SELECT table_schema,table_name FROM information_schema.tables
                 WHERE table_type='BASE TABLE'
                   AND table_schema IN ('platform','catalog','market','research','operations','trading')""").fetchall()
            tables={str(a)+"."+str(b) for a,b in rows}
            expected=38
            return {"status":"ok" if len(tables)>=expected else "SCHEMA_INCOMPLETE",
                "database":DBNAME,"tables":len(tables),"expected_tables":expected,
                "sqlite_untouched":True,"n8n_database_untouched":True}
    except Exception as exc:
        return {"status":"UNAVAILABLE","reason":type(exc).__name__+": "+str(exc)[:180],
            "database":DBNAME,"tables":0}

def bootstrap():
    import psycopg
    from psycopg import sql
    root=os.environ.get("INVESTMENT_DATABASE_URL")
    if not root:raise RuntimeError("INVESTMENT_DATABASE_URL_MISSING")
    u=urlsplit(root)
    if u.scheme not in ("postgres","postgresql") or not u.hostname:
        raise RuntimeError("INVALID_POSTGRES_URL")
    # Connect only to the existing configured database for CREATE DATABASE.
    with psycopg.connect(root,autocommit=True,connect_timeout=15) as admin:
        exists=admin.execute("SELECT 1 FROM pg_database WHERE datname=%s",(DBNAME,)).fetchone()
        if not exists:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DBNAME)))
    ddl=SQL_PATH.read_text(encoding="utf-8")
    if ddl.count("CREATE TABLE IF NOT EXISTS")!=38:
        raise RuntimeError("SCHEMA_NOT_38_TABLES")
    with psycopg.connect(postgres_url(),autocommit=True,connect_timeout=15) as db:
        db.execute(ddl)
    state=schema_health()
    if state["status"]!="ok":
        raise RuntimeError("SCHEMA_INSTALL_INCOMPLETE:"+str(state))
    return state

def save_file(raw,media_type,source_class):
    if not isinstance(raw,bytes) or not raw:
        raise ValueError("ARTIFACT_BYTES_REQUIRED")
    sha=hashlib.sha256(raw).hexdigest()
    ARTIFACT_ROOT.mkdir(parents=True,exist_ok=True)
    target=ARTIFACT_ROOT/sha[:2]/sha
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        import tempfile
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as f:
            f.write(raw);f.flush();os.fsync(f.fileno());name=f.name
        os.chmod(name,0o600)
        os.replace(name,target)
    elif target.stat().st_size!=len(raw) or hashlib.sha256(target.read_bytes()).hexdigest()!=sha:
        raise ValueError("ARTIFACT_COLLISION_OR_CORRUPTION")
    return {"sha":sha,"size":len(raw),"uri":"investment-file://"+sha,
            "media":media_type,"class":source_class}

def upsert_artifact(cur,a):
    row=cur.execute("""INSERT INTO platform.artifacts
      (sha256,storage_uri,media_type,byte_length,source_class)
      VALUES (%s,%s,%s,%s,%s)
      ON CONFLICT(sha256,byte_length)
      DO UPDATE SET storage_uri=platform.artifacts.storage_uri
      RETURNING artifact_id""",
      (a["sha"],a["uri"],a["media"],a["size"],a["class"])).fetchone()
    return row[0]

def record_source(kind,source_id,version,pine,source_url=None,rights="PENDING_REVIEW",title=None):
    if kind not in ("strategy","indicator","library") or not isinstance(source_id,str) or not source_id:
        raise ValueError("INVALID_SOURCE_ID")
    if not isinstance(pine,str) or not pine.strip() or not isinstance(version,str):
        raise ValueError("SOURCE_VERSION_AND_CODE_REQUIRED")
    file=save_file(pine.encode("utf-8"),"text/x-pinescript","REAL_SOURCE")
    major_match=re.search(r"(?m)^\s*//@version=(\d+)\s*$",pine)
    major=int(major_match.group(1)) if major_match else None
    if major not in (4,5,6):major=None
    with connect() as db:
        with db.cursor() as cur:
            script_id=cur.execute("""INSERT INTO catalog.scripts
              (provider,external_script_key,script_kind,title,canonical_url)
              VALUES('TradingView',%s,%s,%s,%s)
              ON CONFLICT(provider,external_script_key) DO UPDATE SET
                last_seen_at=now(),
                title=COALESCE(EXCLUDED.title,catalog.scripts.title),
                canonical_url=COALESCE(EXCLUDED.canonical_url,catalog.scripts.canonical_url)
              RETURNING script_id""",
              (source_id,kind.upper(),title,source_url)).fetchone()[0]
            artifact_id=upsert_artifact(cur,file)
            v=cur.execute("""INSERT INTO catalog.script_versions
                (script_id,provider_version,content_sha256,pine_major,source_artifact_id,rights_state)
                VALUES(%s,%s,%s,%s,%s,%s)
                ON CONFLICT(script_id,content_sha256) DO UPDATE SET
                    content_sha256=EXCLUDED.content_sha256
                RETURNING script_version_id""",
                (script_id,version,file["sha"],major,artifact_id,rights)).fetchone()[0]
            # Resolve only exact pinned Pine imports if the referenced version
            # already exists. An unresolved import is NOT a valid library.
            for full in re.findall(r"(?m)^\s*import\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/\d+)\b",pine):
                row=cur.execute("""SELECT sv.script_version_id FROM catalog.scripts s
                     JOIN catalog.script_versions sv ON sv.script_id=s.script_id
                     WHERE s.script_kind='LIBRARY' AND s.external_script_key=%s
                       AND sv.provider_version=%s LIMIT 1""",
                     ("/".join(full.split("/")[:2]),full.split("/")[-1])).fetchone()
                cur.execute("""INSERT INTO catalog.script_dependencies
                  (from_version_id,import_name,resolved_version_id,resolution_state)
                  VALUES(%s,%s,%s,%s) ON CONFLICT(from_version_id,import_name)
                  DO UPDATE SET resolved_version_id=EXCLUDED.resolved_version_id,
                   resolution_state=EXCLUDED.resolution_state""",
                   (v,full,row[0] if row else None,"PINNED" if row else "MISSING"))
        db.commit()
    return {"script_id":str(script_id),"script_version_id":str(v),
            "artifact_id":str(artifact_id),"sha256":file["sha"]}


def approve_exact_published_mpl_source(source_id, version, sha256):
    """User-acknowledged public MPL source, exact PostgreSQL version only.

    This approves only consent for source conversion; it is NOT Pine→Python
    validation, TV parity, broker activation or a publication authenticity claim.
    """
    from investment_tv_publication import bundled_ddds_reference
    pinned = bundled_ddds_reference()
    if (source_id != pinned["source_id"] or sha256 != pinned["source_sha256"] or
            version != "snapshot-sha256-" + sha256[:16] or
            pinned["source_rights"] != "MPL-2.0"):
        raise ValueError("RIGHTS_APPROVAL_PINNED_MPL_STRATEGY_ONLY")
    with connect() as db:
        with db.cursor() as cur:
            row = cur.execute("""SELECT sv.script_version_id,sv.rights_state
              FROM catalog.script_versions sv
              JOIN catalog.scripts s ON s.script_id=sv.script_id
              WHERE s.provider='TradingView' AND s.external_script_key=%s
              AND sv.provider_version=%s AND sv.content_sha256=%s
              ORDER BY sv.acquired_at DESC LIMIT 1
              FOR UPDATE OF sv""",(source_id,version,sha256)).fetchone()
            if not row:
                raise ValueError("APPROVAL_EXACT_POSTGRES_PINE_NOT_REGISTERED")
            if row[1] not in ("PENDING_REVIEW","APPROVED"):
                raise ValueError("APPROVAL_EXISTING_RIGHTS_BLOCKED")
            cur.execute("""UPDATE catalog.script_versions
               SET rights_state='APPROVED'
               WHERE script_version_id=%s""",(row[0],))
        db.commit()
    return {"rights_state":"APPROVED","script_version_id":str(row[0]),
            "scope":"ONLY_USER_SELECTED_SOURCE_COMPILATION",
            "conversion_validated":False,"tradingview_chart_validated":False}

def record_conversion(source_id,version,python_code,converter_version,scope=""):
    if not python_code or not isinstance(python_code,str):
        raise ValueError("NO_GENERATED_PYTHON")
    file=save_file(python_code.encode("utf-8"),"text/x-python","GENERATED_PYTHON")
    with connect() as db:
        with db.cursor() as cur:
            row=cur.execute("""SELECT sv.script_version_id FROM catalog.scripts s
                JOIN catalog.script_versions sv ON sv.script_id=s.script_id
                WHERE s.external_script_key=%s AND sv.provider_version=%s
                ORDER BY sv.acquired_at DESC LIMIT 1""",(source_id,version)).fetchone()
            if not row:raise ValueError("POSTGRES_PINE_SOURCE_NOT_REGISTERED")
            source_version=row[0]
            deps=cur.execute("""SELECT import_name,resolution_state,
                    COALESCE(resolved_version_id::text,'') FROM catalog.script_dependencies
                    WHERE from_version_id=%s ORDER BY import_name""",(source_version,)).fetchall()
            if any(x[1]!="PINNED" for x in deps):raise ValueError("LIBRARY_DEPENDENCY_NOT_PINNED")
            lock=hashlib.sha256(json.dumps(deps,default=str).encode()).hexdigest()
            fingerprint=hashlib.sha256((str(source_version)+lock+converter_version).encode()).hexdigest()
            aid=upsert_artifact(cur,file)
            cid=cur.execute("""INSERT INTO research.conversions
               (script_version_id,dependency_lock_hash,converter_version,input_fingerprint,
                python_artifact_id,status,diagnostics,finished_at)
               VALUES(%s,%s,%s,%s,%s,'GENERATED',%s::jsonb,now())
               ON CONFLICT(script_version_id,dependency_lock_hash,converter_version,input_fingerprint)
               DO UPDATE SET python_artifact_id=EXCLUDED.python_artifact_id,
                  status=EXCLUDED.status,finished_at=EXCLUDED.finished_at
               RETURNING conversion_id""",
               (source_version,lock,converter_version,fingerprint,aid,json.dumps({"scope":scope}))).fetchone()[0]
        db.commit()
    return {"conversion_id":str(cid),"script_version_id":str(source_version),
            "python_artifact_id":str(aid),"dependency_lock_hash":lock}

def pine_library_by_import_path(import_name):
    """Read the exact library author/name/version from the canonical source DB.

    A missing or ambiguous library is not substituted with the latest version.
    """
    parts=import_name.split("/")
    if len(parts)!=3 or not all(parts) or not parts[2].isdigit():
        raise ValueError("INVALID_PINE_LIBRARY_IMPORT_PATH")
    external="/".join(parts[:2])
    with connect() as db:
        rows=db.execute("""SELECT sv.script_version_id,sv.content_sha256,
          a.storage_uri,sv.provider_version
          FROM catalog.scripts s
          JOIN catalog.script_versions sv ON sv.script_id=s.script_id
          JOIN platform.artifacts a ON a.artifact_id=sv.source_artifact_id
          WHERE s.script_kind='LIBRARY' AND s.external_script_key=%s
            AND sv.provider_version=%s ORDER BY sv.acquired_at DESC LIMIT 3""",
          (external,parts[2])).fetchall()
    if not rows:return None
    if len({x[1] for x in rows})!=1:
        raise ValueError("AMBIGUOUS_PINE_LIBRARY_VERSION")
    sv,sha,uri,version=rows[0]
    sha=sha.strip()
    if uri!="investment-file://"+sha:
        raise ValueError("PINE_LIBRARY_ARTIFACT_URI_MISMATCH")
    source=(ARTIFACT_ROOT/sha[:2]/sha).read_bytes()
    if hashlib.sha256(source).hexdigest()!=sha:
        raise ValueError("PINE_LIBRARY_ARTIFACT_SHA_MISMATCH")
    return {"kind":"library","source_id":external,"version_key":version,
      "source_sha256":sha,"script_version_id":str(sv),
      "pine_code":source.decode("utf-8")}


def refresh_exact_dependency_pins(source_id,version,dependencies):
    """Pin only proven exact library source versions for this strategy."""
    with connect() as db:
        with db.cursor() as cur:
            row=cur.execute("""SELECT sv.script_version_id FROM catalog.scripts s
              JOIN catalog.script_versions sv ON sv.script_id=s.script_id
              WHERE s.external_script_key=%s AND sv.provider_version=%s
              ORDER BY sv.acquired_at DESC LIMIT 1""",(source_id,version)).fetchone()
            if not row:raise ValueError("PINNED_STRATEGY_NOT_FOUND")
            version_id=row[0]
            for d in dependencies:
                if not d.get("script_version_id"):
                    raise ValueError("UNVERIFIED_LIBRARY_DEPENDENCY")
                cur.execute("""UPDATE catalog.script_dependencies SET
                   resolved_version_id=%s,resolution_state='PINNED'
                   WHERE from_version_id=%s AND import_name=%s""",
                   (d["script_version_id"],version_id,d["import_name"]))
            if dependencies:
                rows=cur.execute("""SELECT import_name,resolution_state FROM catalog.script_dependencies
                 WHERE from_version_id=%s""",(version_id,)).fetchall()
                expected={d["import_name"] for d in dependencies}
                if expected!={r[0] for r in rows} or any(r[1]!="PINNED" for r in rows):
                    raise ValueError("STRATEGY_DEPENDENCY_PIN_SET_INCOMPLETE")
        db.commit()
    return {"script_version_id":str(version_id),"resolved_count":len(dependencies)}


def dependencies_for_source(source_id,version):
    with connect() as db:
        row=db.execute("""SELECT sv.script_version_id FROM catalog.scripts s
           JOIN catalog.script_versions sv ON sv.script_id=s.script_id
           WHERE s.external_script_key=%s AND sv.provider_version=%s
           ORDER BY sv.acquired_at DESC LIMIT 1""",(source_id,version)).fetchone()
        if not row:raise ValueError("SOURCE_VERSION_NOT_IN_CANONICAL_DB")
        deps=db.execute("""SELECT import_name,resolution_state,
            COALESCE(resolved_version_id::text,'') FROM catalog.script_dependencies
            WHERE from_version_id=%s ORDER BY import_name""",(row[0],)).fetchall()
    return {"script_version_id":str(row[0]),
            "dependencies":[{"import_name":x[0],"state":x[1],"resolved_version_id":x[2]} for x in deps],
            "all_pinned":all(x[1]=="PINNED" for x in deps)}

def comparison_for_source(source_id,version):
    with connect() as db:
        row=db.execute("""SELECT cc.comparison_id,cc.status,cc.numeric_match,
             cc.visual_verdict,r.reference_id FROM catalog.scripts s
            JOIN catalog.script_versions sv ON sv.script_id=s.script_id
            JOIN research.conversions c ON c.script_version_id=sv.script_version_id
            JOIN research.chart_comparisons cc ON cc.conversion_id=c.conversion_id
            JOIN research.tv_references r ON r.reference_id=cc.reference_id
              AND r.script_version_id=sv.script_version_id
            WHERE s.external_script_key=%s AND sv.provider_version=%s
            ORDER BY cc.computed_at DESC LIMIT 1""",(source_id,version)).fetchone()
    return ({"comparison_id":str(row[0]),"status":row[1],
             "numeric_match":row[2],"visual_verdict":row[3],
             "reference_id":str(row[4])} if row else None)

def verified_chart_evidence_for_source(source_id,version,sha256):
    """Strong canonical proof for a future, non-DDDS publish candidate.

    Both the source/conversion and original captured reference are pinned to
    the same version. An actual captured dataset and nonempty per-point numeric
    comparison counts are required: a success label alone is insufficient.
    """
    with connect() as db:
        row=db.execute("""SELECT cc.comparison_id,cc.status,cc.numeric_match,
              cc.visual_verdict,cc.mismatch_metrics,r.reference_id,
              r.capture_state,r.timeframe,d.bars_count,d.quality_state,
              i.venue,i.native_symbol,c.status,sv.content_sha256
            FROM catalog.scripts s
            JOIN catalog.script_versions sv ON sv.script_id=s.script_id
            JOIN research.conversions c ON c.script_version_id=sv.script_version_id
            JOIN research.chart_comparisons cc ON cc.conversion_id=c.conversion_id
            JOIN research.tv_references r ON r.reference_id=cc.reference_id
             AND r.script_version_id=sv.script_version_id
            JOIN market.dataset_snapshots d ON d.dataset_id=r.dataset_id
             AND d.instrument_id=r.instrument_id AND d.timeframe=r.timeframe
            JOIN market.instruments i ON i.instrument_id=r.instrument_id
            WHERE s.external_script_key=%s AND sv.provider_version=%s
              AND sv.content_sha256=%s
            ORDER BY cc.computed_at DESC LIMIT 1""",
             (source_id,version,sha256)).fetchone()
    if not row:return None
    (cid,status,numeric,visual,metrics,rid,capture,timeframe,
     bars,quality,venue,native,conversion_status,actual_sha)=row
    if (status!="VERIFIED" or numeric is not True or visual not in ("PASS","MATCH") or
        capture not in ("VERIFIED","VALIDATED") or conversion_status!="GENERATED" or
        quality not in ("PASS","APPROVED","VERIFIED") or actual_sha!=sha256 or
        not isinstance(metrics,dict)):
        return None
    compared=metrics.get("compared_numeric_points")
    mismatches=metrics.get("mismatched_numeric_points")
    if type(compared) is not int or type(mismatches) is not int or compared<=0 or mismatches!=0:
        return None
    if type(bars) is not int or bars<40 or not native or not venue or not timeframe:return None
    return {"verified_bar_count":bars,"numeric_points":compared,
      "numeric_mismatches":0,"symbol":venue+":"+native,
      "timeframe":timeframe,
      "verification_type":"CANONICAL_PINNED_TV_REFERENCE_VS_CONVERTED_PYTHON_NUMERIC_VERIFIED",
      "evidence_url":"urn:autonomous-investor:comparison:"+str(cid),
      "comparison_id":str(cid),"reference_id":str(rid),
      "official_tradingview_publication_parity_verified":False,
      "tradingview_299_trades_compared":False}


def link_original_tradingview_publication(source_id,version,sha256,public_url):
    """Bind a real browser-inspected TradingView publication URL to the exact
    canonical Pine version. The public publisher's source bytes may differ,
    so this records a publication link, NOT a numeric equivalence result.
    """
    import re
    if not re.fullmatch(
        r"https://www\.tradingview\.com/script/[A-Za-z0-9]{8}(?:-[A-Za-z0-9._-]+)?/",
        public_url):
        raise ValueError("INVALID_OFFICIAL_TRADINGVIEW_PUBLICATION_URL")
    if not re.fullmatch(r"[0-9a-f]{64}",sha256):
        raise ValueError("INVALID_PINNED_PINE_SHA256")
    with connect() as db:
        with db.cursor() as cur:
            match=cur.execute("""SELECT s.script_id,s.canonical_url
                 FROM catalog.scripts s
                 JOIN catalog.script_versions sv ON sv.script_id=s.script_id
                 WHERE s.external_script_key=%s AND sv.provider_version=%s
                   AND sv.content_sha256=%s LIMIT 1""",
                (source_id,version,sha256)).fetchone()
            if not match:
                raise ValueError("TRADINGVIEW_PUBLICATION_PINNED_VERSION_NOT_FOUND")
            if match[1] not in (None,"",public_url):
                raise ValueError("TRADINGVIEW_PUBLICATION_EXISTING_URL_CONFLICT")
            cur.execute("""UPDATE catalog.scripts SET canonical_url=%s
                WHERE script_id=%s AND (canonical_url IS NULL OR canonical_url=%s)""",
                (public_url,match[0],public_url))
        db.commit()
    return {"script_id":str(match[0]),"original_page_url":public_url,
            "content_equivalence_verified":False}


def get_source(source_id,version):
    """Fetch the exact canonical immutable Pine version, not a random latest row."""
    with connect() as db:
        row=db.execute("""SELECT sv.script_version_id,sv.content_sha256,
           a.storage_uri FROM catalog.scripts s
           JOIN catalog.script_versions sv ON sv.script_id=s.script_id
           JOIN platform.artifacts a ON a.artifact_id=sv.source_artifact_id
           WHERE s.external_script_key=%s AND sv.provider_version=%s
           ORDER BY sv.acquired_at DESC LIMIT 1""",(source_id,version)).fetchone()
    if not row:raise ValueError("POSTGRES_EXACT_SOURCE_NOT_FOUND")
    source_version,sha,uri=row
    if not uri.startswith("investment-file://"):raise ValueError("NONLOCAL_SOURCE_ARTIFACT")
    fp=ARTIFACT_ROOT/uri.removeprefix("investment-file://")[:2]/uri.removeprefix("investment-file://")
    raw=fp.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha.strip():raise ValueError("ARTIFACT_SHA_MISMATCH")
    return {"pine_code":raw.decode("utf-8"),"script_version_id":str(source_version),"source_sha256":sha.strip()}

def counts():
    status=schema_health()
    if status["status"]!="ok":return status
    tables={"scripts":"catalog.scripts","versions":"catalog.script_versions",
            "libraries":"catalog.scripts","conversions":"research.conversions",
            "tv_references":"research.tv_references","comparisons":"research.chart_comparisons",
            "pipeline_runs":"operations.pipeline_runs","node_runs":"operations.node_runs"}
    with connect() as db:
        for label,table in tables.items():
            if label=="libraries":
                status[label]=db.execute("SELECT count(*) FROM catalog.scripts WHERE script_kind='LIBRARY'").fetchone()[0]
            else:
                status[label]=db.execute("SELECT count(*) FROM "+table).fetchone()[0]
    return status

def mirror_node_event(run_id,stage_key,workflow,node_id,node_name,status,payload,error=None):
    """Link the original node's run to Postgres operations trace by stable UUID."""
    import uuid
    run_uuid=uuid.UUID(hex=run_id)
    clean={key:value for key,value in (payload or {}).items() if key not in (
         "pine_code","python_code","manual_library","items","catalog_items")}
    with connect() as db:
        with db.cursor() as cur:
            cur.execute("""INSERT INTO operations.pipeline_runs
                  (pipeline_run_id,requested_by,status,correlation_id,policy_version)
                  VALUES(%s,'internal-executor','RUNNING',%s,'db-v1')
                  ON CONFLICT(pipeline_run_id) DO NOTHING""",(run_uuid,run_id))
            sr=cur.execute("""INSERT INTO operations.stage_runs
                (pipeline_run_id,stage_key,status,started_at)
                VALUES(%s,%s,%s,now()) ON CONFLICT(pipeline_run_id,stage_key,stage_attempt)
                DO UPDATE SET status=EXCLUDED.status RETURNING stage_run_id""",
                (run_uuid,stage_key,status)).fetchone()[0]
            cur.execute("""INSERT INTO operations.node_runs
                (stage_run_id,node_id,node_name,status,output_ref,error_code)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s)""",(sr,node_id or stage_key,
                   node_name,status,json.dumps(clean,ensure_ascii=False,default=str),str(error)[:200] if error else None))
            if node_id in ("wf01-strategy-16","wf01-library-16","wf02-03") or status=="FAILED":
                finished_status=(str((payload or {}).get("status") or "SUCCESS")
                    if status=="SUCCESS" else "FAILED")
                cur.execute("""UPDATE operations.pipeline_runs
                    SET status=%s,ended_at=now(),error_code=%s
                    WHERE pipeline_run_id=%s""",
                    (finished_status,str(error)[:200] if error else None,run_uuid))
                cur.execute("""UPDATE operations.stage_runs
                    SET status=%s,finished_at=now(),error_code=%s
                    WHERE stage_run_id=%s""",
                    (finished_status,str(error)[:200] if error else None,sr))
        db.commit()

def canonical_pipeline_record(run_id):
    """Read back the canonical Postgres row and its linked stage/node events."""
    import uuid
    uuid_value=uuid.UUID(hex=run_id)
    with connect() as db:
        row=db.execute("""SELECT p.pipeline_run_id,p.status,p.selected_script_version_id,
             p.initiated_at,p.ended_at,p.error_code,
             s.external_script_key,sv.provider_version
             FROM operations.pipeline_runs p
             LEFT JOIN catalog.script_versions sv ON sv.script_version_id=p.selected_script_version_id
             LEFT JOIN catalog.scripts s ON s.script_id=sv.script_id
             WHERE p.pipeline_run_id=%s""",(uuid_value,)).fetchone()
        if not row:return {"status":"NOT_RECORDED"}
        stage_rows=db.execute("""SELECT sr.stage_key,sr.status,sr.started_at,sr.finished_at,
            count(n.node_run_id) FROM operations.stage_runs sr
            LEFT JOIN operations.node_runs n ON n.stage_run_id=sr.stage_run_id
            WHERE sr.pipeline_run_id=%s
            GROUP BY sr.stage_run_id ORDER BY sr.stage_key""",(uuid_value,)).fetchall()
        node_count=sum(int(x[4]) for x in stage_rows)
    return {"status":row[1],"run_id":str(row[0]),
            "script_version_id":str(row[2]) if row[2] else None,
            "source_id":row[6],"version_key":row[7],
            "started_at":row[3].isoformat() if row[3] else None,
            "finished_at":row[4].isoformat() if row[4] else None,
            "error":row[5],"node_runs":node_count,
            "stages":[{"stage":x[0],"status":x[1],
             "started_at":x[2].isoformat() if x[2] else None,
             "finished_at":x[3].isoformat() if x[3] else None,
             "node_runs":int(x[4])} for x in stage_rows]}

def finish_pipeline_run(run_id,status,selected=None,error=None):
    import uuid
    run_uuid=uuid.UUID(hex=run_id)
    script_version=None
    with connect() as db:
        with db.cursor() as cur:
            if selected and selected.get("source_id") and selected.get("version_key"):
                row=cur.execute("""SELECT sv.script_version_id FROM catalog.scripts s
                  JOIN catalog.script_versions sv ON sv.script_id=s.script_id
                  WHERE s.external_script_key=%s AND sv.provider_version=%s
                  ORDER BY sv.acquired_at DESC LIMIT 1""",
                  (selected["source_id"],selected["version_key"])).fetchone()
                script_version=row[0] if row else None
            cur.execute("""INSERT INTO operations.pipeline_runs
                (pipeline_run_id,requested_by,status,correlation_id,policy_version,
                 selected_script_version_id,ended_at,error_code)
                VALUES(%s,'integration-console',%s,%s,'db-v1',%s,now(),%s)
                ON CONFLICT(pipeline_run_id) DO UPDATE SET
                  status=EXCLUDED.status,selected_script_version_id=EXCLUDED.selected_script_version_id,
                  ended_at=EXCLUDED.ended_at,error_code=EXCLUDED.error_code""",
                (run_uuid,status,run_id,script_version,str(error)[:180] if error else None))
        db.commit()
    return {"pipeline_run_id":str(run_uuid),"script_version_id":str(script_version) if script_version else None,
            "postgres_sync":"SYNCED"}

def backup_sqlite():
    if not SQLITE_PATH.exists():return None
    folder=Path(os.getenv("INVESTMENT_BACKUP_ROOT","/data/investment-backups"));folder.mkdir(parents=True,exist_ok=True)
    name="studio_before_investment_pg_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".sqlite3"
    dest=folder/name
    with sqlite3.connect(str(SQLITE_PATH),timeout=30) as src:
        with sqlite3.connect(str(dest)) as copy:
            src.backup(copy)
    os.chmod(dest,0o600)
    return str(dest)

def import_legacy():
    """Read-only reconciliation of old Pine and Python rows; never delete any."""
    backup=backup_sqlite()
    if not backup:return {"sources":0,"conversions":0,"backup":None}
    with sqlite3.connect("file:"+backup+"?mode=ro",uri=True) as src:
        src.row_factory=sqlite3.Row
        names={x[0] for x in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        pines=src.execute("SELECT * FROM investment_pine_payloads").fetchall() if "investment_pine_payloads" in names else []
        conversions=src.execute("SELECT * FROM investment_python_conversions").fetchall() if "investment_python_conversions" in names else []
        context={}
        if "investment_source_context" in names:
            for item in src.execute("SELECT * FROM investment_source_context"):
                context[(item["kind"],item["source_id"],item["version_key"])]=dict(item)
    summary={"sources":0,"conversions":0,"errors":[],"backup":backup}
    with connect() as db:
        batch=db.execute("""INSERT INTO platform.legacy_import_batches
          (source_system,source_db,source_backup_ref,status,expected_rows)
          VALUES('studio-sqlite',%s,%s,'IN_PROGRESS',%s) RETURNING batch_id""",
          (str(SQLITE_PATH),backup,len(pines)+len(conversions))).fetchone()[0]
        db.commit()
    def mapping(table,key,entity,result,sha=None,error=None):
        with connect() as db:
            db.execute("""INSERT INTO platform.legacy_id_map
              (batch_id,source_table,source_primary_key,target_table,target_primary_key,source_content_sha,status,error_detail)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
              (batch,table,key,entity,str(result) if result else None,sha,
               "IMPORTED" if result else "QUARANTINED",str(error)[:500] if error else None))
            db.commit()
    for row in pines:
        x=dict(row);key="|".join(str(x[k]) for k in ("kind","source_id","version_key"))
        try:
            metadata=context.get((x["kind"],x["source_id"],x["version_key"]),{})
            res=record_source(x["kind"],x["source_id"],x["version_key"],x["pine_code"],
                metadata.get("source_url"),x["rights_state"],metadata.get("source_title"))
            mapping("investment_pine_payloads",key,"catalog.script_versions",res["script_version_id"],res["sha256"])
            summary["sources"]+=1
        except Exception as exc:
            mapping("investment_pine_payloads",key,"catalog.script_versions",None,error=exc)
            summary["errors"].append(key+": "+str(exc)[:150])
    for row in conversions:
        x=dict(row);key="|".join(str(x[k]) for k in ("kind","source_id","version_key"))
        try:
            res=record_conversion(x["source_id"],x["version_key"],x["python_code"],
                "legacy-pine-converter",x["converter_scope"])
            mapping("investment_python_conversions",key,"research.conversions",res["conversion_id"])
            summary["conversions"]+=1
        except Exception as exc:
            mapping("investment_python_conversions",key,"research.conversions",None,error=exc)
            summary["errors"].append(key+": "+str(exc)[:150])
    with connect() as db:
        db.execute("""UPDATE platform.legacy_import_batches SET status=%s,finished_at=now(),
                imported_rows=%s,rejected_rows=%s WHERE batch_id=%s""",
            ("COMPLETE" if not summary["errors"] else "PARTIAL",
             summary["sources"]+summary["conversions"],len(summary["errors"]),batch))
        db.commit()
    return summary

def run_initialization():
    status=bootstrap()
    # Run an automatic one-time importer; future resync is explicit, not a
    # hidden rewrite of all historical source records on every restart.
    with connect() as db:
        row=db.execute("""SELECT 1 FROM platform.legacy_import_batches
         WHERE source_system='studio-sqlite' AND status='COMPLETE' LIMIT 1""").fetchone()
    migration={"skipped":"ALREADY_IMPORTED"} if row else import_legacy()
    return {"schema":status,"legacy":migration}

if __name__=="__main__":
    print(json.dumps(run_initialization(),ensure_ascii=False,default=str))
