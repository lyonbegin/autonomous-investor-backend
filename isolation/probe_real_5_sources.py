#!/usr/bin/env python3
"""Exact user-provided archive hash-based source samples. No code is published."""
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"n8n"/"editor-adapter"))
from investment_pynecomp import scan_imports,sha
from investment_free_pyne import compile_pine,FreePineBlocked

PINNED="https://raw.githubusercontent.com/venkatalokeshanne/trading_strategies_indicators/a9a6f4a9145de22bacacc24b827fb4095a3a425c/TradingView/strategies/"
SOURCES=[["02yfhjiz","02yfhjiz-Complex-Single-Trade-Strategy.pine","81d0299b4ee1c60e87e88e8279d13c928a285a07a32658cd1cfcccee6d94a701"],["03zgCMqx","03zgCMqx-PROP-Scalper-V2-FINAL.pine","db7c9e6e9dd177ae1c06bba5e6dce557005c1a662e142350dd0ef35211ce596f"],["0mSobwAz","0mSobwAz-NQ-EMA-VWAP-Strategy.pine","1f768d5c60601f05948b8604077cc35f142acbec26923a134d2165c2f16d1350"],["0wggzSk5","0wggzSk5-JUP-RSI-Long-Strategy-3Commas.pine","648e6ac23d92f143704f3961ae5208d328ce66c3d07c74bff3d7b6e602b10171"],["06s9ohae","06s9ohae-FCPO-Session-Based-Momentum-Scalper-with-ATR-Volatility-Filter.pine","56854582fd0079fca7361c4531937367cc960f856578cd53ce519f248c1ffaae"]]
rows=[]
for script_id,filename,expected in SOURCES:
    result={"script_id":script_id,"source_sha256_expected":expected}
    try:
        req=Request(PINNED+filename,headers={"User-Agent":"wf02-isolated-verified-src/1"})
        with urlopen(req,timeout=15) as f:raw=f.read(520000)
        actual=hashlib.sha256(raw).hexdigest()
        result["source_sha256_actual"]=actual
        if actual!=expected:raise ValueError("PINNED_SHA256_MISMATCH")
        pine=raw.decode("utf-8")
        result["source_bytes"]=len(raw)
        result["direct_library_imports"]=scan_imports(pine)
        if result["direct_library_imports"]:
            result["status"]="BLOCKED_UNRESOLVED_LIBRARY"
        else:
            code=compile_pine(pine,expected_sha=sha(pine),timeout=20)
            result["status"]="PYTHON_GENERATED_UNVALIDATED"
            result["python_bytes"]=len(code.encode("utf-8"))
            result["python_sha256"]=hashlib.sha256(code.encode("utf-8")).hexdigest()
    except FreePineBlocked as e:
        result["status"]=e.code
    except Exception as e:
        result["status"]="ERROR_"+type(e).__name__
        result["error"]=str(e)[:240]
    rows.append(result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
Path("wf02_isolated_real5_result.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
if not all(x.get("source_sha256_actual")==x["source_sha256_expected"] for x in rows):
    raise SystemExit("REAL_SOURCE_HASH_VALIDATION_FAILED")
