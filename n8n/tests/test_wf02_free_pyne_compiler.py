"""Integration: actual bundled DDDS 141 lines -> FREE PYNE -> Python in WF02.

No paid API, no fabricated generated source, no market/TV parity claims.
"""
import hashlib
import importlib.metadata
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"editor-adapter"))
import investment_free_pyne as free
from investment_tv_publication import register_for_existing_wf02,bundled_ddds_reference
from investment_wf02 import (execute_wf02_node01,execute_wf02_node02,
   execute_wf02_node03,execute_wf02_node04,execute_wf02_node05,execute_wf02_node06)
from investment_source_registry import open_registry


class TestOfflineFreeConverter(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env=patch.dict(os.environ,{
            "STUDIO_DB_PATH":str(Path(self.temp.name)/"studio.sqlite3"),
            "INVESTMENT_DATABASE_URL":"",
            "PYNESYS_API_KEY":""
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_actual_same_ddds_141_lines_through_all_six_wf02_nodes(self):
        assert free.installed(),"PYNE free compiler unavailable in CI image"
        pub=bundled_ddds_reference()
        registered=register_for_existing_wf02("test-session",acknowledge_mpl=True)
        self.assertEqual(registered["source_sha256"],pub["source_sha256"])
        input_json={"ui_selection":"strategy","requested_detail_limit":1,
                    "source_id":registered["source_id"],
                    "version_key":registered["version_key"]}
        stages=[execute_wf02_node01,execute_wf02_node02,execute_wf02_node03,
                execute_wf02_node04,execute_wf02_node05,execute_wf02_node06]
        data=input_json
        for fn in stages:
            data=fn(data,workflow_kind="strategy")
            self.assertFalse(data.get("conversion_validated",False))
            self.assertFalse(data.get("live_orders_enabled",False))
        self.assertEqual(data["status"],"PYNE_FREE_GENERATED_UNVALIDATED")
        self.assertEqual(data["converter_scope"],"PYNE_FREE_FULL_PINE")
        self.assertEqual(data["compiler"]["compiler"],free.COMPILER_ID)
        self.assertFalse(data["compiler"]["api_key_required"])
        self.assertEqual(data["source_sha256"],pub["source_sha256"])
        self.assertEqual(data["python_sha256"],hashlib.sha256(
                data["python_code"].encode()).hexdigest())
        self.assertIn("def execute_script_compiled(",data["python_code"])
        self.assertIn("CompileStrategyBroker",data["python_code"])
        self.assertFalse(data["runtime_execution_verified"])
        self.assertFalse(data["tradingview_chart_validated"])

        # The immutable cache must be read on repeat; never rerun compiler or
        # substitute some unrelated SMA/Bollinger sample.
        again=execute_wf02_node04(
            execute_wf02_node03(execute_wf02_node02(
                execute_wf02_node01(input_json,workflow_kind="strategy"),
                    workflow_kind="strategy"),workflow_kind="strategy"),
            workflow_kind="strategy")
        self.assertTrue(again["strategy_code_cache_hit"])
        self.assertEqual(again["python_code"],data["python_code"])
        with open_registry() as db:
            count=db.execute("SELECT COUNT(*) FROM investment_pyne_free_artifacts").fetchone()[0]
        self.assertEqual(count,1)

    def test_wrong_pine_sha_fails_closed(self):
        with self.assertRaisesRegex(free.FreePineBlocked,"PYNE_FREE_SOURCE_SHA_MISMATCH"):
            free.compile_pine("//@version=6\nstrategy('Wrong')",
                               expected_sha=bundled_ddds_reference()["source_sha256"])

    def test_external_pine_import_is_blocked_not_silently_discarded(self):
        with self.assertRaisesRegex(free.FreePineBlocked,"PYNE_FREE_LIBRARY_IMPORT_UNSUPPORTED"):
            free.compile_pine("//@version=6\nstrategy('X')\nimport A/B/2\n")

    def test_pending_review_never_compiles(self):
        row=register_for_existing_wf02("test-session",acknowledge_mpl=False)
        step=execute_wf02_node01({
            "ui_selection":"strategy","requested_detail_limit":1,
            "source_id":row["source_id"],"version_key":row["version_key"]},
            workflow_kind="strategy")
        self.assertEqual(step["status"],"WF02_SOURCE_RIGHTS_NOT_APPROVED")

if __name__=="__main__":unittest.main()
