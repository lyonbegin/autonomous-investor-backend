"""WF-02: exact Pine + recursively pinned libraries → PyneComp → PyneCore.

The legacy SMA/EMA and RSI-specific generators are NOT called.
Outputs are GENERATED, never parity VALIDATED. Missing external API key,
sources, or untested runtime dependencies produce explicit blocked states.
"""
import hashlib
import os
import re
from contextlib import closing
from investment_source_registry import open_registry
from investment_pynecomp import (
    COMPILER_ID,PyneCompBlocked,scan_imports,resolve_imports,
    dependency_lock,sha,compile_remote,cached,save_cache,compiler_status
)
WF02_PATH="operations/WF02-pine-to-python.json"
BLOCKED={"PINNED_LIBRARY_SOURCE_MISSING","PYNECOMP_API_KEY_MISSING",
         "PYNECOMP_AUTH_DENIED","PYNECOMP_QUOTA_EXCEEDED",
         "PYNECOMP_API_UNREACHABLE","PYNECOMP_HTTP_ERROR",
         "PYNECOMP_INVALID_RESPONSE","PYNECOMP_INVALID_ENCODING",
         "PYNECOMP_GENERATED_PYTHON_SYNTAX_INVALID",
         "PYNECOMP_EMPTY_OR_OVERSIZED_PYTHON",
         "PYNECOMP_RUNTIME_NOT_INSTALLED","PYNECOMP_INVALID_FILENAME",
         "CYCLIC_PINE_LIBRARY_DEPENDENCY","TOO_MANY_LIBRARY_IMPORTS",
         "PINNED_LIBRARY_ID_VERSION_MISMATCH",
         "LIBRARY_SOURCE_SHA256_MISMATCH","AMBIGUOUS_PINE_LIBRARY_VERSION",
         "NOT_A_PINE_LIBRARY","PINE_SOURCE_TOO_LARGE","PINE_SOURCE_EMPTY",
         "PINNED_LIBRARY_SOURCE_ACCESS_FAILED",
         "PINE_LIBRARY_DEPENDENCY_NOT_PINNED"}

def blocked(previous,reason,step):
    return {k:v for k,v in previous.items() if k not in
            ("pine_code","python_code","resolved_libraries","compiled_libraries")} | {
        "status":reason,"blocked_at":step,"conversion_validated":False,
        "tradingview_chart_validated":False,"python_code":None,
        "paper_enabled":False,"live_orders_enabled":False}

