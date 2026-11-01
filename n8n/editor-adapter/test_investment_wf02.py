"""WF02 real SQLite Pine input and supported Python generation tests."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent / "pine-parity"))
from investment_wf02 import execute_wf02_node01,execute_wf02_node02,execute_wf02_node03
from investment_pine_store import save_verified_source
from engine import read_csv,parse_pine,run_python

SUPPORTED="""//@version=6
strategy("SMA/EMA cross",overlay=true)
fastLen = input.int(3, "fast")
slowLen = input.int(7, "slow")
fastMA = ta.sma(close, fastLen)
slowMA = ta.ema(close, slowLen)
longSignal = ta.crossover(fastMA, slowMA)
shortSignal = ta.crossunder(fastMA, slowMA)
if (longSignal)
    strategy.entry("Long", strategy.long)
if (shortSignal)
    strategy.entry("Short", strategy.short)
plot(fastMA)
plot(slowMA)
"""

def seed(code, source_id):
    return save_verified_source({"candidate":{"source_id":source_id,"version_key":"1.0"},
        "pine_code":code},"strategy")

class WF02ConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher=patch.dict(os.environ,{"STUDIO_DB_PATH":self.tmp.name+"/wf02.sqlite"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_real_saved_pine_load_convert_persist_and_execute_generated_python(self):
        seed(SUPPORTED,"PUB;test-valid")
        root=execute_wf02_node01({"ui_selection":"strategy","requested_detail_limit":1},
                 workflow_kind="strategy")
        self.assertEqual(root["pine_code"],SUPPORTED)
        converted=execute_wf02_node02(root,workflow_kind="strategy")
        self.assertEqual(converted["status"],"PYTHON_GENERATED")
        self.assertIn("def run_strategy",converted["python_code"])
        self.assertFalse(converted["conversion_validated"])
        report=execute_wf02_node03(converted,workflow_kind="strategy")
        self.assertFalse(report["paper_enabled"])
        self.assertFalse(report["tradingview_chart_validated"])
        bars=[{"time":str(i),"open":float(100+i%9),"close":float(102+((-1)**i)*(i%13))}
               for i in range(70)]
        ns={}
        exec(compile(converted["python_code"],"<generated/test-only>","exec"),ns)
        actual=ns["run_strategy"](bars)
        expected=run_python(bars,parse_pine(SUPPORTED))
        self.assertEqual(actual["series"],expected[0])
        self.assertEqual(actual["signals"],expected[1])
        self.assertEqual(actual["trades"],expected[2])
        with sqlite3.connect(self.tmp.name+"/wf02.sqlite") as db:
            row=db.execute("SELECT python_code FROM investment_python_conversions").fetchone()
        self.assertEqual(row[0],converted["python_code"])

    def test_complex_pine_is_reported_unsupported_not_fake_converted(self):
        code="""//@version=6
strategy("complex",overlay=true)
multiframe = request.security(syminfo.tickerid, "D", close)
strategy.entry("Buy",strategy.long)
"""
        seed(code,"PUB;complex")
        root=execute_wf02_node01({"ui_selection":"strategy","requested_detail_limit":1,
                 "source_id":"PUB;complex","version_key":"1.0"},workflow_kind="strategy")
        converted=execute_wf02_node02(root,workflow_kind="strategy")
        self.assertEqual(converted["status"],"UNSUPPORTED_PINE")
        self.assertIsNone(converted["python_code"])
        self.assertIn("unsupported_reason",converted)
        self.assertFalse(execute_wf02_node03(converted,workflow_kind="strategy")["paper_enabled"])
        with sqlite3.connect(self.tmp.name+"/wf02.sqlite") as db:
            existing={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("investment_python_conversions",existing)

    def test_missing_source_does_not_get_placeholder_code(self):
        with self.assertRaisesRegex(ValueError,"WF02_NO_STORED_PINE"):
            execute_wf02_node01({"ui_selection":"strategy","requested_detail_limit":1},
                                  workflow_kind="strategy")

if __name__=="__main__":
    unittest.main()
