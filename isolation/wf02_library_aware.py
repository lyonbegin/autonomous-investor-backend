#!/usr/bin/env python3
"""Isolated library-aware PYNE runner; no production edits, no claims of native transpilation.

The 0.6.31 upstream compiler cannot emit Python for import scripts. PYNE's
Runtime.run(mode="auto", libraries=...) supports import through interpret.
This adapter deliberately labels the result INTERPRETED, not TRANSPILED.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "n8n" / "editor-adapter"))
from investment_pynecomp import scan_imports, resolve_imports, dependency_lock, sha, PyneCompBlocked
from investment_free_pyne import compile_pine, FreePineBlocked
from pynescript.runtime import Runtime

def dependency_bundle(strategy_source: str, source_map: dict[str, str]) -> dict[str, Any]:
    """Resolve exact recursive import closure, with missing versions failing closed."""
    def loader(import_name: str):
        code=source_map.get(import_name)
        if not isinstance(code,str):
            return None
        parts=import_name.split("/")
        if len(parts)!=3:return None
        return {"kind":"library","source_id":"/".join(parts[:2]),
                "version_key":parts[2], "pine_code":code,"source_sha256":sha(code)}
    sources=resolve_imports(strategy_source, loader)
    inputs=[]
    for lib in sources:
        parts=lib["import_name"].split("/")
        inputs.append({"namespace":parts[0],"name":parts[1],
                       "version":int(parts[2]),"source":lib["pine_code"]})
    return {"imports":scan_imports(strategy_source),
            "libraries":inputs,
            "dependency_lock_hash":dependency_lock(sources),
            "resolved_libraries": [x["import_name"] for x in sources]}

def run_strategy(strategy_source: str, source_map: dict[str,str], bars: list[dict],
                 *, symbol:str="TEST") -> dict[str,Any]:
    """Use native PYNE compile only when possible; imports use documented auto-interpret."""
    pinned=dependency_bundle(strategy_source,source_map)
    if pinned["imports"]:
        output=Runtime(symbol=symbol).run(strategy_source,bars,mode="auto",libraries=pinned["libraries"])
        backend=output.get("auto_backend")
        if output.get("error"):
            return {"status":"PYNE_LIBRARY_RUNTIME_FAILED","error":str(output["error"]),
                    "strategy_sha256":sha(strategy_source),
                    "dependency_lock_hash":pinned["dependency_lock_hash"],
                    "resolved_libraries":pinned["resolved_libraries"],
                    "native_python_generated":False}
        return {"status":"PYNE_LIBRARY_INTERPRETED_NOT_TRANSPILED",
                "strategy_sha256":sha(strategy_source),
                "dependency_lock_hash":pinned["dependency_lock_hash"],
                "resolved_libraries":pinned["resolved_libraries"],
                "library_count":len(pinned["libraries"]),"runtime_backend":backend,
                "plot_0":(output.get("series") or {}).get("plot_0"),
                "native_python_generated":False,"runtime_output":output}
    code=compile_pine(strategy_source,expected_sha=sha(strategy_source))
    return {"status":"PYNE_NATIVE_PYTHON_GENERATED_UNVALIDATED",
            "strategy_sha256":sha(strategy_source),
            "generated_python":code,"generated_python_sha256":sha(code),
            "native_python_generated":True}

def fixture_bars(n:int=5):
    return [{"open":100.0+i,"high":102.0+i,"low":99.0+i,
             "close":101.0+i,"volume":1000.0,
             "time":1700000000000+i*60000} for i in range(n)]

def selftest():
    root='//@version=6\nstrategy("Library-aware test")\nimport demo/Calc/3 as c\nplot(c.twice(close))\n'
    parent='//@version=6\nlibrary("Calc")\nexport twice(float v) => v*2\n'
    cases=[]
    direct=run_strategy(root,{"demo/Calc/3":parent},fixture_bars())
    cases.append({"case":"direct_import","status":direct["status"],
                  "backend":direct.get("runtime_backend"),"plots":direct.get("plot_0"),
                  "error":direct.get("error"),
                  "imported":direct.get("resolved_libraries")})
    try:
        run_strategy(root,{},fixture_bars())
        cases.append({"case":"missing_direct_import","status":"UNEXPECTED_SUCCESS"})
    except PyneCompBlocked as e:
        cases.append({"case":"missing_direct_import","status":e.code})
    grandchild='//@version=6\nlibrary("Child")\nexport inc(float v) => v+1\n'
    nested_parent='//@version=6\nlibrary("Calc")\nimport demo/Child/2 as sub\nexport twice(float v) => sub.inc(v)*2\n'
    nested=run_strategy(root,{"demo/Calc/3":nested_parent,
                             "demo/Child/2":grandchild},fixture_bars())
    cases.append({"case":"transitive_import","status":nested["status"],
                  "backend":nested.get("runtime_backend"),"plots":nested.get("plot_0"),
                  "error":nested.get("error"),
                  "imported":nested.get("resolved_libraries")})
    report={"pyne":"0.6.31","operator":"library-aware isolated auto runtime",
            "strategy_identity":"synthetic test only; NOT one of 4428",
            "production_modified":False,
            "cases":cases}
    Path("wf02_isolated_library_runtime_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2,default=str))
    assert cases[0]["status"]=="PYNE_LIBRARY_INTERPRETED_NOT_TRANSPILED",cases
    assert cases[0]["backend"]=="interpret",cases
    assert cases[1]["status"]=="PINNED_LIBRARY_SOURCE_MISSING",cases
    assert cases[2]["status"]=="PYNE_LIBRARY_INTERPRETED_NOT_TRANSPILED",cases
    assert cases[2]["backend"]=="interpret",cases

if __name__=="__main__":
    selftest()