def execute_wf02_node01(input_json,*,workflow_kind):
    """Read the exact existing DB version, not another script after failure."""
    if workflow_kind!="strategy" or not isinstance(input_json,dict):
        raise ValueError("WF02_STRATEGY_INPUT_REQUIRED")
    if input_json.get("ui_selection")!="strategy" or input_json.get("requested_detail_limit")!=1:
        raise ValueError("WF02_MANUAL_SELECTION_REQUIRED")
    sid,version=input_json.get("source_id"),input_json.get("version_key")
    if (sid is None)!=(version is None) or (
        sid is not None and (not isinstance(sid,str) or not isinstance(version,str) or
        not 1<=len(sid)<=240 or not 1<=len(version)<=150)):
        raise ValueError("WF02_EXACT_ID_AND_VERSION_REQUIRED_TOGETHER")
    with closing(open_registry()) as db:
        names={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "investment_pine_payloads" not in names:
            raise ValueError("WF02_NO_STORED_PINE")
        if sid is None:
            row=db.execute("""SELECT source_id,version_key,pine_code,rights_state FROM
                 investment_pine_payloads WHERE kind='strategy'
                 ORDER BY saved_at DESC,rowid DESC LIMIT 1""").fetchone()
        else:
            row=db.execute("""SELECT source_id,version_key,pine_code,rights_state FROM
                investment_pine_payloads WHERE kind='strategy'
                AND source_id=? AND version_key=?""",(sid,version)).fetchone()
    if not row or not row["pine_code"].strip():raise ValueError("WF02_PINE_NOT_IN_DATABASE")
    # Never send an unapproved source to the external PyneComp service.
    # Permission must be checked again at execution, not only during intake.
    if row["rights_state"] != "APPROVED":
        raise ValueError("WF02_SOURCE_RIGHTS_NOT_APPROVED")
    pine=row["pine_code"]
    try:scan_imports(pine)
    except PyneCompBlocked as exc:raise ValueError(exc.code) from None
    canonical=None
    if os.getenv("INVESTMENT_DATABASE_URL"):
        from investment_pg import get_source
        canonical=get_source(row["source_id"],row["version_key"])
        if canonical["pine_code"]!=pine or canonical["source_sha256"]!=sha(pine):
            raise ValueError("POSTGRES_SQLITE_SOURCE_CONTENT_MISMATCH")
    return {"kind":"strategy","script_version_id":canonical["script_version_id"] if canonical else None,
        "source_id":row["source_id"],"version_key":row["version_key"],
        "source_sha256":sha(pine),"pine_code":pine,
        "rights_state":row["rights_state"],
        "status":"PINE_LOADED","converter_scope":"PYNECOMP_FULL_PINE",
        "conversion_validated":False,"tradingview_chart_validated":False}

def _load_exact_library(import_name):
    parts=import_name.split("/")
    if len(parts)!=3:return None
    if os.getenv("INVESTMENT_DATABASE_URL"):
        from investment_pg import pine_library_by_import_path
        return pine_library_by_import_path(import_name)
    with closing(open_registry()) as db:
        row=db.execute("""SELECT pine_code FROM investment_pine_payloads
          WHERE kind='library' AND source_id=? AND version_key=?""",
          ("/".join(parts[:2]),parts[2])).fetchone()
    if not row:return None
    return {"kind":"library","source_id":"/".join(parts[:2]),
        "version_key":parts[2],"source_sha256":sha(row[0]),"pine_code":row[0]}

def execute_wf02_node02(input_json,*,workflow_kind):
    """Recursively find exact Pine library versions; no stand-in placeholders."""
    if workflow_kind!="strategy" or input_json.get("status")!="PINE_LOADED":
        raise ValueError("WF02_PINE_INPUT_MISSING")
    pine=input_json["pine_code"]
    requested=scan_imports(pine)
    try:libs=resolve_imports(pine,_load_exact_library)
    except PyneCompBlocked as exc:
        return {**blocked(input_json,exc.code,"LIBRARY_RESOLUTION"),
            "requested_imports":requested}
    except (ValueError,OSError) as exc:
        return {**blocked(input_json,"PINNED_LIBRARY_SOURCE_ACCESS_FAILED","LIBRARY_RESOLUTION"),
            "requested_imports":requested,"diagnostic_type":type(exc).__name__}
    return {**input_json,"status":"LIBRARIES_RESOLVED",
        "requested_imports":requested,"resolved_libraries":libs,
        "dependency_lock_hash":dependency_lock(libs),
        "library_count":len(libs)}

def execute_wf02_node03(input_json,*,workflow_kind):
    """Compile missing libraries in dependency order; reuse ONLY exact PyneComp cache."""
    if workflow_kind!="strategy":raise ValueError("WF02_STRATEGY_REQUIRED")
    if input_json.get("status")!="LIBRARIES_RESOLVED":return input_json
    libs=input_json.get("resolved_libraries",[])
    outputs=[]
    for i,lib in enumerate(libs):
        lock=dependency_lock(libs[:i])
        code=cached("library",lib["source_id"],lib["version_key"],lib["source_sha256"],lock)
        hit=code is not None
        if code is None:
            try:code=compile_remote(lib["pine_code"],filename="pine_library.pine")
            except PyneCompBlocked as exc:
                return {**blocked(input_json,exc.code,"LIBRARY_COMPILATION"),
                    "blocked_import":lib["import_name"],"libraries_compiled":len(outputs)}
            save_cache("library",lib["source_id"],lib["version_key"],
                       lib["source_sha256"],lock,code,lib["module_path"])
            if os.getenv("INVESTMENT_DATABASE_URL"):
                from investment_pg import record_conversion
                record_conversion(lib["source_id"],lib["version_key"],code,
                                  COMPILER_ID,"PYNECOMP_LIBRARY_UNVALIDATED")
        outputs.append({"import_name":lib["import_name"],"source_id":lib["source_id"],
            "version_key":lib["version_key"],"source_sha256":lib["source_sha256"],
            "module_path":lib["module_path"],"python_code":code,"cache_hit":hit})
    return {**input_json,"status":"PYNECOMP_LIBRARIES_COMPILED",
        "compiled_libraries":outputs,"library_code_cache_hits":sum(x["cache_hit"] for x in outputs)}

def execute_wf02_node04(input_json,*,workflow_kind):
    """Call only the documented PyneComp service; never legacy handwritten generators."""
    if workflow_kind!="strategy":raise ValueError("WF02_STRATEGY_REQUIRED")
    if input_json.get("status")!="PYNECOMP_LIBRARIES_COMPILED":return input_json
    sid,version=input_json["source_id"],input_json["version_key"]
    lock=input_json["dependency_lock_hash"]
    code=cached("strategy",sid,version,input_json["source_sha256"],lock)
    cached_hit=code is not None
    if code is None:
        try:code=compile_remote(input_json["pine_code"],filename="strategy.pine")
        except PyneCompBlocked as exc:
            return blocked(input_json,exc.code,"STRATEGY_COMPILATION")
    return {**input_json,"status":"PYNECOMP_CODE_COMPILED",
        "python_code":code,"compiler_id":COMPILER_ID,
        "strategy_code_cache_hit":cached_hit}

def execute_wf02_node05(input_json,*,workflow_kind):
    """Persist exact PyneComp output, label it GENERATED, not parity VALIDATED."""
    if workflow_kind!="strategy":raise ValueError("WF02_STRATEGY_REQUIRED")
    if input_json.get("status")!="PYNECOMP_CODE_COMPILED":return input_json
    try:
        import importlib.metadata
        installed=importlib.metadata.version("pynesys-pynecore")
    except importlib.metadata.PackageNotFoundError:
        return blocked(input_json,"PYNECOMP_RUNTIME_NOT_INSTALLED","PYNECORE_INSTALL")
    sid,version=input_json["source_id"],input_json["version_key"]
    code=input_json["python_code"]
    lock=input_json["dependency_lock_hash"]
    pg_result=None
    if os.getenv("INVESTMENT_DATABASE_URL"):
        from investment_pg import refresh_exact_dependency_pins,record_conversion
        refresh_exact_dependency_pins(sid,version,input_json["resolved_libraries"])
        pg_result=record_conversion(sid,version,code,COMPILER_ID,"PYNECOMP_FULL_PINE_UNVALIDATED")
    save_cache("strategy",sid,version,input_json["source_sha256"],lock,code)
    # Linked library modules are saved but still require import-time verification
    # against the PyneCore runtime before execution or agent approval.
    library_linked=not input_json["compiled_libraries"]
    return {**input_json,"status":"PYNECOMP_GENERATED_UNVALIDATED",
        "converter_scope":"PYNECOMP_FULL_PINE",
        "pynecore_runtime_version":installed,
        "conversion_id":pg_result["conversion_id"] if pg_result else None,
        "postgres_sync":pg_result is not None,
        "library_import_linkage_verified":library_linked,
        "runtime_execution_verified":False,
        "conversion_validated":False,"tradingview_chart_validated":False}

def execute_wf02_node06(input_json,*,workflow_kind):
    """Report genuine generated code or precise blocker, never enable trading."""
    if workflow_kind!="strategy":raise ValueError("WF02_STRATEGY_REQUIRED")
    result={k:v for k,v in input_json.items() if k not in
            ("pine_code","resolved_libraries","compiled_libraries")}
    return {**result,"paper_enabled":False,"live_orders_enabled":False,
        "conversion_validated":False,"tradingview_chart_validated":False,
        "compiler":compiler_status()}
