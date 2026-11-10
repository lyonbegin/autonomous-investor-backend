"""No false-green tests: WF02 DDDS source SHA, fresh 300 real-bar Python
runtime and previously verified Vela parity must all be independently checked.
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"editor-adapter"))
import investment_pipeline_ddds_bridge as bridge
import investment_pipeline
import investment_shared_bars_compare as shared
import investment_verified_catalog as catalog

ID=bridge.DDDS_SOURCE_ID
SHA=bridge.DDDS_SOURCE_SHA
VERSION=bridge.DDDS_VERSION
CODE="def actual_generated_entrypoint(): return 1\n"
PY_SHA=hashlib.sha256(CODE.encode()).hexdigest()
SELECTED={"source_id":ID,"version_key":VERSION,"source_sha256":SHA}


def chart_document(bars=300,symbol="NASDAQ:AMZN",
                   provenance="TRADINGVIEW_PUBLIC_CHART_PASSIVE_WEBSOCKET"):
    begin=1791374400000
    candles=[{
      "time_ms":begin+i*7200000,
      "open":248.0,"high":252.0,"low":246.0,
      "close":250.0,"volume":100000.0
    } for i in range(bars)]
    return {
      "status":"OFFICIAL_CHART_OHLCV_CAPTURED",
      "provenance":provenance,
      "symbol":symbol,"timeframe":"120",
      "licensed_data_api":False,
      "complete_2016_2026_history":False,
      "ddds_tradingview_orders_available":False,
      "interval_120_observed_gap_count":bars-1,
      "bar_count":len(candles),"bars":candles,
      "captured_at":"2026-11-10T00:00:00+00:00",
    }

def executed_runner(code,bars):
    assert code==CODE
    n=len(bars)
    return {"status":"EXACT_DDDS_FREE_PYNE_EXECUTED_ON_REAL_AMZN_120_BARS",
      "pine_sha256":SHA,"python_sha256":PY_SHA,"bars_executed":n,
      "plots":{k:[float(250.0)]*n for k in
         ("Decycler","Price anchor","Gradient","Lower band","Upper band","Stop","Target")}}


def verified_candidate(*args):
    return {"publish_ready":True,"python_sha256":PY_SHA,
      "verified_evidence":{"numeric_points":864,"numeric_mismatches":0,
        "verified_bar_count":300,"symbol":"NASDAQ:AMZN","timeframe":"2h",
        "evidence_url":"https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/41728553311",
        "visible_interval_evidence":"https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/41768325427"}}


class RealChartBridge(unittest.TestCase):
    def setUp(self):
        self.patches=[
          patch.object(bridge,"PINNED_PYTHON_SHA",PY_SHA),
          patch.object(shared,"PINNED_PYTHON_SHA",PY_SHA),
          patch.object(investment_pipeline,"saved_sources",return_value={"sources":[{**SELECTED,"rights_state":"APPROVED"}]}),
          patch.object(catalog,"candidate_check",side_effect=verified_candidate)
        ]
        for item in self.patches:item.start()
    def tearDown(self):
        for item in reversed(self.patches):item.stop()

    def run_real(self,**kw):
        def fetch_worker(url):
            self.assertEqual(url,bridge.WORKER)
            self.assertNotIn("autonomous-investor-public-api",url)
            return kw.pop("document",chart_document())
        return bridge.run_ddds_after_conversion(kw.pop("selected",SELECTED),
          kw.pop("code",CODE),fetch=fetch_worker,
          runner=kw.pop("runner",executed_runner))

    def test_300_exact_current_real_bars_only_claim_prior_vela_parity(self):
        x=self.run_real()
        self.assertEqual(x["bar_count"],300)
        self.assertTrue(x["current_input_is_full_300_bars"])
        self.assertEqual(x["market_provider"],"TRADINGVIEW_PUBLIC_CHART_PASSIVE_WEBSOCKET")
        self.assertEqual(x["python_sha256"],PY_SHA)
        self.assertTrue(x["current_python_runtime_executed"])
        self.assertFalse(x["current_input_vela_parity_evaluated_in_this_backend_run"])
        self.assertTrue(x["previous_site_parity_verified"])
        self.assertEqual(x["previous_site_parity_points"],864)
        self.assertEqual(x["symbol"],"NASDAQ:AMZN")
        self.assertIn("/verified/index.html?view=compare",x["chart_open_url"])
        self.assertFalse(x["official_tradingview_publication_parity_verified"])
        self.assertFalse(x["original_tradingview_299_trades_verified"])
        self.assertFalse(x["paper_enabled"])

    def test_block_other_source_even_with_pinned_ddds_python(self):
        with self.assertRaisesRegex(ValueError,"EXACT_PINNED_SOURCE"):
            self.run_real(selected={**SELECTED,"source_id":"PUB;another"})

    def test_missing_source_sha_is_not_deduced_or_fake_success(self):
        with self.assertRaisesRegex(ValueError,"EXACT_PINNED_SOURCE"):
            self.run_real(selected={"source_id":ID,"version_key":VERSION})

    def test_tampered_python_code_blocked(self):
        with self.assertRaisesRegex(ValueError,"PYNE_GENERATED_PYTHON_SHA"):
            self.run_real(code="print('SMA fake')")

    def test_compiled_pyne_sha_must_equal_previously_verified_artifact(self):
        with patch.object(catalog,"candidate_check",return_value={
            **verified_candidate(),"python_sha256":"f"*64}):
            with self.assertRaisesRegex(ValueError,"PREVIOUS_SITE_PARITY_PROVEN"):
                self.run_real()

    def test_bad_864_evidence_does_not_pass(self):
        altered=verified_candidate()
        altered["verified_evidence"]["numeric_mismatches"]=1
        with patch.object(catalog,"candidate_check",return_value=altered):
            with self.assertRaisesRegex(ValueError,"PRIOR_PARITY_PROVENANCE_MISSING"):
                self.run_real()

    def test_unapproved_rights_cannot_pretend_verified(self):
        with patch.object(catalog,"candidate_check",return_value={
            "publish_ready":False,"reason":"PINE_RIGHTS_NOT_APPROVED"}):
            with self.assertRaisesRegex(ValueError,"PREVIOUS_SITE_PARITY_PROVEN"):
                self.run_real()

    def test_worker_wrong_symbol_or_unverified_provenance_blocked(self):
        for data in (chart_document(symbol="BATS:AMZN"),
                     chart_document(provenance="UNVERIFIED_OR_FALLBACK")):
            with self.assertRaisesRegex(ValueError,"FREE_DDDS_EXPECTS_REAL_PUBLIC"):
                self.run_real(document=data)

    def test_current_80_worker_bars_run_without_claiming_300_fresh_bars(self):
        result=self.run_real(document=chart_document(bars=80))
        self.assertEqual(result["bar_count"],80)
        self.assertTrue(result["current_python_runtime_executed"])
        self.assertFalse(result["current_input_is_full_300_bars"])
        self.assertFalse(result["current_input_vela_parity_evaluated_in_this_backend_run"])

    def test_short_or_corrupt_worker_bars_blocked(self):
        with self.assertRaisesRegex(ValueError,"FREE_DDDS_OHLCV_BAR_COUNT_INVALID"):
            self.run_real(document=chart_document(bars=20))
        bad=chart_document()
        bad["bars"][5]["volume"]=None
        with self.assertRaisesRegex(ValueError,"FREE_DDDS_NONFINITE_OHLCV"):
            self.run_real(document=bad)

    def test_actual_http_request_posts_to_worker(self):
        class FakeResponse:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,limit):return json.dumps(chart_document()).encode()
        def fake_urlopen(req,timeout):
            self.assertEqual(req.get_method(),"POST")
            self.assertEqual(req.full_url,bridge.WORKER)
            self.assertEqual(timeout,90)
            return FakeResponse()
        with patch.object(bridge,"urlopen",side_effect=fake_urlopen):
            bars,market=bridge.fetch_site_bars()
        self.assertEqual(len(bars),300)
        self.assertEqual(market["provider"],"TRADINGVIEW_PUBLIC_CHART_PASSIVE_WEBSOCKET")



    def test_corrupted_generated_python_runtime_refused(self):
        def bad_runner(code,bars):
            out=executed_runner(code,bars)
            out["python_sha256"]="b"*64
            return out
        with self.assertRaisesRegex(ValueError,"RUNTIME_PROVENANCE_MISMATCH"):
            self.run_real(runner=bad_runner)

if __name__=="__main__":
    unittest.main()
