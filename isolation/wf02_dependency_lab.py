#!/usr/bin/env python3
"""Read-only WF02 clone smoke tests. Uses only a temporary SQLite store."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "n8n" / "editor-adapter"))
from investment_pynecomp import scan_imports, resolve_imports, sha, PyneCompBlocked
from investment_wf02 import execute_wf02_node02, execute_wf02_node03
from investment_free_pyne import status as compiler_status, compile_pine, FreePineBlocked

ROOT = '//@version=6\nimport demo/Parent/3 as p\nstrategy("Isolated test")\nplot(close)\n'
PARENT = '//@version=6\nimport demo/Child/2 as c\nlibrary("Parent")\nexport twice(float v) => c.inc(v)*2\n'
CHILD = '//@version=6\nlibrary("Child")\nexport inc(float v) => v+1\n'
NO_IMPORT = '//@version=6\nstrategy("Isolated independent compile")\nplot(close)\n'

def seed(db, omit_child=False):
    db.execute("""CREATE TABLE investment_pine_payloads (
      kind TEXT NOT NULL,source_id TEXT NOT NULL,version_key TEXT NOT NULL,
      pine_code TEXT NOT NULL,rights_state TEXT NOT NULL,saved_at TEXT NOT NULL,
      PRIMARY KEY(kind,source_id,version_key))""")
    now=datetime.now(timezone.utc).isoformat()
    rows=[("strategy","demo/root","1",ROOT,"APPROVED",now),
          ("library","demo/Parent","3",PARENT,"APPROVED",now)]
    if not omit_child:rows.append(("library","demo/Child","2",CHILD,"APPROVED",now))
    db.executemany("INSERT INTO investment_pine_payloads VALUES (?,?,?,?,?,?)",rows)
    db.commit()

def run():
    report={"sandbox":True,"production_database_access":False,
            "source_branch_copy":"feature/wf02-bridge-real-ddds-verified-site-20261104",
            "compiler":compiler_status(),"tests":{}}
    assert scan_imports(ROOT)==["demo/Parent/3"]
    report["tests"]["import_scan"]="PASS"
    with tempfile.TemporaryDirectory(prefix="wf02-isolated-") as folder:
        os.environ["STUDIO_DB_PATH"]=str(Path(folder)/"test.sqlite3")
        os.environ.pop("INVESTMENT_DATABASE_URL",None)
        db=sqlite3.connect(os.environ["STUDIO_DB_PATH"])
        seed(db)
        db.close()
        inp={"kind":"strategy","status":"PINE_LOADED",
             "pine_code":ROOT,"source_id":"demo/root","version_key":"1",
             "source_sha256":sha(ROOT),"rights_state":"APPROVED"}
        out=execute_wf02_node02(inp,workflow_kind="strategy")
        paths=[x["import_name"] for x in out.get("resolved_libraries",[])]
        assert out["status"]=="LIBRARIES_RESOLVED",out
        assert paths==["demo/Child/2","demo/Parent/3"],paths
        assert out["library_count"]==2
        report["tests"]["recursive_exact_library_resolution"]="PASS"
        report["resolved_order"]=paths
        blocked=execute_wf02_node03(out,workflow_kind="strategy")
        assert blocked["status"]=="PYNE_FREE_LIBRARY_IMPORT_UNSUPPORTED",blocked
        report["tests"]["wf02_existing_library_compilation_gate"]="BLOCKED_AS_IMPLEMENTED"
    with tempfile.TemporaryDirectory(prefix="wf02-missing-") as folder:
        os.environ["STUDIO_DB_PATH"]=str(Path(folder)/"test.sqlite3")
        db=sqlite3.connect(os.environ["STUDIO_DB_PATH"]);seed(db,omit_child=True);db.close()
        missing=execute_wf02_node02(inp,workflow_kind="strategy")
        assert missing["status"]=="PINNED_LIBRARY_SOURCE_MISSING",missing
        report["tests"]["missing_transitive_library"]="CORRECTLY_BLOCKED"
    try:
        compiled=compile_pine(NO_IMPORT,expected_sha=sha(NO_IMPORT))
        report["tests"]["pine_to_python_no_import"]="COMPILED"
        report["generated_python_bytes"]=len(compiled.encode("utf-8"))
        report["generated_python_sha256"]=hashlib.sha256(compiled.encode()).hexdigest()
    except FreePineBlocked as exc:
        report["tests"]["pine_to_python_no_import"]="BLOCKED"
        report["compiler_block_reason"]=exc.code
    Path("wf02_isolated_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    assert report["compiler"]["installed"] is True,"PINNED_HOOX_PYNE_NOT_INSTALLED"
    return report

if __name__=="__main__":
    run()
