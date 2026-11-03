"""Real compiled DDDS + Python runner on the exact SAME supplied OHLCV.
Synthetic prices are labelled as unit-test inputs, NOT live TradingView data.
"""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"editor-adapter"))
from investment_ddds_parity import DDDS_SOURCE_SHA,DDDS_SOURCE_ID
import investment_shared_bars_compare as cmp
from investment_free_pyne_chart import PINNED_PYTHON_SHA

def make_payload():
    rows=[]
    for i in range(240):
        price=150+i*.12
        rows.append({
          "time_ms":1760000000000+i*7200000,
          "open":price,"high":price+2,"low":price-2,
          "close":price+.5,"volume":10000+i*3
        })
    return {"source_id":DDDS_SOURCE_ID,"pine_source_sha256":DDDS_SOURCE_SHA,
            "symbol":"NASDAQ:AMZN","timeframe":"120",
            "acknowledge_mpl":True,"bars":rows}

class SharedBarsTests(unittest.TestCase):
    def test_original_ddds_is_really_compiled_with_pinned_sha(self):
        code=cmp.pinned_python()
        self.assertEqual(hashlib.sha256(code.encode()).hexdigest(),PINNED_PYTHON_SHA)
        self.assertIn("def execute_script_compiled(",code)

    def test_real_ddds_generated_python_runs_on_same_240_bars(self):
        payload=make_payload()
        result=cmp.execute_shared_bars(payload)
        self.assertEqual(result["status"],"EXACT_SITE_CHART_INPUT_PYTHON_EXECUTED")
        self.assertEqual(result["bar_count"],240)
        self.assertEqual(result["time_ms"],[x["time_ms"] for x in payload["bars"]])
        self.assertEqual(result["close"],[x["close"] for x in payload["bars"]])
        self.assertEqual(len(result["plots"]["Decycler"]),240)
        self.assertTrue(any(z is not None for z in result["plots"]["Decycler"]))
        self.assertFalse(result["vela_pine_ddds_indicator_parity_verified"])
        self.assertFalse(result["official_tradingview_publication_parity_verified"])
        self.assertFalse(result["published_299_trades_compared"])
        self.assertFalse(result["live_orders_enabled"])
        self.assertFalse(result["paper_enabled"])

    def test_mutated_ddds_sha_is_blocked(self):
        p=make_payload();p["pine_source_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"SOURCE_SYMBOL_TIMEFRAME_OR_RIGHTS"):
            cmp.exact_bars(p)

    def test_different_timeframe_is_blocked(self):
        p=make_payload();p["timeframe"]="1h"
        with self.assertRaisesRegex(ValueError,"SOURCE_SYMBOL_TIMEFRAME_OR_RIGHTS"):
            cmp.exact_bars(p)

    def test_explicit_mpl_acknowledgement_required(self):
        p=make_payload();p["acknowledge_mpl"]=False
        with self.assertRaisesRegex(ValueError,"SOURCE_SYMBOL_TIMEFRAME_OR_RIGHTS"):
            cmp.exact_bars(p)

    def test_wrong_price_is_blocked(self):
        p=make_payload();p["bars"][20]["close"]=99999
        with self.assertRaisesRegex(ValueError,"OHLCV_INVALID"):
            cmp.exact_bars(p)

    def test_duplicate_time_is_blocked(self):
        p=make_payload();p["bars"][15]["time_ms"]=p["bars"][14]["time_ms"]
        with self.assertRaisesRegex(ValueError,"NOT_STRICTLY_INCREASING"):
            cmp.exact_bars(p)

    def test_unknown_extra_bar_data_is_blocked(self):
        p=make_payload();p["bars"][0]["indicator_fake"]=3
        with self.assertRaisesRegex(ValueError,"BAR_SHAPE_MISMATCH"):
            cmp.exact_bars(p)

    def test_generated_python_must_match_pinned_sha(self):
        p=make_payload()
        with self.assertRaisesRegex(ValueError,"PYTHON_SHA_MISMATCH"):
            cmp.execute_shared_bars(p,compiled_code="def fake(): pass")

if __name__=="__main__":
    unittest.main()
