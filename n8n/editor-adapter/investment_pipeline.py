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
        db.execute("""CREATE TABLE IF NOT EXISTS investment_tv_publication_previews (
          source_id TEXT NOT NULL, version_key TEXT NOT NULL,
          source_sha256 TEXT NOT NULL, publication_id TEXT NOT NULL,
          original_page_url TEXT NOT NULL, published_chart_image_url TEXT NOT NULL,
          evidence TEXT NOT NULL, observed_on TEXT NOT NULL,
          source_byte_match_verified INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(source_id,version_key,source_sha256)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS investment_source_context (
          kind TEXT NOT NULL, source_id TEXT NOT NULL, version_key TEXT NOT NULL,
          source_url TEXT NOT NULL, source_title TEXT,
          observed_at TEXT NOT NULL, PRIMARY KEY(kind,source_id,version_key)
        )""")
        has_sources=bool(db.execute("""SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='investment_pine_payloads'""").fetchone())
        if has_sources:
            for (sid,version,sha),pub in TV_PUBLICATION_SNAPSHOTS.items():
                stored=db.execute("""SELECT pine_code FROM investment_pine_payloads
                    WHERE kind='strategy' AND source_id=? AND version_key=?""",
                    (sid,version)).fetchone()
                if not stored or hashlib.sha256(stored[0].encode("utf-8")).hexdigest()!=sha:
                    continue
                db.execute("""INSERT INTO investment_tv_publication_previews
                   (source_id,version_key,source_sha256,publication_id,original_page_url,
                    published_chart_image_url,evidence,observed_on,source_byte_match_verified)
                   VALUES(?,?,?,?,?,?,?,?,0) ON CONFLICT DO NOTHING""",
                   (sid,version,sha,pub["publication_id"],pub["page_url"],
                    pub["image_url"],pub["evidence"],pub["verified_on"]))
                old=db.execute("""SELECT source_url FROM investment_source_context
                    WHERE kind='strategy' AND source_id=? AND version_key=?""",
                    (sid,version)).fetchone()
                if old and old[0]!=pub["page_url"]:
                    print("TV_PUBLICATION_ORIGINAL_URL_CONFLICT",sid,version,flush=True)
                    continue
                db.execute("""INSERT INTO investment_source_context
                    (kind,source_id,version_key,source_url,source_title,observed_at)
                    VALUES('strategy',?,?,?,?,?)
                    ON CONFLICT(kind,source_id,version_key) DO NOTHING""",
                    (sid,version,pub["page_url"],pub["title"],now()))

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

