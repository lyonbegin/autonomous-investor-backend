"""FREE, local Pine v6 → Python using hoox-pyne (AGPL-3.0).

No PyneComp API key, remote request, or silent fallback. 100% of Pine source
is fed to the CLI; generated code is genuine hoox-pyne emitter output.
This module DOES NOT claim TradingView order/fill/plot parity. Compilation
happens in a bounded isolated process, generated user code is NOT executed
on the public HTTP handler.
"""
from __future__ import annotations
from contextlib import closing
from datetime import datetime,timezone
import ast
import hashlib
import importlib.metadata
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from investment_source_registry import open_registry

COMPILER_ID="hoox-pyne-0.6.31-offline"
VERSION="0.6.31"
MAX_PINE_BYTES=512*1024
MAX_PY_BYTES=3*1024*1024
COMPILE_TIMEOUT_SEC=65

class FreePineBlocked(ValueError):
    def __init__(self,code:str):
        if not re.fullmatch(r"PYNE_FREE_[A-Z0-9_]{4,80}",code):
            code="PYNE_FREE_UNEXPECTED_FAILURE"
        super().__init__(code)
        self.code=code

def hash_source(text:str)->str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def installed() -> bool:
    try:
        return importlib.metadata.version("hoox-pyne")==VERSION and shutil.which("pyne") is not None
    except importlib.metadata.PackageNotFoundError:
        return False

def status()->dict:
    return {
        "engine":"PYNE (hoox-sh/pyne) free local Pine v6 → Python",
        "compiler":COMPILER_ID,
        "version":VERSION,
        "installed":installed(),
        "api_key_required":False,
        "api_key_configured":False,
        "local_only":True,
        "license":"AGPL-3.0",
        "strategy_parity_verified":False,
        "runtime":"PYNE; NOT PyneCore",
        "live_orders_enabled":False,
    }

def _limit_child():
    # subprocess is short lived, no paid API, and runs untrusted Pine only
    # through compiler. Generated Python MUST NOT be imported in web server.
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(55,60))
        resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_PY_BYTES,MAX_PY_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
    except (ImportError,ValueError,OSError):
        pass

def compile_pine(pine:str, *, expected_sha:str|None=None,
                 timeout:int=COMPILE_TIMEOUT_SEC)->str:
    if not isinstance(pine,str) or not pine.strip():
        raise FreePineBlocked("PYNE_FREE_PINE_EMPTY")
    blob=pine.encode("utf-8")
    if len(blob)>MAX_PINE_BYTES:
        raise FreePineBlocked("PYNE_FREE_PINE_TOO_LARGE")
    if expected_sha is not None and expected_sha!=hash_source(pine):
        raise FreePineBlocked("PYNE_FREE_SOURCE_SHA_MISMATCH")
    if not re.search(r"(?m)^\s*//@version=[456]\s*$",pine):
        raise FreePineBlocked("PYNE_FREE_VERSION_UNSUPPORTED")
    if not re.search(r"(?m)^\s*(strategy|indicator|library)\s*\(",pine):
        raise FreePineBlocked("PYNE_FREE_PINE_DECLARATION_MISSING")
    if re.search(r"(?m)^\s*import\s+\S+",pine):
        # No placeholder library handling. Needs separate explicit pinned
        # library cross-module compatibility implementation.
        raise FreePineBlocked("PYNE_FREE_LIBRARY_IMPORT_UNSUPPORTED")
    if not installed():
        raise FreePineBlocked("PYNE_FREE_RUNTIME_NOT_INSTALLED")
    with tempfile.TemporaryDirectory(prefix="wf02-pyne-") as temp:
        root=Path(temp)
        src=root/"source.pine";dest=root/"generated.py"
        src.write_bytes(blob)
        try:
            outcome=subprocess.run(
                ["pyne","compile",str(src),"--emit","-o",str(dest)],
                cwd=temp, stdin=subprocess.DEVNULL,capture_output=True,
                text=True,timeout=min(max(int(timeout),1),120),
                env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"},
                preexec_fn=_limit_child if os.name=="posix" else None,
            )
        except subprocess.TimeoutExpired:
            raise FreePineBlocked("PYNE_FREE_COMPILE_TIMEOUT") from None
        except OSError:
            raise FreePineBlocked("PYNE_FREE_COMPILE_UNAVAILABLE") from None
        if outcome.returncode!=0:
            raise FreePineBlocked("PYNE_FREE_PINE_COMPILE_FAILED")
        if not dest.is_file() or dest.stat().st_size>MAX_PY_BYTES:
            raise FreePineBlocked("PYNE_FREE_PYTHON_OUTPUT_INVALID")
        try:
            generated=dest.read_text(encoding="utf-8")
            parsed=ast.parse(generated,filename="<PYNE exact Pine generated>")
            if not any(isinstance(node,ast.FunctionDef) and
                       node.name=="execute_script_compiled" for node in parsed.body):
                raise FreePineBlocked("PYNE_FREE_EXECUTION_ENTRYPOINT_MISSING")
        except (UnicodeError,SyntaxError) as exc:
            raise FreePineBlocked("PYNE_FREE_PYTHON_SYNTAX_INVALID") from exc
        return generated

