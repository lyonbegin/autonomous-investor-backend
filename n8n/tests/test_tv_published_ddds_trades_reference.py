"""Offline contract tests for original WF02's pinned public DDDS trade baseline.

The 299 test fixtures below are SYNTHETIC; live Chromium CI separately
verifies real public TradingView values before approving deployment.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"editor-adapter"))
import investment_tv_trade_reference as tv
from investment_tv_publication import bundled_ddds_reference


def mock_trades():
    base=bundled_ddds_reference()
    rows=[]
    for i in range(299,0,-1):
        raw=f"{i}Long\nExit\nEntry\nOct 19, 2026, 13:30\nOct 16, 2026, 17:30\n255.60\nUSD\n250.04\nUSD\n113\nUSD"
        rows.append({"trade_number":i,"side":"LONG",
                     "entry_time_display":"Oct 16, 2026, 17:30",
                     "exit_time_display":"Oct 19, 2026, 13:30",
                     "entry_price_display":250.04,"exit_price_display":255.60,
                     "time_zone":"NOT_DECLARED_IN_PUBLISHED_ROW",
                     "raw_visible_trade":raw})
    digest=hashlib.sha256("\n".join(f'{r["trade_number"]}\t{r["raw_visible_trade"]}' for r in rows).encode()).hexdigest()
    return {
        "status":"PUBLISHED_DDDS_299_TRADES_CAPTURED",
        "source":"OFFICIAL_TRADINGVIEW_PUBLICATION_VISIBLE_STRATEGY_REPORT",
        "source_code_reference_sha256":base["source_sha256"],
        "expected_trade_count":299,"observed_trade_count":299,
        "capture_verified_complete":True,
        "tradingview_pynecore_parity_verified":False,
        "is_live_strategy_tester_export":False,
        "rows_sha256":digest,
        "trades":rows
    }


class PublishedDDDS299ReferenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.patcher=patch.object(tv,"latest_reference",return_value=bundled_ddds_reference())
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
    def test_correct_identity_and_299_rows_save_and_read_session(self):
        payload=mock_trades()
        result=tv.capture("sid",root=self.folder,transport=lambda req:payload)
        self.assertEqual(result["status"],"PUBLISHED_DDDS_299_TRADES_CAPTURED")
        self.assertFalse(result["live_orders_enabled"])
        self.assertFalse(result["tradingview_pynecore_parity_verified"])
        self.assertEqual(tv.latest("sid",self.folder)["observed_trade_count"],299)
        self.assertEqual(tv.latest("another-sid",self.folder)["status"],
                         "NO_OFFICIAL_DDDS_TRADES_CAPTURE")
    def test_reject_missing_row_instead_of_claiming_complete(self):
        data=mock_trades()
        data["trades"].pop()
        with self.assertRaisesRegex(ValueError,"ARRAY_INVALID"):
            tv.capture("sid",root=self.folder,transport=lambda req:data)
    def test_reject_false_tradingview_pynecore_verdict(self):
        data=mock_trades();data["tradingview_pynecore_parity_verified"]=True
        with self.assertRaisesRegex(ValueError,"PROVENANCE_OR_COUNT_INCOMPLETE"):
            tv.capture("sid",root=self.folder,transport=lambda req:data)
    def test_reject_corrupt_original_trade_row(self):
        data=mock_trades();data["trades"][0]["exit_price_display"]=245
        with self.assertRaisesRegex(ValueError,"HASH_MISMATCH"):
            tv.capture("sid",root=self.folder,transport=lambda req:data)
    def test_reject_other_pine_before_browser_call(self):
        fake=bundled_ddds_reference()
        fake["source_sha256"]="0"*64
        with patch.object(tv,"latest_reference",return_value=fake):
            with self.assertRaisesRegex(ValueError,"ONLY_EXACT"):
                tv.capture("sid",root=self.folder,transport=lambda req:mock_trades())

if __name__=="__main__":unittest.main()
