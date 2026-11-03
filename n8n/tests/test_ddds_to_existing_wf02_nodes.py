"""Real original WF02 six-node execution contract for published 141-line DDDS.

This test runs the actual source registry and WF02 node functions; it does not
pretend a remote paid PyneComp response is available without credentials.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/"editor-adapter"
sys.path.insert(0,str(ROOT))
from investment_tv_publication import register_for_existing_wf02,bundled_ddds_reference
from investment_wf02 import (execute_wf02_node01,execute_wf02_node02,
  execute_wf02_node03,execute_wf02_node04,execute_wf02_node05,execute_wf02_node06)
from investment_source_registry import open_registry

class DDDSExistingSixNodes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env=patch.dict(os.environ,{"STUDIO_DB_PATH":str(Path(self.temp.name)/"studio.sqlite3"),
             "INVESTMENT_DATABASE_URL":"","PYNESYS_API_KEY":""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def input_for(self,reference):
        return {"ui_selection":"strategy","requested_detail_limit":1,
                "source_id":reference["source_id"],"version_key":reference["version_key"]}

    def test_exact_bundled_ddds_mpl_register_and_genuine_wf02_reaches_compiler_gate(self):
        record=register_for_existing_wf02("test-session",acknowledge_mpl=True)
        pinned=bundled_ddds_reference()
        self.assertEqual(record["source_sha256"],pinned["source_sha256"])
        self.assertEqual(record["status"],"PUBLISHED_PINE_REGISTERED_FOR_EXISTING_WF02")
        self.assertEqual(record["rights_state"],"APPROVED")
        self.assertTrue(record["user_acknowledged_mpl"])
        self.assertFalse(record["live_orders_enabled"])
        with open_registry() as db:
            row=db.execute("""SELECT pine_code,rights_state FROM investment_pine_payloads
              WHERE kind='strategy' AND source_id=? AND version_key=?""",
              (record["source_id"],record["version_key"])).fetchone()
            self.assertEqual(row["pine_code"],pinned["pine_source"])
            self.assertEqual(row["rights_state"],"APPROVED")
        data=execute_wf02_node01(self.input_for(record),workflow_kind="strategy")
        self.assertEqual(data["status"],"PINE_LOADED")
        self.assertEqual(data["source_sha256"],pinned["source_sha256"])
        data=execute_wf02_node02(data,workflow_kind="strategy")
        self.assertEqual(data["status"],"LIBRARIES_RESOLVED")
        data=execute_wf02_node03(data,workflow_kind="strategy")
        self.assertEqual(data["status"],"PYNECOMP_LIBRARIES_COMPILED")
        data=execute_wf02_node04(data,workflow_kind="strategy")
        self.assertEqual(data["status"],"PYNECOMP_API_KEY_MISSING")
        self.assertEqual(data["blocked_at"],"STRATEGY_COMPILATION")
        self.assertFalse(data["conversion_validated"])
        self.assertFalse(data["live_orders_enabled"])
        data=execute_wf02_node05(data,workflow_kind="strategy")
        data=execute_wf02_node06(data,workflow_kind="strategy")
        self.assertEqual(data["status"],"PYNECOMP_API_KEY_MISSING")
        self.assertFalse(data["paper_enabled"])
        self.assertFalse(data["tradingview_chart_validated"])
        self.assertFalse(data["compiler"]["api_key_configured"])

    def test_pending_review_cannot_escape_rights_gate(self):
        record=register_for_existing_wf02("test-session",acknowledge_mpl=False)
        self.assertEqual(record["rights_state"],"PENDING_REVIEW")
        data=execute_wf02_node01(self.input_for(record),workflow_kind="strategy")
        self.assertEqual(data["status"],"WF02_SOURCE_RIGHTS_NOT_APPROVED")
        self.assertFalse(data["conversion_validated"])

    def test_exact_idempotent_registration_and_immutable_sha(self):
        first=register_for_existing_wf02("test-session",acknowledge_mpl=True)
        second=register_for_existing_wf02("test-session",acknowledge_mpl=True)
        self.assertTrue(first["source_created"])
        self.assertFalse(second["source_created"])
        self.assertEqual(first["source_sha256"],second["source_sha256"])
        with open_registry() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM investment_pine_payloads").fetchone()[0],1)

if __name__=="__main__":
    unittest.main()
