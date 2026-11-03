"""WF-01 manually supplied real Pine library path: no false live TradingView claims."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from investment_node_adapter import (execute_node01,execute_node02,execute_node03,
    execute_node04,execute_node05,execute_node06,execute_node07,execute_node11,
    execute_node15,execute_node16)

PINE="//@version=6\nlibrary('User Supplied Functions',overlay=false)\nexport twice(float x) => x * 2\n"
MANUAL={"source_url":"https://www.tradingview.com/script/j7vCseM2/",
        "version_key":"user-submitted-v5","pine_code":PINE}

class ManualLibraryTests(unittest.TestCase):
    def test_user_supplied_library_reaches_sqlite_without_pretending_live(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,{"STUDIO_DB_PATH":directory+"/runs.sqlite",
                        "TRADINGVIEW_AUTHORIZED_CATALOG_URL":""}):
            a=execute_node01({"ui_selection":"library","requested_detail_limit":1,
                "manual_library":MANUAL},workflow_kind="library")
            b=execute_node02(a,workflow_kind="library")
            c=execute_node03(b,workflow_kind="library")
            self.assertFalse(c["catalog_is_live"])
            self.assertEqual(c["catalog_source"],"USER_SUBMITTED_LIBRARY_SOURCE")
            self.assertFalse(c["tradingview_requested"])
            d=execute_node04(c,workflow_kind="library")
            e=execute_node05(d,workflow_kind="library")
            f=execute_node06(e,workflow_kind="library")
            self.assertTrue(f["has_candidate"])
            g=execute_node07(f,workflow_kind="library")
            self.assertEqual(g["_studio_active_ports"],[0])
            h=execute_node11(g,workflow_kind="library")
            self.assertEqual(h["pine_code"],PINE)
            saved=execute_node15(h,workflow_kind="library")
            result=execute_node16(saved,workflow_kind="library")
            self.assertEqual(result["status"],"PINE_SAVED_CONVERSION_PENDING")
            self.assertEqual(result["saved_count"],1)
            self.assertFalse(result["tradingview_chart_validated"])
            with sqlite3.connect(directory+"/runs.sqlite") as db:
                self.assertEqual(db.execute("SELECT pine_code FROM investment_pine_payloads WHERE kind='library'").fetchone()[0],PINE)

    def test_without_library_source_must_block_at_n03(self):
        a=execute_node01({"ui_selection":"library","requested_detail_limit":1},workflow_kind="library")
        b=execute_node02(a,workflow_kind="library")
        with patch.dict(os.environ,{"TRADINGVIEW_AUTHORIZED_CATALOG_URL":""}):
            with self.assertRaisesRegex(ValueError,"LICENSED_MANIFEST_STRATEGIES_ONLY"):
                execute_node03(b,workflow_kind="library")

    def test_rejects_non_library_and_untrusted_source_urls(self):
        for item in ({**MANUAL,"source_url":"http://example.test/script/j7vCseM2/"},
                     {**MANUAL,"pine_code":"//@version=6\nindicator('not library')"}):
            with self.assertRaisesRegex(ValueError,"LIBRARY_"):
                execute_node01({"ui_selection":"library","requested_detail_limit":1,
                    "manual_library":item},workflow_kind="library")
