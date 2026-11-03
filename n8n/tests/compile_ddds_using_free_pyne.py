"""Compile EXACT published DDDS Pine using FREE local hoox-pyne.
No fabricated source, no imported/executed generated Python, no paper/live grant.
"""
from __future__ import annotations
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ADAPTER=Path(__file__).resolve().parents[1]/"editor-adapter"
sys.path.insert(0,str(ADAPTER))
SOURCE_SHA="5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507"
SOURCE_ID="PUB;5442675d418140c58486eb4a7ae12768"
VERSION="0.6.31"

def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def record(status, **kwargs):
    return {"status":status,"source_id":SOURCE_ID,"source_sha256":SOURCE_SHA,
            "compiler":"hoox-pyne=="+VERSION,"python_executed":False,
            "tradingview_parity_verified":False,"pynecore_compatibility_verified":False,
            "paper_enabled":False,"live_orders_enabled":False,**kwargs}

def check_cli(pine):
    with tempfile.TemporaryDirectory(prefix="wf02-ddds-check-") as tmp:
        p=Path(tmp)/"DDDS.pine"
        p.write_text(pine,encoding="utf-8")
        try:
            r=subprocess.run(["pyne","check",str(p)],cwd=tmp,
                stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=50)
        except FileNotFoundError:
            return {"returncode":127,"reason":"PYNE_CLI_NOT_INSTALLED"}
        except subprocess.TimeoutExpired:
            return {"returncode":124,"reason":"PYNE_CHECK_TIMEOUT"}
        return {"returncode":r.returncode,"stdout_tail":r.stdout[-1800:],
                "stderr_tail":r.stderr[-4000:]}

def compile_ddds(out, *, source=None, compiler=None, diagnostic=None):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    if source is None:
        from investment_tv_publication import bundled_ddds_reference
        source=bundled_ddds_reference()
    if not isinstance(source,dict):
        return record("BLOCKED_SOURCE_NOT_OBJECT")
    pine=source.get("pine_source")
    if (not isinstance(pine,str) or source.get("source_id")!=SOURCE_ID
        or source.get("source_sha256")!=SOURCE_SHA
        or digest(pine)!=SOURCE_SHA or len(pine.splitlines())!=141):
        return record("BLOCKED_EXACT_141_LINE_SOURCE_MISMATCH",
            actual_sha=digest(pine) if isinstance(pine,str) else None,
            actual_lines=len(pine.splitlines()) if isinstance(pine,str) else None)
    if source.get("source_rights")!="MPL-2.0":
        return record("BLOCKED_PINNED_SOURCE_RIGHTS_MISSING")
    check=(diagnostic or check_cli)(pine)
    if not isinstance(check,dict) or check.get("returncode")!=0:
        return record("BLOCKED_PYNE_CHECK",pine_lines=141,check=check)
    if compiler is None:
        from investment_free_pyne import compile_pine
        compiler=compile_pine
    try:
        code=compiler(pine,expected_sha=SOURCE_SHA)
    except Exception as exc:
        reason=getattr(exc,"code","PYNE_FREE_UNEXPECTED_FAILURE")
        if not isinstance(reason,str) or not reason.startswith("PYNE_FREE_"):
            reason="PYNE_FREE_UNEXPECTED_FAILURE"
        return record("BLOCKED_PYNE_COMPILE",pine_lines=141,
            reason=reason,error_type=type(exc).__name__,check=check)
    if not isinstance(code,str) or not code.strip():
        return record("BLOCKED_EMPTY_PYTHON_OUTPUT",check=check)
    try:
        tree=ast.parse(code)
        if not any(isinstance(n,ast.FunctionDef)
                   and n.name=="execute_script_compiled" for n in tree.body):
            raise SyntaxError("execute_script_compiled missing")
    except SyntaxError:
        return record("BLOCKED_INVALID_GENERATED_PYTHON",check=check)
    dest=out/"DDDS_exact_hoox_pyne.py"
    dest.write_text(code,encoding="utf-8")
    return record("GENERATED_UNVALIDATED",pine_lines=141,check=check,
        python_sha256=digest(code),python_bytes=len(code.encode("utf-8")),
        python_filename=dest.name)

def main():
    out=Path(os.getenv("DDDS_COMPILE_OUTPUT_DIR","/tmp/ddds-real-free-pyne"))
    try:
        result=compile_ddds(out)
    except Exception as exc:
        result=record("BLOCKED_UNEXPECTED_EXCEPTION",
            error_type=type(exc).__name__)
    out.mkdir(parents=True,exist_ok=True)
    (out/"manifest.json").write_text(json.dumps(result,ensure_ascii=False,
        indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["status"]=="GENERATED_UNVALIDATED" else 4

if __name__=="__main__":
    raise SystemExit(main())
