"""Pine code persistence and duplicate checks, without author/SHA ledgers."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from investment_node_adapter import execute_node15,execute_node16
from investment_source_registry import check_candidates

CODE="//@version=6\nstrategy('test')\nplot(close)\n"
def incoming(code=CODE):
    return {"kind":"strategy",
      "candidate":{"kind":"strategy","source_id":"one","version_key":"v1"},
      "pine_code":code,"pine_source_acquired":True,"rights_state":"PENDING_REVIEW",
      "conversion_validated":False,"tradingview_chart_validated":False}

class StoreTests(unittest.TestCase):
    def test_save_then_show_and_skip_duplicate(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(
           os.environ,{"STUDIO_DB_PATH":temp+"/store.sqlite3"}):
            first=execute_node15(incoming(),workflow_kind="strategy")
            result=execute_node16(first,workflow_kind="strategy")
            self.assertEqual(result["status"],"PINE_SAVED_CONVERSION_PENDING")
            self.assertEqual(result["saved_count"],1)
            self.assertFalse(result["paper_enabled"])
            self.assertEqual(execute_node16(execute_node15(incoming(),
                 workflow_kind="strategy"),workflow_kind="strategy")["saved_count"],0)
            with sqlite3.connect(temp+"/store.sqlite3") as db:
                self.assertEqual(db.execute(
                    "SELECT pine_code FROM investment_pine_payloads").fetchone()[0],CODE)
                cols={x[1] for x in db.execute(
                    "PRAGMA table_info(investment_pine_payloads)")}
                self.assertFalse({"pine_sha256","author","source_url"} & cols)
            self.assertEqual(check_candidates("strategy",[
               {"kind":"strategy","source_id":"one","version_key":"v1"}]
               )["imported_count"],1)

    def test_existing_version_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(
           os.environ,{"STUDIO_DB_PATH":temp+"/store.sqlite3"}):
            execute_node15(incoming(),workflow_kind="strategy")
            with self.assertRaisesRegex(ValueError,"DIFFERENT_CODE"):
                execute_node15(incoming(CODE+"// changed"),workflow_kind="strategy")
            with self.assertRaisesRegex(ValueError,"SOURCE_NOT_ACQUIRED"):
                execute_node15({**incoming(),"pine_source_acquired":False},
                               workflow_kind="strategy")
            with self.assertRaisesRegex(ValueError,"SOURCE_SAVE_NOT_COMPLETE"):
                execute_node16(incoming(),workflow_kind="strategy")

if __name__=="__main__":unittest.main()