def select_supported_saved_strategy():
    """Prefer exactly cached PyneComp source; never test with removed RSI/SMA parsers."""
    with closing(open_registry()) as db:
        names={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "investment_pine_payloads" not in names:return None
        candidates=db.execute("""SELECT source_id,version_key,pine_code FROM
           investment_pine_payloads WHERE kind='strategy'
           ORDER BY saved_at DESC LIMIT 120""").fetchall()
        compiled=set()
        if "investment_pynecomp_artifacts" in names:
            compiled={(x[0],x[1],x[2]) for x in db.execute(
                "SELECT source_id,version_key,source_sha256 FROM investment_pynecomp_artifacts "
                "WHERE kind='strategy' AND compiler_id='pynecomp-http-v1-pynecore-6.11.1'")}
    if not candidates:return None
    preferred=[]
    for row in candidates:
        pine=row["pine_code"]
        source_sha=hashlib.sha256(pine.encode("utf-8")).hexdigest()
        preferred.append({"source_id":row["source_id"],"version_key":row["version_key"],
          "source_sha256":source_sha,
          "selection_basis":"EXACT_PYNECOMP_CACHE" if
          (row["source_id"],row["version_key"],source_sha) in compiled
          else "SAVED_SOURCE_REQUIRES_PYNECOMP_COMPILATION"})
    preferred.sort(key=lambda x:0 if x["selection_basis"]=="EXACT_PYNECOMP_CACHE" else 1)
    return preferred[0]


# This mapping is limited to a publication directly inspected in a real
# TradingView browser on 2026-11-03. The public Pine Editor link exposes the
# same PUB ID, but the publication's source bytes have NOT been proven equal
# to the saved internal Pine version. Never label the screenshot TV parity.
TV_PUBLICATION_SNAPSHOTS={
  ("PUB;67a1548c0960450086a19d5b0ef1d467","1.0",
   "bc7eb79dc2ea81f5a1e8d43521b720c2d6689e8bdb19f21f3e861322f5707b04"):{
    "title":"Sequence Snap | RSI-Confirmed Reversal Scalper",
    "page_url":"https://www.tradingview.com/script/49jNhJXM-Sequence-Snap-RSI-Confirmed-Reversal-Scalper/",
    "image_url":"https://s3.tradingview.com/4/49jNhJXM_mid.webp",
    "publication_id":"49jNhJXM",
    "pine_editor_source_id":"PUB;67a1548c0960450086a19d5b0ef1d467",
    "published_chart_symbol":"NASDAQ:NVDA",
    "published_chart_timeframe":"2h",
    "evidence":"ACTUAL_TRADINGVIEW_PAGE_AND_PINE_EDITOR_ID_OBSERVED",
    "verified_on":"2026-11-03",
    "source_byte_match_verified":False,
    "strategy_report_parity_verified":False,
    "published_snapshot_not_live_chart":True
  }
}


def tv_publication_for(source_id,version_key,sha):
    return TV_PUBLICATION_SNAPSHOTS.get((source_id,version_key,sha))


def exact_stored_pine(source_id,version_key):
    """Return EXACT pinned Pine used by the DB workflow, never a same-ID latest fallback."""
    if not isinstance(source_id,str) or not 1<=len(source_id)<=240:
        raise ValueError("SOURCE_ID_REQUIRED")
    if not isinstance(version_key,str) or not 1<=len(version_key)<=150:
        raise ValueError("VERSION_KEY_REQUIRED")
    with closing(open_registry()) as db:
        row=db.execute("""SELECT pine_code,rights_state FROM investment_pine_payloads
            WHERE kind='strategy' AND source_id=? AND version_key=?""",
            (source_id,version_key)).fetchone()
    if row is None:raise ValueError("EXACT_STRATEGY_VERSION_NOT_IN_DB")
    code=row["pine_code"]
    if not isinstance(code,str) or not code.strip() or len(code.encode("utf-8"))>512*1024:
        raise ValueError("PINNED_SOURCE_EMPTY_OR_TOO_LARGE")
    sha=hashlib.sha256(code.encode("utf-8")).hexdigest()
    version_uuid=None
    if os.environ.get("INVESTMENT_DATABASE_URL"):
        from investment_pg import get_source
        canonical=get_source(source_id,version_key)
        if canonical["source_sha256"]!=sha or canonical["pine_code"]!=code:
            raise ValueError("CANONICAL_PINE_VERSION_MISMATCH")
        version_uuid=canonical["script_version_id"]
        if tv_publication_for(source_id,version_key,sha):
            from investment_pg import link_original_tradingview_publication
            link_original_tradingview_publication(
                source_id,version_key,sha,
                tv_publication_for(source_id,version_key,sha)["page_url"])
    context=context_for_source(source_id,version_key)
    publication=tv_publication_for(source_id,version_key,sha)
    return {"source_id":source_id,"version_key":version_key,
       "tradingview_publication":publication,
       "tradingview_original_url":(context or {}).get("source_url"),
       "tradingview_original_title":(context or {}).get("source_title"),
       "source_sha256":sha,"source":code,"kind":"strategy",
       "rights_state":row["rights_state"],"script_version_id":version_uuid,
       "original_record":"SQLITE_WITH_POSTGRES_READBACK" if version_uuid else "SQLITE_ONLY"}


def saved_sources(limit=80):
    """Public metadata, no Pine source body; caller may pin an exact DB version."""
    if type(limit) is not int or not 1<=limit<=120:
        raise ValueError("INVALID_SOURCE_PAGE_LIMIT")
    records=select_from_db("strategy")[:limit]
    with closing(open_registry()) as db:
        names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        already=set()
        if "investment_python_conversions" in names:
            already={(x["source_id"],x["version_key"]) for x in db.execute(
                "SELECT source_id,version_key FROM investment_python_conversions WHERE kind='strategy'")}
        hashes={(row["source_id"],row["version_key"]):
                hashlib.sha256(row["pine_code"].encode("utf-8")).hexdigest()
                for row in db.execute("""SELECT source_id,version_key,pine_code
                         FROM investment_pine_payloads WHERE kind='strategy'""")}
    with closing(open_registry()) as db:
        name_set={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        pynecomp_rows=set()
        if "investment_pynecomp_artifacts" in name_set:
            pynecomp_rows={(x[0],x[1],x[2]) for x in db.execute(
                "SELECT source_id,version_key,source_sha256 FROM investment_pynecomp_artifacts "
                "WHERE kind='strategy' AND compiler_id='pynecomp-http-v1-pynecore-6.11.1'")}
    result=[{**{k:row[k] for k in ("source_id","version_key","rights_state","saved_at","chars")},
        "source_sha256":hashes.get((row["source_id"],row["version_key"])),
        "legacy_python_code_stored":(row["source_id"],row["version_key"]) in already,
        "pynecomp_generated_stored":(row["source_id"],row["version_key"],
            hashes.get((row["source_id"],row["version_key"]))) in pynecomp_rows}
        for row in records]
    result.sort(key=lambda x:(not x["pynecomp_generated_stored"],x["source_id"]))
    for entry in result:
        context=context_for_source(entry["source_id"],entry["version_key"])
        pub=tv_publication_for(entry["source_id"],entry["version_key"],entry["source_sha256"])
        entry["tradingview_publication"]=pub
        entry["tradingview_original_url"]=(pub or {}).get("page_url") or (context or {}).get("source_url")
        entry["tradingview_original_title"]=(pub or {}).get("title") or (context or {}).get("source_title")
    return {"status":"ok","sources":result,"count":len(result),
            "source":"EXISTING_SQLITE_SOURCE_REGISTRY",
            "note":"legacy_python_code_stored is NOT PyneComp output; pynecomp_generated_stored is not yet PyneCore/TradingView parity verified",
            "pynecomp":__import__("investment_pynecomp").compiler_status()}


def validate_selected(source):
    if source is None:return None
    if not isinstance(source,dict) or set(source)!={"source_id","version_key"}:
        raise ValueError("EXACT_SOURCE_ID_AND_VERSION_REQUIRED")
    sid,version=source["source_id"],source["version_key"]
    if not isinstance(sid,str) or not isinstance(version,str) or not (1<=len(sid)<=240 and 1<=len(version)<=150):
        raise ValueError("INVALID_EXPLICIT_SOURCE_ID_OR_VERSION")
    with closing(open_registry()) as db:
        exists=db.execute("""SELECT 1 FROM investment_pine_payloads
             WHERE kind='strategy' AND source_id=? AND version_key=?""",
             (sid,version)).fetchone()
    if not exists:raise ValueError("EXPLICIT_SOURCE_VERSION_NOT_IN_DATABASE")
    return dict(source)


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
        # A successful HTTP/Python invocation is not proof of successful
        # Pine conversion or of a new TradingView source.
        node_state=("UNSUPPORTED_PINE" if output.get("status")=="UNSUPPORTED_PINE"
                    else "NO_NEW_SOURCE" if output.get("status") in (
                        "NO_FETCHABLE_NEW_PINE","NO_NEW_SOURCE")
                    else "SUCCESS")
        event(run_id,stage_name,path,node["id"],node["name"],node_state,
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

def actual_python_chart_for_exact_source(selected):
    """Execute the restored original-source Python chart path on real market OHLCV.
    This is research/visual review, never TradingView website plot parity.
    """
    pine=exact_stored_pine(selected["source_id"],selected["version_key"])
    symbol=os.environ.get("INVESTMENT_CHART_SYMBOL","NASDAQ:NVDA")
    horizon=os.environ.get("INVESTMENT_CHART_HORIZON","2h")
    if not 1<=len(symbol)<=100 or not 1<=len(horizon)<=12:
        raise ValueError("CHART_SYMBOL_OR_HORIZON_INVALID")
    public=os.environ.get("INVESTMENT_PUBLIC_API",
        "https://autonomous-investor-public-api-production.up.railway.app").rstrip("/")
    params=urllib.parse.urlencode({"version":selected["version_key"],
       "sha256":pine["source_sha256"],"symbol":symbol,"horizon":horizon})
    url=public+"/api/public/scripts/"+urllib.parse.quote(selected["source_id"],safe="")+"/compare-exact?"+params
    req=urllib.request.Request(url,headers={"User-Agent":"investment-WF02-chart-v1",
                                             "Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=100) as response:
            data=json.load(response)
    except urllib.error.HTTPError as exc:
        raise ValueError("EXACT_CHART_API_HTTP_"+str(exc.code)) from exc
    except (OSError,TimeoutError,ValueError) as exc:
        raise ValueError("EXACT_CHART_API_NOT_READY_"+type(exc).__name__) from exc
    if data.get("mode")!="EXACT_PINNED_STUDIO_SOURCE":
        raise ValueError("CHART_NOT_PINNED_TO_STUDIO_DB")
    chart=data.get("chart") or {}
    source=data.get("source") or {}
    if (chart.get("source_hash")!=pine["source_sha256"] or
        source.get("source_sha256")!=pine["source_sha256"] or
        source.get("version_key")!=selected["version_key"] or
        chart.get("script_id")!=selected["source_id"]):
        raise ValueError("CHART_SOURCE_VERSION_MISMATCH")
    bars=chart.get("bars") or []
    visual=chart.get("visual") or {}
    if len(bars)<50 or visual.get("adapter") in (None,"unsupported") or visual.get("error"):
        raise ValueError("REAL_MARKET_OR_PYTHON_CHART_UNSUPPORTED:"+str(visual.get("error"))[:180])
    meta=chart.get("market_data") or {}
    if not meta.get("provider") or not meta.get("count"):
        raise ValueError("CHART_MARKET_PROVENANCE_MISSING")
    preview_url=("https://autonomous-investor-public-production.up.railway.app/compare/"+
         urllib.parse.quote(selected["source_id"],safe="")+"?"+
         urllib.parse.urlencode({"version":selected["version_key"],
             "sha256":pine["source_sha256"],"symbol":symbol,"horizon":horizon}))
    return {"status":"CHART_PREVIEW_READY_TV_PARITY_PENDING",
       "source_id":selected["source_id"],"version_key":selected["version_key"],
       "source_sha256":pine["source_sha256"],
       "script_version_id":pine["script_version_id"],
       "symbol":chart.get("symbol"),"horizon":chart.get("horizon"),
       "market_provider":meta["provider"],"bar_count":len(bars),
       "python_adapter":visual["adapter"],
       "python_markers":len(visual.get("markers") or []),
       "python_trade_count":len(visual.get("trades") or []),
       "preview_url":preview_url,"same_ohlcv":data.get("same_ohlcv") is True,
       "tv_website_parity_verified":False,"data_provider":meta["provider"]}


def process(run_id,sid,requested_source=None):
    statuses={}
    selected=None
    converted=None
    chart=None
    try:
        stage(run_id,"strategy",STRATEGY,"RUNNING")
        if requested_source:
            selected=dict(requested_source)
            statuses["strategy"]="REUSED_EXACT_DB_SOURCE"
            stage(run_id,"strategy",STRATEGY,statuses["strategy"],selected)
        else:
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
                usable=select_supported_saved_strategy()
                if usable:
                    selected={k:usable[k] for k in ("source_id","version_key")}
                    statuses["strategy"]="REUSED_SAVED_SUPPORTED_SOURCE"
                    stage(run_id,"strategy",STRATEGY,statuses["strategy"],
                          {**usable,"note":"AUTO_FALLBACK_ONLY_AFTER_NO_NEW_PINE; EXACT_SOURCE_PINNED_FOR_ALL_NEXT_STAGES"})
                else:
                    statuses["strategy"]="BLOCKED_NO_CONVERTIBLE_SAVED_SOURCE"
                    stage(run_id,"strategy",STRATEGY,statuses["strategy"],
                          {"reason":"No DB Pine version with saved and still supported Python conversion"})

        # Library is a dependency resolution stage for the EXACT selected
        # strategy. Never collect unrelated "one library" as fake progress.
        stage(run_id,"library",LIBRARY,"RUNNING")
        if not selected:
            statuses["library"]="BLOCKED_NO_SELECTED_SOURCE"
            stage(run_id,"library",LIBRARY,statuses["library"])
        else:
            try:
                # Actual recursive Pine Library resolution now runs inside WF02-N02.
                # The old PINNED metadata state alone is no longer sufficient.
                from investment_pynecomp import scan_imports
                with closing(open_registry()) as db:
                    row=db.execute("""SELECT pine_code FROM investment_pine_payloads
                       WHERE kind='strategy' AND source_id=? AND version_key=?""",
                       (selected["source_id"],selected["version_key"])).fetchone()
                if not row:raise ValueError("EXACT_PINE_SOURCE_NOT_IN_DATABASE")
                imports=scan_imports(row[0])
                statuses["library"]="NOT_REQUIRED" if not imports else "RESOLVE_WITH_PYNECOMP"
                stage(run_id,"library",LIBRARY,statuses["library"],
                    {"requested_imports":imports,
                     "resolution_workflow":"WF02_N02_N03","resolved":not imports})
            except Exception as exc:
                statuses["library"]="BLOCKED_DEPENDENCY_CHECK_FAILED"
                stage(run_id,"library",LIBRARY,statuses["library"],error=str(exc))
        stage(run_id,"python",PYTHON,"RUNNING")
        if not selected:
            statuses["python"]="BLOCKED_NO_SAVED_STRATEGY"
            stage(run_id,"python",PYTHON,statuses["python"])
        elif statuses["library"] not in ("NOT_REQUIRED","RESOLVE_WITH_PYNECOMP"):
            statuses["python"]="BLOCKED_LIBRARY_DEPENDENCY"
            stage(run_id,"python",PYTHON,statuses["python"],selected)
        else:
            try:
                result=run_graph(run_id,"python",PYTHON,
                    {"ui_selection":"strategy","requested_detail_limit":1,**selected})
                if result.get("status")=="PYNECOMP_GENERATED_UNVALIDATED" and result.get("python_code"):
                    converted=selected
                    statuses["python"]="PYNECOMP_GENERATED_UNVALIDATED"
                    stage(run_id,"python",PYTHON,statuses["python"],
                        {**selected,"conversion_id":result.get("conversion_id"),
                         "converter_scope":"PYNECOMP_FULL_PINE",
                         "library_import_linkage_verified":
                             result.get("library_import_linkage_verified",False),
                         "runtime_execution_verified":False})
                else:
                    statuses["python"]="BLOCKED_"+str(result.get("status","UNKNOWN"))[:96]
                    stage(run_id,"python",PYTHON,statuses["python"],
                        {**selected,
                         "blocked_at":result.get("blocked_at"),
                         "requested_imports":result.get("requested_imports"),
                         "blocked_import":result.get("blocked_import"),
                         "reason":result.get("status")})
            except Exception as exc:
                statuses["python"]="FAILED"
                stage(run_id,"python",PYTHON,"FAILED",selected,
                      type(exc).__name__+": "+str(exc)[:260])
        stage(run_id,"chart",PARITY,"RUNNING")
        # No legacy restricted Python graph is allowed to masquerade as output
        # of the new PyneComp/PyneCore compiler.
        if converted:
            statuses["chart"]="BLOCKED_PYNECORE_RUNTIME_GRAPH_NOT_CONNECTED"
            stage(run_id,"chart",PARITY,statuses["chart"],
                 {**converted,"reason":
                  "PyneComp code generated but PyneCore runtime/OHLCV and TradingView keypoint parity not independently executed",
                  "legacy_chart_is_not_pynecore_output":True})
        else:
            statuses["chart"]="BLOCKED_PYNECOMP_CONVERSION_NOT_READY"
            stage(run_id,"chart",PARITY,statuses["chart"],
                  {"reason":statuses.get("python")})
        final="PARTIAL_BLOCKED"
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
                "requested_source":requested_source,
                "selection_mode":"EXPLICIT_PINNED" if requested_source else
                   "AUTO_NEW_OR_SAVED_PYNECOMP_CACHE_PRIORITY",
                "converted_source":converted,"chart":chart,
                "postgres_sync":postgres_finish,
                "postgres_trace_failures":trace_failures,
                "note":"PyneComp-generated code is NOT yet executed against the TradingView keypoints. Legacy Quant graphs are not PyneCore evidence."}
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

def start(sid,selected_source=None):
    if not isinstance(sid,str) or len(sid)!=48:raise ValueError("PIPELINE_SESSION_REQUIRED")
    selected_source=validate_selected(selected_source)
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
                (run_id,sid,status,started_at,result_json) VALUES(?,?,'RUNNING',?,?)""",
                (run_id,sid,now(),json.dumps({"requested_source":selected_source},ensure_ascii=False)))
            db.commit()
        _active.add(run_id)
        threading.Thread(target=process,args=(run_id,sid,selected_source),daemon=True,name="investment-pipeline-"+run_id[:8]).start()
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
    canonical={"status":"NOT_CONFIGURED"}
    if os.environ.get("INVESTMENT_DATABASE_URL"):
        try:
            from investment_pg import canonical_pipeline_record
            canonical=canonical_pipeline_record(row["run_id"])
        except Exception as exc:
            canonical={"status":"READ_FAILED","reason":type(exc).__name__+": "+str(exc)[:180]}
    if row["status"] not in ("RUNNING","INTERRUPTED") and canonical.get("status")!=row["status"]:
        canonical["status_mismatch"]=True
    return {"run_id":row["run_id"],"status":row["status"],
      "started_at":row["started_at"],"finished_at":row["finished_at"],
      "result":json.loads(row["result_json"]), "canonical_postgres":canonical,
      "events":[{**dict(e),"payload":json.loads(e["payload_json"])} for e in events]}
