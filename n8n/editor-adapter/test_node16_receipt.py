"""WF01 N16 SQLite readback contract; local test fixtures, not production evidence."""
import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch
from investment_source_registry import open_registry
from investment_node_adapter import execute_node15, execute_node16, node_binding, execute_node

class Node16ReceiptTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patch=patch.dict(os.environ,{"STUDIO_DB_PATH":self.temp.name+"/stock.sqlite3"})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)

    def source(self,kind):
        code="//@version=6\n// This Source Code Form is subject to the terms of the Mozilla Public License 2.0\n// © Test Author\nstrategy(\"test\", overlay=true)\n"
        digest=hashlib.sha256(code.encode()).hexdigest()
        candidate={"kind":kind,"source_id":"test-001","version_key":"v1","source_url":"https://www.tradingview.com/script/TEST01/","author":"Test Author","pine_version":"6","source_license_reported":"MPL-2.0","source_sha256_reported":digest}
        return {"kind":kind,"candidate":candidate,"pine_code":code,"pine_source_sha256":digest,"source_review_approved":False,"conversion_validated":False,"tradingview_chart_validated":False,"rights_state":"PENDING_REVIEW","source_available":True,"source_integrity_checked":True,"source_branch":"VERIFIED_PINE_TO_IMPORT","_studio_active_ports":[0]}

    def test_stored_receipt_verified_and_idempotent(self):
        for kind in ("strategy","library"):
            with self.subTest(kind=kind):
                path=f"operations/WF01-latest-{kind}-one.json"
                self.assertEqual(node_binding(path,f"wf01-{kind}-16")["python_function"],"execute_node16")
                saved=execute_node15(self.source(kind),workflow_kind=kind)
                verified=execute_node(path,f"wf01-{kind}-16",saved)
                self.assertTrue(verified["db_readback_verified"])
                self.assertEqual(verified["status"],"SOURCE_STORED_REVIEW_PENDING")
                self.assertEqual(verified["saved_count"],1)
                self.assertFalse(verified["paper_enabled"])
                self.assertFalse(verified["live_orders_enabled"])
                repeat=execute_node15(self.source(kind),workflow_kind=kind)
                self.assertEqual(execute_node16(repeat,workflow_kind=kind)["saved_count"],0)

    def test_fail_closed_before_or_after_tampering(self):
        data=self.source("strategy")
        with self.assertRaisesRegex(ValueError,"N16_N15_SUCCESS_RECEIPT_REQUIRED"):
            execute_node16(data,workflow_kind="strategy")
        saved=execute_node15(data,workflow_kind="strategy")
        with self.assertRaisesRegex(ValueError,"N16_PREMATURE_APPROVAL_CLAIM"):
            execute_node16({**saved,"conversion_validated":True},workflow_kind="strategy")
        with open_registry() as db:
            db.execute("UPDATE investment_pine_source_artifacts SET pine_code='tampered'")
            db.commit()
        with self.assertRaisesRegex(ValueError,"N16_PERSISTED_SOURCE_READBACK_MISMATCH"):
            execute_node16(saved,workflow_kind="strategy")

if __name__=="__main__":
    unittest.main()
