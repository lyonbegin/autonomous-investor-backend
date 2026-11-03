"""Real existing 4-stage controller WF02 subgraph uses FREE local hoox-PYNE.

This is not a mock compiler and does not assert TradingView strategy parity.
"""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"editor-adapter"))
import investment_pipeline as pipe
import investment_free_pyne as free
from investment_tv_publication import register_for_existing_wf02,bundled_ddds_reference

class TestIntegratedFreePyne(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder=Path(self.temp.name)
        (folder/"stock-workflows"/"operations").mkdir(parents=True)
        shutil.copyfile(ROOT/"workflows"/"operations"/"WF02-pine-to-python.json",
                        folder/"stock-workflows"/"operations"/"WF02-pine-to-python.json")
        self.env=patch.dict(os.environ,{
            "STUDIO_DB_PATH":str(folder/"studio.sqlite3"),
            "STUDIO_STATIC_ROOT":str(folder),
            "INVESTMENT_DATABASE_URL":"",
            "PYNESYS_API_KEY":""})
        self.env.start()
        self.addCleanup(self.env.stop)
        pipe.init()

    def test_integrated_controller_runs_same_free_ddds_python_compilation(self):
        source=register_for_existing_wf02("sid",acknowledge_mpl=True)
        data=pipe.run_graph("run-test","python",pipe.PYTHON,{
            "ui_selection":"strategy","requested_detail_limit":1,
            "source_id":source["source_id"],"version_key":source["version_key"]})
        self.assertEqual(data["status"],"PYNE_FREE_GENERATED_UNVALIDATED")
        self.assertEqual(data["compiler"]["compiler"],free.COMPILER_ID)
        self.assertFalse(data["compiler"]["api_key_required"])
        self.assertEqual(data["source_sha256"],bundled_ddds_reference()["source_sha256"])
        from investment_source_registry import open_registry
        with open_registry() as db:
            rows=db.execute("""SELECT node_id, status FROM investment_pipeline_events
                                  WHERE run_id='run-test' ORDER BY event_id""").fetchall()
        self.assertEqual([x["node_id"] for x in rows],
                         [f"wf02-0{n}" for n in range(1,7)])
        source_listing=pipe.saved_sources()
        selected=next(x for x in source_listing["sources"]
                      if x["source_id"]==source["source_id"])
        self.assertTrue(selected["free_pyne_generated_stored"])
        self.assertFalse(selected["legacy_python_code_stored"])
        self.assertEqual(source_listing["free_pyne"]["compiler"],free.COMPILER_ID)
        self.assertFalse(data["tradingview_chart_validated"])
        self.assertFalse(data["live_orders_enabled"])

if __name__=="__main__":unittest.main()
