"""PyneComp-only Pine to Python adapter. Never fall back to handcrafted RSI/SMA code.

The official PyneSys compiler is an authenticated service. This module only
talks to the documented POST /compiler/compile API. Python artifacts are
syntax-checked and pinned to the immutable Pine source and dependency tree;
they are NOT TradingView parity validated.
"""
import hashlib
import json
import os
import re
import uuid
from datetime import datetime,timezone
from urllib import request,error
from contextlib import closing
from investment_source_registry import open_registry

ENDPOINT="https://api.pynesys.io/compiler/compile"
COMPILER_ID="pynecomp-http-v1-pynecore-6.11.1"
MAX_BYTES=512*1024
IMPORT_RE=re.compile(r"(?m)^[ \t]*import[ \t]+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[0-9]+)(?=\s|$)")
class PyneCompBlocked(Exception):
    def __init__(self,code):
        if not re.fullmatch(r"[A-Z][A-Z_0-9]{3,95}",code):
            code="PYNECOMP_UNEXPECTED_FAILURE"
        super().__init__(code)
        self.code=code

def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def scan_imports(pine):
    if not isinstance(pine,str) or not pine.strip():
        raise PyneCompBlocked("PINE_SOURCE_EMPTY")
    if len(pine.encode("utf-8"))>MAX_BYTES:
        raise PyneCompBlocked("PINE_SOURCE_TOO_LARGE")
    found=list(dict.fromkeys(IMPORT_RE.findall(pine)))
    if len(found)>64:raise PyneCompBlocked("TOO_MANY_LIBRARY_IMPORTS")
    return found

def resolve_imports(pine,loader):
    """Resolve exact Pine Library versions recursively, never latest-by-name."""
    output=[]
    visited=set()
    active=set()
    def walk(import_name):
        if import_name in active:raise PyneCompBlocked("CYCLIC_PINE_LIBRARY_DEPENDENCY")
        if import_name in visited:return
        if len(visited)>64:raise PyneCompBlocked("TOO_MANY_LIBRARY_IMPORTS")
        active.add(import_name)
        entry=loader(import_name)
        if not entry:raise PyneCompBlocked("PINNED_LIBRARY_SOURCE_MISSING")
        pieces=import_name.split("/")
        if (entry.get("kind")!="library" or
            entry.get("source_id")!="/".join(pieces[:2]) or
            entry.get("version_key")!=pieces[2]):
            raise PyneCompBlocked("PINNED_LIBRARY_ID_VERSION_MISMATCH")
        source=entry.get("pine_code")
        if not isinstance(source,str) or not re.search(r"(?m)^\s*library\s*\(",source):
            raise PyneCompBlocked("NOT_A_PINE_LIBRARY")
        if entry.get("source_sha256")!=sha(source):
            raise PyneCompBlocked("LIBRARY_SOURCE_SHA256_MISMATCH")
        for child in scan_imports(source):
            walk(child)
        active.remove(import_name)
        visited.add(import_name)
        output.append({
            "kind":"library","import_name":import_name,
            "source_id":entry["source_id"],"version_key":entry["version_key"],
            "source_sha256":entry["source_sha256"],
            "script_version_id":entry.get("script_version_id"),
            "pine_code":source,
            "module_path":"/".join(pieces[:2])+"/"+pieces[2]})
    for name in scan_imports(pine):
        walk(name)
    return output

def dependency_lock(libs):
    identities=sorted((e["import_name"],e["source_sha256"]) for e in libs)
    return sha(json.dumps(identities,ensure_ascii=False,separators=(",",":")))

def python_syntax_checked(code):
    if not isinstance(code,str) or not code.strip() or len(code.encode("utf-8"))>MAX_BYTES*5:
        raise PyneCompBlocked("PYNECOMP_EMPTY_OR_OVERSIZED_PYTHON")
    try:compile(code,"<PyneComp generated Python>","exec")
    except (SyntaxError,ValueError,TypeError):
        raise PyneCompBlocked("PYNECOMP_GENERATED_PYTHON_SYNTAX_INVALID") from None
    return code

