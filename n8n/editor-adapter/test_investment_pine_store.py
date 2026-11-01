"""Unit contracts for N15 real project SQLite persistence. Synthetic Pine
used ONLY for unit isolation, never represented as real TradingView data.
"""
import hashlib, os, sqlite3, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from investment_node_adapter import execute_node15,execute_node16
from investment_source_registry import check_candidates

PINE="//@version=6\n// © Example Author\nstrategy(\"test\", overlay=true)\nplot(close)\n"

def incoming(code=PINE):
    digest=hashlib.sha256(code.encode()).hexdigest()
    return {"kind":"strategy","candidate":{"kind":"strategy",
       "source_id":"PUB;one","version_key":"1.0",
       "source_url":"https://www.tradingview.com/script/ABCDEFGH/",
       "author":"Example Author","pine_version":"6",
       "source_license_reported":"MPL-2.0",
       "source_sha256_reported":digest},
      "pine_code":code,"pine_source_sha256":digest,
      "_studio_active_ports":[0],"source_branch":"VERIFIED_PINE_TO_IMPORT",
      "source_available":True,"source_integrity_checked":True,
      "source_review_approved":False,
      "conversion_validated":False,"tradingview_chart_validated":False,
      "rights_state":"MPL_2_0_REVIEW_REQUIRED"}

class PineStore(unittest.TestCase):
    def test_exact_source_persisted_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{"STUDIO_DB_PATH":str(Path(td)/"studio.sqlite3")}):
            row=incoming()
            first=execute_node15(row,workflow_kind="strategy")
            self.assertTrue(first["source_saved"])
            self.assertTrue(first["source_created"])
            self.assertEqual(first["saved_count"],1)
            receipt=execute_node16(first,workflow_kind="strategy")
            self.assertTrue(receipt["db_readback_verified"])
            self.assertEqual(receipt["status"],"SOURCE_STORED_REVIEW_PENDING")
            self.assertFalse(receipt["conversion_validated"])
            self.assertFalse(receipt["tradingview_chart_validated"])
            self.assertFalse(receipt["paper_enabled"])
            self.assertFalse(receipt["live_orders_enabled"])
            with self.assertRaisesRegex(ValueError,"N16_SOURCE_HASH_INVALID"):
                execute_node16({**first,"pine_code":first["pine_code"]+"//modified"},workflow_kind="strategy")
            second=execute_node15(row,workflow_kind="strategy")
            self.assertTrue(second["source_saved"])
            self.assertFalse(second["source_created"])
            self.assertEqual(second["saved_count"],0)
            with sqlite3.connect(str(Path(td)/"studio.sqlite3")) as db:
                saved=db.execute("SELECT pine_code,pine_sha256,rights_state,conversion_validated FROM investment_pine_source_artifacts").fetchone()
                self.assertEqual(saved[0],PINE)
                self.assertEqual(saved[1],hashlib.sha256(PINE.encode()).hexdigest())
                self.assertEqual(saved[2],"MPL_2_0_REVIEW_REQUIRED")
                self.assertEqual(saved[3],0)
            checked=check_candidates("strategy",[row["candidate"]])
            self.assertEqual(checked["imported_count"],1)
            self.assertTrue(checked["items"][0]["imported"])
            self.assertFalse(checked["items"][0]["conversion_approved"])

    def test_version_conflict_and_unverified_source_rejected(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{"STUDIO_DB_PATH":str(Path(td)/"studio.sqlite3")}):
            row=incoming()
            execute_node15(row,workflow_kind="strategy")
            with self.assertRaisesRegex(ValueError,"N15_EXISTING_SOURCE_VERSION_HAS_DIFFERENT_BYTES"):
                execute_node15(incoming(PINE+"// changed\n"),workflow_kind="strategy")
            with self.assertRaisesRegex(ValueError,"N15_UNVERIFIED_N13_BRANCH"):
                execute_node15({**row,"_studio_active_ports":[1]},workflow_kind="strategy")
            with self.assertRaisesRegex(ValueError,"N15_SOURCE_NOT_VALIDATED_BY_N12"):
                execute_node15({**row,"source_integrity_checked":False},workflow_kind="strategy")
            with self.assertRaisesRegex(ValueError,"N15_UNVERIFIED_CONVERSION_CLAIM"):
                execute_node15({**row,"conversion_validated":True},workflow_kind="strategy")

if __name__=="__main__":unittest.main()
