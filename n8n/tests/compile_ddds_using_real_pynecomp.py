"""Actual DDDS PyneComp compile job, using the EXISTING WF02 converter.

This performs a paid/authenticated external compile ONLY when a secure
PYNESYS_API_KEY secret was configured for this job. No mock Python code,
fallback strategy or locally improvised Pine compiler is used.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]/"editor-adapter"
sys.path.insert(0,str(ROOT))
from investment_pynecomp import (
    COMPILER_ID, PyneCompBlocked,compile_remote,scan_imports,python_syntax_checked
)
from investment_tv_publication import bundled_ddds_reference
from investment_ddds_parity import DDDS_SOURCE_SHA, DDDS_SOURCE_ID, DDDS_VERSION

OUT=Path(os.environ.get("WF02_DDDS_COMPILE_EVIDENCE","/tmp/ddds-exact-pynecomp"))
OUT.mkdir(parents=True,exist_ok=True)

def main():
    source=bundled_ddds_reference()
    pine=source["pine_source"]
    source_sha=hashlib.sha256(pine.encode("utf-8")).hexdigest()
    assert source_sha==DDDS_SOURCE_SHA==source["source_sha256"]
    assert source["source_id"]==DDDS_SOURCE_ID
    assert source["source_rights"]=="MPL-2.0"
    imports=scan_imports(pine)
    if imports:
        raise RuntimeError("PINNED_DDDS_IMPORTS_UNEXPECTED")
    record={
        "source_id":DDDS_SOURCE_ID,
        "version_key":DDDS_VERSION,
        "pine_sha256":DDDS_SOURCE_SHA,
        "pine_lines":len(pine.splitlines()),
        "license":"MPL-2.0",
        "publication_url":source["publication_url"],
        "compiler_id":COMPILER_ID,
        "python_sha256":None,
        "pynecore_runtime_target":"6.11.1",
        "tv_trade_baseline_count":299,
        "official_tv_amzn_2h_full_history_available":False,
        "compiled_python_executed":False,
        "tv_pynecore_trade_parity_verified":False,
        "live_orders_enabled":False,
    }
    if not os.environ.get("PYNESYS_API_KEY"):
        record["status"]="BLOCKED_PYNESYS_API_KEY_NOT_CONFIGURED"
        (OUT/"manifest.json").write_text(json.dumps(record,indent=2,ensure_ascii=False))
        print("DDDS_EXACT_PYNECOMP_NOT_AVAILABLE: GitHub secret PYNESYS_API_KEY not configured")
        return
    try:
        compiled=compile_remote(pine,filename="DDDS_exact.pine")
    except PyneCompBlocked as exc:
        record["status"]=exc.code
        (OUT/"manifest.json").write_text(json.dumps(record,indent=2,ensure_ascii=False))
        print("DDDS_EXACT_PYNECOMP_COMPILE_BLOCKED",exc.code)
        raise SystemExit(4)
    code=python_syntax_checked(compiled)
    py_sha=hashlib.sha256(code.encode("utf-8")).hexdigest()
    record["status"]="EXACT_DDDS_PYNECOMP_PYTHON_GENERATED_UNVALIDATED"
    record["python_sha256"]=py_sha
    record["compiled_python_filename"]="DDDS_exact_pynecomp.py"
    # Official compiler output, but never import/execute in this public CI job.
    (OUT/"DDDS_exact_pynecomp.py").write_text(code,encoding="utf-8")
    (OUT/"manifest.json").write_text(json.dumps(record,indent=2,ensure_ascii=False))
    print("DDDS_EXACT_PYNECOMP_SOURCE_GENERATED",json.dumps({
        "pine_sha256":source_sha,
        "python_sha256":py_sha,
        "python_bytes":len(code.encode("utf-8")),
        "parity_verified":False
    }))

if __name__=="__main__":
    main()