def ensure_cache():
    with closing(open_registry()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS investment_pyne_free_artifacts (
            kind TEXT NOT NULL,
            source_id TEXT NOT NULL,
            version_key TEXT NOT NULL,
            pine_sha256 TEXT NOT NULL,
            dependency_lock TEXT NOT NULL,
            compiler_id TEXT NOT NULL,
            python_sha256 TEXT NOT NULL,
            python_code TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(kind,source_id,version_key,pine_sha256,dependency_lock,compiler_id)
        )""")
        db.commit()

def cached(kind:str,sid:str,version:str,pine_sha:str,lock:str)->str|None:
    ensure_cache()
    with closing(open_registry()) as db:
        row=db.execute("""SELECT python_code,python_sha256 FROM investment_pyne_free_artifacts
            WHERE kind=? AND source_id=? AND version_key=? AND pine_sha256=?
            AND dependency_lock=? AND compiler_id=?""",
            (kind,sid,version,pine_sha,lock,COMPILER_ID)).fetchone()
    if row is None:return None
    code=row["python_code"]
    if hash_source(code)!=row["python_sha256"]:
        raise FreePineBlocked("PYNE_FREE_CACHE_PYTHON_SHA_MISMATCH")
    try:
        tree=ast.parse(code)
        if not any(isinstance(n,ast.FunctionDef) and
                   n.name=="execute_script_compiled" for n in tree.body):
            raise SyntaxError()
    except SyntaxError:
        raise FreePineBlocked("PYNE_FREE_CACHE_PYTHON_INVALID") from None
    return code

def store(kind:str,sid:str,version:str,pine_sha:str,lock:str,code:str)->dict:
    if not isinstance(code,str) or len(code.encode("utf-8"))>MAX_PY_BYTES:
        raise FreePineBlocked("PYNE_FREE_CACHE_PYTHON_INVALID")
    py_hash=hash_source(code)
    ensure_cache()
    with closing(open_registry()) as db:
        db.execute("""INSERT INTO investment_pyne_free_artifacts
            (kind,source_id,version_key,pine_sha256,dependency_lock,
             compiler_id,python_sha256,python_code,created_at)
            VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING""",
            (kind,sid,version,pine_sha,lock,COMPILER_ID,py_hash,code,
             datetime.now(timezone.utc).isoformat()))
        db.commit()
    pinned=cached(kind,sid,version,pine_sha,lock)
    if pinned!=code:
        raise FreePineBlocked("PYNE_FREE_CACHE_VERSION_CONFLICT")
    return {"compiler_id":COMPILER_ID,"pine_sha256":pine_sha,
            "python_sha256":py_hash,"bytes":len(code.encode("utf-8")),
            "conversion_validated":False,"tradingview_parity_verified":False}


def ddds_artifact(sid:str,*, include_code:bool=False)->dict:
    """Read source-matched actual compiled Python from the original WF02 DB.

    The selected TradingView publication must be the same immutable DDDS
    Pine source; unknown sources do not receive this code as a surrogate.
    """
    from investment_tv_publication import latest_reference
    from investment_pynecomp import dependency_lock
    from investment_ddds_parity import DDDS_SOURCE_SHA,DDDS_SOURCE_ID,DDDS_VERSION
    reference=latest_reference(sid)
    if reference.get("source_sha256")!=DDDS_SOURCE_SHA:
        return {"status":"PYNE_FREE_SELECTED_SOURCE_NOT_DDDS",
                "generated_python_available":False,"parity_verified":False,
                "live_orders_enabled":False}
    with closing(open_registry()) as db:
        names={r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        source=None
        if "investment_pine_payloads" in names:
            source=db.execute("""SELECT pine_code,rights_state FROM investment_pine_payloads
               WHERE kind='strategy' AND source_id=? AND version_key=?""",
               (DDDS_SOURCE_ID,DDDS_VERSION)).fetchone()
        right=source["rights_state"] if source is not None else None
        source_sha=hash_source(source["pine_code"]) if source is not None else None
    if source_sha!=DDDS_SOURCE_SHA or right!="APPROVED":
        return {"status":"PYNE_FREE_SOURCE_NOT_REGISTERED_OR_NOT_APPROVED",
                "source_id":DDDS_SOURCE_ID,"version_key":DDDS_VERSION,
                "rights_state":right,
                "generated_python_available":False,"parity_verified":False,
                "live_orders_enabled":False}
    lock=dependency_lock([])
    code=cached("strategy",DDDS_SOURCE_ID,DDDS_VERSION,DDDS_SOURCE_SHA,lock)
    result={
        "status":"PYNE_FREE_GENERATED_UNVALIDATED" if code is not None
                 else "PYNE_FREE_COMPILE_NOT_RUN",
        "source_id":DDDS_SOURCE_ID,"version_key":DDDS_VERSION,
        "pine_source_sha256":DDDS_SOURCE_SHA,
        "compiler":status(),
        "generated_python_available":code is not None,
        "python_sha256":hash_source(code) if code is not None else None,
        "python_bytes":len(code.encode("utf-8")) if code is not None else 0,
        "python_runtime_executed":False,
        "tradingview_strategy_parity_verified":False,
        "paper_enabled":False,"live_orders_enabled":False
    }
    if include_code and code is not None:
        result["python_code"]=code
    return result
