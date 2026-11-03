"""No legacy handwritten converter; real WF02 input, exact library graph and compiler transport."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"pine-parity"))
from investment_wf02 import (execute_wf02_node01,execute_wf02_node02,
    execute_wf02_node03,execute_wf02_node04,execute_wf02_node05,
    execute_wf02_node06)
from investment_pynecomp import sha,compile_remote,PyneCompBlocked
from investment_pine_store import save_verified_source

PINE="""//@version=6
strategy("full", overlay=true, commission_type=strategy.commission.percent, commission_value=0.04)
var float x=na
if ta.crossover(ta.ema(close,8),ta.sma(close,20))
    x := close
    strategy.entry("Long",strategy.long)
strategy.exit("X","Long",stop=x*0.98,limit=x*1.04)
"""

LIB="""//@version=6
library("Calc")
export get_value(float v)=>v*2
"""

def seed(pine,sid):
    return save_verified_source({"candidate":{"source_id":sid,"version_key":"1.0"},
        "pine_code":pine},"strategy")

class PyneCompWF02(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env=patch.dict(os.environ,{"STUDIO_DB_PATH":tmp.name+"/store.sqlite",
              "PYNESYS_API_KEY":""})
        env.start();self.addCleanup(env.stop)
        seed(PINE,"PUB;full-v6")
    def root(self,sid="PUB;full-v6"):
        return execute_wf02_node01({"ui_selection":"strategy",
               "requested_detail_limit":1,"source_id":sid,"version_key":"1.0"},
               workflow_kind="strategy")
    def flow(self):
        a=self.root()
        a=execute_wf02_node02(a,workflow_kind="strategy")
        a=execute_wf02_node03(a,workflow_kind="strategy")
        a=execute_wf02_node04(a,workflow_kind="strategy")
        a=execute_wf02_node05(a,workflow_kind="strategy")
        return execute_wf02_node06(a,workflow_kind="strategy")

    def test_full_pine_no_legacy_converter_when_no_pynesys_key(self):
        result=self.flow()
        self.assertEqual(result["status"],"PYNECOMP_API_KEY_MISSING")
        self.assertIsNone(result["python_code"])
        self.assertFalse(result["paper_enabled"])
        self.assertFalse(result["tradingview_chart_validated"])
        self.assertEqual(result["blocked_at"],"STRATEGY_COMPILATION")
        self.assertEqual(result["source_id"],"PUB;full-v6")

    def test_authenticated_PyneComp_output_is_only_generated_not_validated(self):
        generated='"""@pyne"""\nfrom pynecore.lib import close\n\ndef main():\n    return close\n'
        with patch("investment_wf02.compile_remote",return_value=generated) as compiler:
          with patch("importlib.metadata.version",return_value="6.11.1"):
            result=self.flow()
        compiler.assert_called_once()
        self.assertEqual(result["status"],"PYNECOMP_GENERATED_UNVALIDATED")
        self.assertEqual(result["python_code"],generated)
        self.assertFalse(result["conversion_validated"])
        self.assertFalse(result["tradingview_chart_validated"])
        self.assertEqual(result["converter_scope"],"PYNECOMP_FULL_PINE")
        self.assertEqual(result["pynecore_runtime_version"],"6.11.1")
        # Existing exact source/code must be reused, not recompiled after a key disappears.
        with patch("investment_wf02.compile_remote",side_effect=AssertionError("NO RECOMPILE")):
          with patch("importlib.metadata.version",return_value="6.11.1"):
            cached=self.flow()
        self.assertEqual(cached["status"],"PYNECOMP_GENERATED_UNVALIDATED")
        self.assertTrue(cached.get("strategy_code_cache_hit"))

    def test_real_import_requires_exact_library_version_and_no_substitute(self):
        source='//@version=6\nimport author/Calc/3 as lib\nstrategy("t")\nplot(lib.get_value(close))'
        seed(source,"PUB;with-lib")
        missing=execute_wf02_node02(self.root("PUB;with-lib"),workflow_kind="strategy")
        self.assertEqual(missing["status"],"PINNED_LIBRARY_SOURCE_MISSING")
        self.assertIn("author/Calc/3",missing["requested_imports"])
        self.assertIsNone(missing["python_code"])
        entry={"kind":"library","source_id":"author/Calc","version_key":"3",
           "pine_code":LIB,"source_sha256":sha(LIB)}
        with patch("investment_wf02._load_exact_library",return_value=entry):
          result=execute_wf02_node02(self.root("PUB;with-lib"),workflow_kind="strategy")
        self.assertEqual(result["status"],"LIBRARIES_RESOLVED")
        self.assertEqual(result["resolved_libraries"][0]["import_name"],"author/Calc/3")
        with patch("investment_wf02.compile_remote",
            side_effect=['"""@pyne"""\ndef twice(v):return v*2',
                         '"""@pyne"""\ndef main():return 1']) as compiler:
          with patch("investment_wf02._load_exact_library",return_value=entry):
            a=execute_wf02_node03(result,workflow_kind="strategy")
            self.assertEqual(a["status"],"PYNECOMP_LIBRARIES_COMPILED")
            b=execute_wf02_node04(a,workflow_kind="strategy")
            self.assertEqual(b["status"],"PYNECOMP_CODE_COMPILED")
            with patch("importlib.metadata.version",return_value="6.11.1"):
              c=execute_wf02_node05(b,workflow_kind="strategy")
        self.assertEqual(compiler.call_count,2)
        self.assertFalse(c["library_import_linkage_verified"])
        self.assertFalse(c["conversion_validated"])
        self.assertEqual(c["status"],"PYNECOMP_GENERATED_UNVALIDATED")

    def test_api_key_is_checked_before_any_request_and_invalid_python_rejected(self):
        with self.assertRaisesRegex(PyneCompBlocked,"PYNECOMP_API_KEY_MISSING"):
            compile_remote(PINE,api_key="")
        with self.assertRaisesRegex(PyneCompBlocked,"PYNECOMP_GENERATED_PYTHON_SYNTAX_INVALID"):
            compile_remote(PINE,api_key="fake-but-never-sent",
                           transport=lambda req:b"def broken(:\n")

    def test_missing_source_blocking(self):
        with self.assertRaisesRegex(ValueError,"WF02_PINE_NOT_IN_DATABASE"):
            self.root("PUB;absent")

if __name__=="__main__":unittest.main()
