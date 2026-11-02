"""Project-owned four-stage investment workflow runner.

This is not a mock n8n success animation. It executes the functions bound to
the four original investment workflows, stores stage/node outcomes in the
existing SQLite, reuses previously saved Pine and Python results, and marks
missing real TradingView reference material as BLOCKED. It never fabricates
screenshots, market candles, strategy signals, or conversion success.
"""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
import time

from investment_source_registry import open_registry

STRATEGY="operations/WF01-latest-strategy-one.json"
LIBRARY="operations/WF01-latest-library-one.json"
PYTHON="operations/WF02-pine-to-python.json"
PARITY="operations/WF02-chart-parity-first-stage.json"
STAGES=("strategy","library","python","chart")
PARITY_HOST="https://investment-pine-parity-review-production.up.railway.app"
_running_lock=threading.Lock()
_active=set()

def now():
    return datetime.now(timezone.utc).isoformat()

def init():
    with closing(open_registry()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS investment_pipeline_runs(
           run_id TEXT PRIMARY KEY, sid TEXT NOT NULL, status TEXT NOT NULL,
           started_at TEXT NOT NULL, finished_at TEXT,
           selected_source_id TEXT, selected_version TEXT,
           result_json TEXT NOT NULL DEFAULT '{}'
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS investment_pipeline_events(
           event_id INTEGER PRIMARY KEY AUTOINCREMENT,
           run_id TEXT NOT NULL, stage TEXT NOT NULL,
           workflow TEXT NOT NULL, node_id TEXT,
           node_name TEXT NOT NULL, status TEXT NOT NULL,
           payload_json TEXT NOT NULL, error TEXT, at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_investment_pipeline_sid ON investment_pipeline_runs(sid, started_at DESC)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_investment_pipeline_events ON investment_pipeline_events(run_id,event_id)")
        # A crashed container must not leave permanently green or 'running' jobs.
        db.execute("UPDATE investment_pipeline_runs SET status='INTERRUPTED',finished_at=? WHERE status='RUNNING'",(now(),))
        db.commit()

def event(run_id,stage,workflow,node_id,name,status,payload=None,error=None):
    # Keep complete source in investment_pine_payloads and generated Python in
    # investment_python_conversions; no duplicate megabyte-sized blobs in trace.
    clean={}
    for k,v in (payload or {}).items():
        if k in ("pine_code","python_code","manual_library","items","catalog_items","candidates"):
            if isinstance(v,str):clean[k+"_bytes"]=len(v.encode("utf-8"))
            elif isinstance(v,list):clean[k+"_count"]=len(v)
            continue
        if k in ("strategy_spec","comparison") and isinstance(v,(dict,list)):
            clean[k]=str(v)[:1200]
            continue
        if isinstance(v,(str,int,float,bool,type(None))):
            clean[k]=v[:900] if isinstance(v,str) else v
        elif isinstance(v,dict):
            clean[k]={key:(val[:160] if isinstance(val,str) else val)
                 for key,val in v.items() if key not in ("pine_code","python_code","manual_library")}
    with closing(open_registry()) as db:
        db.execute("""INSERT INTO investment_pipeline_events
          (run_id,stage,workflow,node_id,node_name,status,payload_json,error,at)
          VALUES(?,?,?,?,?,?,?,?,?)""",(run_id,stage,workflow,node_id,name,status,
                             json.dumps(clean,ensure_ascii=False,default=str),
                             str(error)[:2000] if error else None,now()))
        db.commit()
    if os.environ.get("INVESTMENT_DATABASE_URL"):
        try:
            from investment_pg import mirror_node_event
            mirror_node_event(run_id,stage,workflow,node_id or stage,name,status,clean,error)
        except Exception as exc:
            with closing(open_registry()) as db:
                db.execute("""INSERT INTO investment_pipeline_events
                  (run_id,stage,workflow,node_id,node_name,status,payload_json,error,at)
                  VALUES(?,?,?,?,?,'POSTGRES_TRACE_FAILED','{}',?,?)""",
                  (run_id,stage,workflow,node_id or stage,"Canonical DB sync",
                   (type(exc).__name__+": "+str(exc))[:450],now()))
                db.commit()
            print("PIPELINE_POSTGRES_NODE_SYNC_FAILED",run_id,stage,
                  type(exc).__name__,str(exc)[:160],flush=True)

def stage(run_id,label,workflow,status,detail=None,error=None):
    event(run_id,label,workflow,None,{"strategy":"WF-01 전략 수집",
          "library":"WF-01 라이브러리 수집","python":"WF-02 Pine→Python",
          "chart":"WF-02 원본·Python 차트 비교"}[label],status,detail,error)

def select_from_db(kind="strategy"):
    with closing(open_registry()) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "investment_pine_payloads" not in tables:return []
        rows=db.execute("""SELECT source_id,version_key,length(pine_code) AS chars,
                 rights_state,saved_at FROM investment_pine_payloads
                 WHERE kind=? ORDER BY saved_at DESC, rowid DESC LIMIT 120""",(kind,)).fetchall()
    return [dict(x) for x in rows]

def context_for_source(source_id,version):
    with closing(open_registry()) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "investment_source_context" not in tables:return None
        row=db.execute("""SELECT source_url,source_title FROM investment_source_context
           WHERE kind='strategy' AND source_id=? AND version_key=?""",
           (source_id,version)).fetchone()
        return dict(row) if row else None

def run_graph(run_id,stage_name,path,inputs):
    """Follow EXACT registered node graph; execute real project Python functions."""
    import investment_node_adapter as adapter
    graph_path=Path(os.environ.get("STUDIO_STATIC_ROOT","/app/dist"))/"stock-workflows"/path
    graph=json.loads(graph_path.read_text(encoding="utf-8"))
    nodes=graph["nodes"]
    names={n["name"]:n for n in nodes}
    node=nodes[0]
    previous=inputs
    for count in range(42):
        binding=adapter.node_binding(path,node["id"])
        if not binding or node.get("parameters",{}).get("studioPython")!=binding:
            raise ValueError("PIPELINE_NODE_BINDING_NOT_APPROVED:"+node["id"])
        started=time.monotonic()
        try:
            output=adapter.execute_node(path,node["id"],previous)
            if not isinstance(output,dict):
                raise ValueError("PIPELINE_NODE_OUTPUT_OBJECT_REQUIRED")
        except Exception as exc:
            event(run_id,stage_name,path,node["id"],node["name"],"FAILED",
                  {"duration_ms":int((time.monotonic()-started)*1000)},str(exc))
            raise
        event(run_id,stage_name,path,node["id"],node["name"],"SUCCESS",
              {**output,"duration_ms":int((time.monotonic()-started)*1000)})
        branches=graph.get("connections",{}).get(node["name"],{}).get("main",[])
        active=output.get("_studio_active_ports",[0])
        if not isinstance(active,list) or len(active)!=1 or not isinstance(active[0],int):
            raise ValueError("PIPELINE_UNSUPPORTED_BRANCH")
        links=branches[active[0]] if active[0]<len(branches) else []
        if not links:
            return output
        target=links[0]["node"]
        if len(links)!=1 or target not in names:
            raise ValueError("PIPELINE_MALFORMED_GRAPH_EDGE")
        node=names[target]
        previous=output
    raise ValueError("PIPELINE_NODE_STEP_LIMIT")

def lookup_reference(source_url,code):
    if not source_url:
        return None,"SOURCE_URL_NOT_IN_DATABASE"
    query=urllib.parse.urlencode({
        "source_url":source_url,
        "pine_sha256":hashlib.sha256(code.encode("utf-8")).hexdigest()})
    req=urllib.request.Request(PARITY_HOST+"/api/references/lookup?"+query,
          headers={"Accept":"application/json","User-Agent":"investment-pipeline-reference-lookup/1"})
    try:
        with urllib.request.urlopen(req,timeout=9) as res:
            result=json.load(res)
            return result,None
    except urllib.error.HTTPError as exc:
        if exc.code==404:return None,"TRADINGVIEW_REFERENCE_NOT_IN_DATABASE"
        return None,"PARITY_LOOKUP_HTTP_"+str(exc.code)
    except (OSError,TimeoutError,ValueError) as exc:
        return None,"PARITY_LOOKUP_ERROR_"+type(exc).__name__

def process(run_id,sid):
    statuses={}
    selected=None
    converted=None
    chart=None
    try:
        stage(run_id,"strategy",STRATEGY,"RUNNING")
        try:
            result=run_graph(run_id,"strategy",STRATEGY,
              {"ui_selection":"strategy","requested_detail_limit":1,"max_pages":3})
            if result.get("source_id") and result.get("version_key") and result.get("status")=="PINE_SAVED_CONVERSION_PENDING":
                selected={"source_id":result["source_id"],"version_key":result["version_key"]}
                statuses["strategy"]="SOURCE_SAVED"
            elif result.get("status")=="NO_FETCHABLE_NEW_PINE":
                statuses["strategy"]="NO_NEW_SOURCE"
            else:
                statuses["strategy"]="UNEXPECTED_RESULT"
            stage(run_id,"strategy",STRATEGY,statuses["strategy"],selected or result)
        except Exception as exc:
            statuses["strategy"]="FAILED"
            stage(run_id,"strategy",STRATEGY,"FAILED",error=str(exc))
        if not selected:
            previous=select_from_db("strategy")
            if previous:
                selected={k:previous[0][k] for k in ("source_id","version_key")}
                stage(run_id,"strategy",STRATEGY,"REUSED_SAVED_SOURCE",selected)
            else:
                stage(run_id,"strategy",STRATEGY,"BLOCKED_NO_SOURCE")
        # Library is a dependency resolution stage for the EXACT selected
        # strategy. Never collect unrelated "one library" as fake progress.
        stage(run_id,"library",LIBRARY,"RUNNING")
        if not selected:
            statuses["library"]="BLOCKED_NO_SELECTED_SOURCE"
            stage(run_id,"library",LIBRARY,statuses["library"])
        else:
            try:
                if os.environ.get("INVESTMENT_DATABASE_URL"):
                    from investment_pg import dependencies_for_source
                    deps=dependencies_for_source(selected["source_id"],selected["version_key"])
                    missing=[d for d in deps["dependencies"] if d["state"]!="PINNED"]
                    statuses["library"]=(
                        "NOT_REQUIRED" if not deps["dependencies"] else
                        "WAITING_DEPENDENCY" if missing else "DEPENDENCIES_PINNED")
                    stage(run_id,"library",LIBRARY,statuses["library"],
                          {"script_version_id":deps["script_version_id"],
                           "dependencies":deps["dependencies"]})
                else:
                    with closing(open_registry()) as db:
                        source=db.execute("""SELECT pine_code FROM investment_pine_payloads
                         WHERE kind='strategy' AND source_id=? AND version_key=?""",
                         (selected["source_id"],selected["version_key"])).fetchone()
                    import re
                    imports=re.findall(r"(?m)^\s*import\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/\d+)\b",
                                       source[0] if source else "")
                    statuses["library"]="WAITING_DEPENDENCY" if imports else "NOT_REQUIRED"
                    stage(run_id,"library",LIBRARY,statuses["library"],{"imports":imports})
            except Exception as exc:
                statuses["library"]="BLOCKED_DEPENDENCY_CHECK_FAILED"
                stage(run_id,"library",LIBRARY,statuses["library"],error=str(exc))
        stage(run_id,"python",PYTHON,"RUNNING")
        if not selected:
            statuses["python"]="BLOCKED_NO_SAVED_STRATEGY"
            stage(run_id,"python",PYTHON,statuses["python"])
        elif statuses["library"] not in ("NOT_REQUIRED","DEPENDENCIES_PINNED"):
            statuses["python"]="BLOCKED_LIBRARY_DEPENDENCY"
            stage(run_id,"python",PYTHON,statuses["python"],selected)
        else:
            # EXACT selected script/version only. Never silently switch to a
            # different strategy just because the selected Pine is unsupported.
            try:
                result=run_graph(run_id,"python",PYTHON,
                    {"ui_selection":"strategy","requested_detail_limit":1,**selected})
                if result.get("status")=="PYTHON_GENERATED" and result.get("python_code"):
                    converted=selected
                    statuses["python"]="PYTHON_GENERATED"
                    stage(run_id,"python",PYTHON,statuses["python"],
                          {**selected,"conversion_id":result.get("conversion_id"),
                           "converter_scope":result.get("converter_scope")})
                elif result.get("status")=="UNSUPPORTED_PINE":
                    statuses["python"]="UNSUPPORTED_SELECTED_PINE"
                    stage(run_id,"python",PYTHON,statuses["python"],
                          {**selected,"unsupported_reason":result.get("unsupported_reason")})
                else:
                    statuses["python"]="BLOCKED_NO_PYTHON_OUTPUT"
                    stage(run_id,"python",PYTHON,statuses["python"],selected)
            except Exception as exc:
                statuses["python"]="FAILED"
                stage(run_id,"python",PYTHON,"FAILED",selected,str(exc))
        stage(run_id,"chart",PARITY,"RUNNING")
        if not converted:
            statuses["chart"]="BLOCKED_PYTHON_NOT_GENERATED"
            stage(run_id,"chart",PARITY,statuses["chart"])
        else:
            source=context_for_source(converted["source_id"],converted["version_key"])
            with closing(open_registry()) as db:
                row=db.execute("""SELECT pine_code FROM investment_pine_payloads
                    WHERE kind='strategy' AND source_id=? AND version_key=?""",
                    (converted["source_id"],converted["version_key"])).fetchone()
            db_comparison=None
            if os.environ.get("INVESTMENT_DATABASE_URL"):
                from investment_pg import comparison_for_source
                db_comparison=comparison_for_source(converted["source_id"],converted["version_key"])
            ref,error=lookup_reference(source["source_url"] if source else None,row[0] if row else "")
            if db_comparison and ref and ref.get("run_id"):
                chart={**db_comparison,"parity_run_id":ref["run_id"],
                       "comparison_url":PARITY_HOST+"/?run="+ref["run_id"]}
                statuses["chart"]="REFERENCE_FOUND_REVIEW_REQUIRED"
                stage(run_id,"chart",PARITY,statuses["chart"],chart)
            else:
                statuses["chart"]="BLOCKED_REAL_TV_CHART_CSV_MISSING"
                stage(run_id,"chart",PARITY,statuses["chart"],{
                    "source_id":converted["source_id"],"version_key":converted["version_key"],
                    "reason":error or "CANONICAL_REFERENCE_OR_COMPARISON_MISSING",
                    "source_url":source.get("source_url") if source else None})
        final=("REVIEW_REQUIRED" if (
           statuses.get("library") in ("NOT_REQUIRED","DEPENDENCIES_PINNED")
           and statuses.get("python")=="PYTHON_GENERATED"
           and statuses.get("chart")=="REFERENCE_FOUND_REVIEW_REQUIRED")
           else "PARTIAL_BLOCKED")
        with closing(open_registry()) as db:
            trace_failures=db.execute("""SELECT count(*) FROM investment_pipeline_events
                WHERE run_id=? AND status='POSTGRES_TRACE_FAILED'""",(run_id,)).fetchone()[0]
        if trace_failures:
            final="FAILED_PERSISTENCE"
        postgres_finish=None
        if os.environ.get("INVESTMENT_DATABASE_URL"):
            try:
                from investment_pg import finish_pipeline_run
                postgres_finish=finish_pipeline_run(run_id,final,selected)
            except Exception as exc:
                final="FAILED_PERSISTENCE"
                postgres_finish={"status":"FAILED","reason":type(exc).__name__+": "+str(exc)[:200]}
        result={"status":final,"stages":statuses,"selected_source":selected,
                "converted_source":converted,"chart":chart,
                "postgres_sync":postgres_finish,
                "postgres_trace_failures":trace_failures,
                "note":"Only stored TradingView chart CSV/screenshots allow visual comparison; no synthetic TV data."}
        with closing(open_registry()) as db:
            db.execute("""UPDATE investment_pipeline_runs SET status=?,finished_at=?,
                selected_source_id=?,selected_version=?,result_json=? WHERE run_id=?""",
                (final,now(),converted["source_id"] if converted else selected["source_id"] if selected else None,
                 converted["version_key"] if converted else selected["version_key"] if selected else None,
                 json.dumps(result,ensure_ascii=False),run_id))
            db.commit()
    except Exception as exc:
        try:
            event(run_id,"chart",PARITY,None,"전체 실행 오류","FAILED",error=str(exc))
        except Exception:
            pass
        if os.environ.get("INVESTMENT_DATABASE_URL"):
            try:
                from investment_pg import finish_pipeline_run
                finish_pipeline_run(run_id,"FAILED",selected,str(exc))
            except Exception as pg_exc:
                print("PIPELINE_POSTGRES_FINALIZATION_FAILED",type(pg_exc).__name__,str(pg_exc)[:200],flush=True)
        with closing(open_registry()) as db:
            db.execute("""UPDATE investment_pipeline_runs
                 SET status='FAILED',finished_at=?,result_json=? WHERE run_id=?""",
                 (now(),json.dumps({"status":"FAILED","error":str(exc)[:1000],
                 "stages":statuses},ensure_ascii=False),run_id))
            db.commit()
    finally:
        with _running_lock:
            _active.discard(run_id)

def start(sid):
    if not isinstance(sid,str) or len(sid)!=48:raise ValueError("PIPELINE_SESSION_REQUIRED")
    with _running_lock:
        with closing(open_registry()) as db:
            latest=db.execute("""SELECT run_id FROM investment_pipeline_runs
                WHERE sid=? AND status='RUNNING' LIMIT 1""",(sid,)).fetchone()
            if latest or _active:raise ValueError("PIPELINE_ALREADY_RUNNING")
            recent=db.execute("""SELECT count(*) FROM investment_pipeline_runs
                    WHERE started_at>datetime('now','-1 day')""").fetchone()[0]
            if recent>=100:raise ValueError("PIPELINE_DAILY_SAFETY_LIMIT")
            run_id=secrets.token_hex(16)
            db.execute("""INSERT INTO investment_pipeline_runs
                (run_id,sid,status,started_at) VALUES(?,?,'RUNNING',?)""",
                (run_id,sid,now()))
            db.commit()
        _active.add(run_id)
        threading.Thread(target=process,args=(run_id,sid),daemon=True,name="investment-pipeline-"+run_id[:8]).start()
    return {"run_id":run_id,"status":"RUNNING"}

def read(sid,run_id=None):
    with closing(open_registry()) as db:
        if run_id:
            row=db.execute("SELECT * FROM investment_pipeline_runs WHERE sid=? AND run_id=?",
                 (sid,run_id)).fetchone()
        else:
            row=db.execute("SELECT * FROM investment_pipeline_runs WHERE sid=? ORDER BY started_at DESC LIMIT 1",
                 (sid,)).fetchone()
        if not row:return {"status":"NOT_STARTED","events":[]}
        events=db.execute("""SELECT event_id,stage,workflow,node_id,node_name,status,payload_json,error,at
          FROM investment_pipeline_events WHERE run_id=? ORDER BY event_id""",(row["run_id"],)).fetchall()
    return {"run_id":row["run_id"],"status":row["status"],
      "started_at":row["started_at"],"finished_at":row["finished_at"],
      "result":json.loads(row["result_json"]),
      "events":[{**dict(e),"payload":json.loads(e["payload_json"])} for e in events]}
