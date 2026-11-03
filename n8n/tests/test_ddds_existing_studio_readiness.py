"""WF02 actual stored DDDS source + PyneComp cache readiness wiring tests."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"editor-adapter"))
import investment_ddds_parity as parity
from investment_tv_publication import register_for_existing_wf02
from investment_pynecomp import save_cache,dependency_lock


class DDDSReadinessIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env=patch.dict(os.environ,{
            "STUDIO_DB_PATH":str(Path(self.tmp.name)/"studio.sqlite3"),
            "INVESTMENT_DATABASE_URL":"",
            "PYNESYS_API_KEY":""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_real_source_registration_and_preexisting_wf02_store(self):
        missing=parity.readiness_for_studio_session("different-new-session")
        self.assertEqual(missing["status"],"DDDS_VERIFICATION_BLOCKED")
        self.assertFalse(missing["identical_source_in_workflow_db"])
        record=register_for_existing_wf02("main-session",acknowledge_mpl=True)
        self.assertEqual(record["rights_state"],"APPROVED")
        d=parity.readiness_for_studio_session("main-session")
        self.assertEqual(d["source_id"],parity.DDDS_SOURCE_ID)
        self.assertEqual(d["version_key"],parity.DDDS_VERSION)
        self.assertTrue(d["identical_source_in_workflow_db"])
        self.assertFalse(d["exact_pynecomp_code_available"])
        self.assertIn("PYNESYS_API_KEY",d["missing_requirements"])
        self.assertIn("VERIFIED_NASDAQ_AMZN_120MIN_FULL_HISTORY_2016_2026",
                      d["missing_requirements"])
        self.assertEqual(d["saved_published_trade_count"],0)
        self.assertFalse(d["tradingview_pynecore_parity_verified"])
        self.assertFalse(d["live_orders_enabled"])

    def test_generated_artifact_cache_cannot_auto_approve_without_market_proof(self):
        register_for_existing_wf02("main-session",acknowledge_mpl=True)
        # Synthetic Python is intentionally stored only in this test-local DB;
        # this is NOT a PyneComp conversion or real TradingView result.
        save_cache("strategy",parity.DDDS_SOURCE_ID,parity.DDDS_VERSION,
                   parity.DDDS_SOURCE_SHA,dependency_lock([]),
                   "synthetic_local_test_value = 12\n")
        d=parity.readiness_for_studio_session("main-session")
        self.assertTrue(d["exact_pynecomp_code_available"])
        self.assertFalse(d["actual_ddds_pynecore_run_available"])
        self.assertFalse(d["tradingview_pynecore_parity_verified"])
        self.assertFalse(d["paper_enabled"])
        self.assertNotIn("PYNESYS_API_KEY",d["missing_requirements"])
        self.assertIn("ISOLATED_DDDS_PYNECORE_RUNTIME_RESULT",d["missing_requirements"])

if __name__=="__main__":
    unittest.main()