def compile_remote(pine,*,filename="script.pine",api_key=None,transport=None):
    """No remote network call occurs when the API key is absent."""
    key=api_key if api_key is not None else os.getenv("PYNESYS_API_KEY","")
    if not key:raise PyneCompBlocked("PYNECOMP_API_KEY_MISSING")
    if not filename.endswith(".pine") or not re.fullmatch(r"[A-Za-z0-9_-]{1,90}\.pine",filename):
        raise PyneCompBlocked("PYNECOMP_INVALID_FILENAME")
    scan_imports(pine)
    boundary="pynecomp-"+uuid.uuid4().hex
    body=(
        ("--"+boundary+"\r\nContent-Disposition: form-data; name=\"script\"; filename=\""+filename+
         "\"\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n").encode("utf-8")+
        pine.encode("utf-8")+("\r\n--"+boundary+"--\r\n").encode("utf-8"))
    req=request.Request(ENDPOINT,data=body,method="POST",
      headers={"Authorization":"Bearer "+key,
               "Content-Type":"multipart/form-data; boundary="+boundary,
               "Accept":"text/plain, application/json",
               "User-Agent":"investment-wf02-pynecomp/1"})
    try:
        if transport is None:
            with request.urlopen(req,timeout=80) as resp:
                if resp.status!=200:raise PyneCompBlocked("PYNECOMP_HTTP_ERROR")
                raw=resp.read(MAX_BYTES*5+1)
        else:
            raw=transport(req)
    except error.HTTPError as exc:
        if exc.code in (401,403):raise PyneCompBlocked("PYNECOMP_AUTH_DENIED") from None
        if exc.code==429:raise PyneCompBlocked("PYNECOMP_QUOTA_EXCEEDED") from None
        raise PyneCompBlocked("PYNECOMP_HTTP_ERROR") from None
    except (error.URLError,TimeoutError,OSError):
        raise PyneCompBlocked("PYNECOMP_API_UNREACHABLE") from None
    if isinstance(raw,str):raw=raw.encode("utf-8")
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES*5:
        raise PyneCompBlocked("PYNECOMP_INVALID_RESPONSE")
    try:code=raw.decode("utf-8")
    except UnicodeDecodeError:raise PyneCompBlocked("PYNECOMP_INVALID_ENCODING") from None
    # The documented endpoint returns plain Python, but permit its explicit
    # "python_code" JSON wrapper without guessing on errors.
    if code.lstrip().startswith("{"):
        try:response=json.loads(code)
        except json.JSONDecodeError:raise PyneCompBlocked("PYNECOMP_INVALID_RESPONSE") from None
        if not isinstance(response,dict) or not isinstance(response.get("python_code"),str):
            raise PyneCompBlocked("PYNECOMP_INVALID_RESPONSE")
        code=response["python_code"]
    return python_syntax_checked(code)

def ensure_cache():
    with closing(open_registry()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS investment_pynecomp_artifacts (
          kind TEXT NOT NULL,source_id TEXT NOT NULL,version_key TEXT NOT NULL,
          source_sha256 TEXT NOT NULL,dependency_lock TEXT NOT NULL,
          compiler_id TEXT NOT NULL,python_code TEXT NOT NULL,
          module_path TEXT,created_at TEXT NOT NULL,
          PRIMARY KEY(kind,source_id,version_key,source_sha256,dependency_lock,compiler_id)
        )""")
        db.commit()

def cached(kind,sid,version,pine_sha,lock):
    ensure_cache()
    with closing(open_registry()) as db:
        row=db.execute("""SELECT python_code FROM investment_pynecomp_artifacts
          WHERE kind=? AND source_id=? AND version_key=? AND source_sha256=?
          AND dependency_lock=? AND compiler_id=?""",
          (kind,sid,version,pine_sha,lock,COMPILER_ID)).fetchone()
    if row:return python_syntax_checked(row[0])
    return None

def save_cache(kind,sid,version,pine_sha,lock,code,module_path=None):
    python_syntax_checked(code)
    ensure_cache()
    with closing(open_registry()) as db:
        db.execute("""INSERT INTO investment_pynecomp_artifacts
          (kind,source_id,version_key,source_sha256,dependency_lock,
           compiler_id,python_code,module_path,created_at)
          VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING""",
          (kind,sid,version,pine_sha,lock,COMPILER_ID,code,module_path,
           datetime.now(timezone.utc).isoformat()))
        db.commit()

def compiler_status():
    return {"engine":"PyneComp → PyneCore",
            "compiler":COMPILER_ID,
            "api_key_configured":bool(os.getenv("PYNESYS_API_KEY")),
            "api":"https://api.pynesys.io/compiler/compile",
            "library_policy":"EXACT_PINNED_SOURCES_ONLY",
            "parity_verified":False}
