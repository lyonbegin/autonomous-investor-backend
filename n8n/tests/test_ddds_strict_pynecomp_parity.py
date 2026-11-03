"""Deterministic contract tests for same-strategy DDDS parity guard.

All generated 299 rows below are synthetic and MUST NEVER be used as a
TradingView evidence fixture. Test is only of comparison logic.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"editor-adapter"))

from investment_tv_publication import bundled_ddds_reference
from investment_ddds_parity import (
    DDDS_SOURCE_SHA, DDDS_SOURCE_ID, DDDS_VERSION, DDDS_COMPILER,
    SOURCE_DEFAULTS, source_defaults_from_pine,
    readiness_from_existing_cache, compare_published_ddds_trades)


def fixture():
    rows = [{
        "trade_number":n,"side":"LONG" if n%2 else "SHORT",
        "entry_price_display":100+n*.01,
        "exit_price_display":100+n*.01+.25,
        "entry_time_display":"Jan 1, 2025, 13:30",
        "exit_time_display":"Jan 1, 2025, 15:30"
    } for n in range(299,0,-1)]
    ref={
        "status":"PUBLISHED_DDDS_299_TRADES_CAPTURED",
        "capture_verified_complete":True,
        "observed_trade_count":299,
        "pine_source_sha256":DDDS_SOURCE_SHA,
        "trades":rows
    }
    actual={
        "pine_source_sha256":DDDS_SOURCE_SHA,
        "source_id":DDDS_SOURCE_ID,
        "version_key":DDDS_VERSION,
        "compiler_id":DDDS_COMPILER,
        "compiler_result_origin":"REAL_PYNECOMP_API",
        "python_sha256":"a"*64,
        "symbol":"NASDAQ:AMZN","interval_minutes":120,
        "reference_symbol_resolution":"PUBLISHED_REPORT_NASDAQ_AMZN_RECONCILED",
        "run_origin":"ISOLATED_PYNECORE_SCRIPT_RUNNER",
        "data_origin":"INDEPENDENT_LICENSED_BATS_AMZN_HISTORY",
        "data_coverage_complete":True,
        "closed_trades":[{
            "direction":row["side"],
            "entry_price":row["entry_price_display"]+0.001,
            "exit_price":row["exit_price_display"]-0.001
        } for row in reversed(rows)]
    }
    return ref,actual


class DDDSActualConversionGuardTests(unittest.TestCase):
    def test_read_all_pine_strategy_defaults_from_actual_bundled_141_lines(self):
        reference=bundled_ddds_reference()
        self.assertEqual(reference["source_sha256"],DDDS_SOURCE_SHA)
        source=source_defaults_from_pine(reference["pine_source"])
        self.assertEqual(source,SOURCE_DEFAULTS)
        self.assertEqual(source["startLen"],31)
        self.assertEqual(source["commission_value"],0.05)
        self.assertEqual(source["atrLen"],14)
        self.assertEqual(source["default_qty_value"],100)
        self.assertEqual(source["initial_capital"],10000)

    def test_actual_current_tradingview_properties_match_defaults_but_not_original_chart_symbol(self):
        from investment_ddds_parity import current_published_properties_proof
        evidence=current_published_properties_proof()
        self.assertEqual(evidence["currently_displayed_report_symbol"],"NASDAQ:AMZN")
        self.assertEqual(evidence["publication_chart_snapshot_symbol"],"BATS:AMZN")
        self.assertEqual(evidence["current_report_timeframe_minutes"],120)
        self.assertEqual(evidence["current_report_execution"]["slippage_ticks"],0)
        self.assertTrue(evidence["current_report_inputs_match_pine_defaults"])
        self.assertFalse(evidence["same_chart_symbol_confirmed"])

    def test_detect_compiler_missing_without_fabricating_a_pynecore_chart(self):
        r=readiness_from_existing_cache(
            pine=bundled_ddds_reference()["pine_source"],
            reference=None,cached_python=None,free_compiler_installed=False)
        self.assertEqual(r["status"],"DDDS_VERIFICATION_BLOCKED")
        self.assertIn("PYNE_FREE_RUNTIME_NOT_INSTALLED",r["missing_requirements"])
        self.assertIn("EXACT_DDDS_FREE_PYNE_PYTHON",r["missing_requirements"])
        self.assertEqual(r["source_input_defaults"]["startLen"],31)
        self.assertFalse(r["tradingview_pynecore_parity_verified"])
        self.assertFalse(r["paper_enabled"])
        self.assertFalse(r["settings_are_published_properties"])

    def test_matching_trade_prices_are_never_trade_or_plot_parity_approval(self):
        ref,actual=fixture()
        result=compare_published_ddds_trades(ref,actual)
        self.assertEqual(result["status"],"DDDS_TRADE_PRICES_MATCH_REVIEW_REQUIRED")
        self.assertEqual(result["compared_price_values"],598)
        self.assertFalse(result["tradingview_pynecore_parity_verified"])
        self.assertFalse(result["live_orders_enabled"])
        self.assertIn("ORDER_PLACEMENT_AND_FILL_EVENTS",
                      result["missing_fidelity_checks"])

    def test_refuses_wrong_strategy_even_if_299_prices_match(self):
        ref,actual=fixture()
        actual["source_id"]="PUB;WRONG"
        self.assertEqual(compare_published_ddds_trades(ref,actual)["status"],
                         "BLOCKED_IDENTICAL_PYNECOMP_ARTIFACT_NOT_PROVEN")

    def test_conflicting_publication_snapshot_and_report_symbol_is_blocked(self):
        ref,actual=fixture()
        actual.pop("reference_symbol_resolution")
        result=compare_published_ddds_trades(ref,actual)
        self.assertEqual(result["status"],"BLOCKED_PUBLISHED_CHART_REPORT_SYMBOL_CONFLICT")
        self.assertEqual(result["frozen_chart_symbol"],"BATS:AMZN")
        self.assertEqual(result["published_report_symbol"],"NASDAQ:AMZN")

    def test_refuses_aapl_or_wrong_timeframe(self):
        ref,actual=fixture()
        actual["symbol"]="NASDAQ:AAPL"
        self.assertEqual(compare_published_ddds_trades(ref,actual)["status"],
                         "BLOCKED_MARKET_SYMBOL_TIMEFRAME_MISMATCH")

    def test_refuses_short_historical_300bar_window_as_299_trade_baseline(self):
        ref,actual=fixture()
        actual["data_coverage_complete"]=False
        self.assertEqual(compare_published_ddds_trades(ref,actual)["status"],
                         "BLOCKED_BATS_AMZN_2H_HISTORY_COVERAGE")

    def test_refuses_298_versus_299_trade_count(self):
        ref,actual=fixture()
        actual["closed_trades"].pop()
        result=compare_published_ddds_trades(ref,actual)
        self.assertEqual(result["status"],"DDDS_TRADE_COUNT_MISMATCH")
        self.assertEqual(result["count_difference"],-1)

    def test_refuses_different_price_and_reports_earliest_mismatch(self):
        ref,actual=fixture()
        actual["closed_trades"][0]["exit_price"]+=3
        result=compare_published_ddds_trades(ref,actual)
        self.assertEqual(result["status"],"DDDS_PUBLISHED_PRICE_SIDE_MISMATCH")
        self.assertEqual(result["mismatch_samples"][0]["trade_number"],1)
        self.assertIn("EXIT_PRICE",result["mismatch_samples"][0]["fields"])

    def test_declines_unverified_tradingview_reference(self):
        ref,actual=fixture()
        ref["capture_verified_complete"]=False
        result=compare_published_ddds_trades(ref,actual)
        self.assertEqual(result["status"],"BLOCKED_OFFICIAL_TRADE_BASELINE_MISSING")

if __name__=="__main__":
    unittest.main()
