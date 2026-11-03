"""Live PyneCore 6.11.1 on genuine public EURUSD historical bars and official
PyneComp-converted indicators/strategies (not artificial numeric fixtures).
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pine-parity"))
from demo_engine import execute_demo


class TestPublishedPyneCompSamples(unittest.TestCase):
    def test_real_market_bollinger_and_sma_strategy(self):
        result = execute_demo()
        self.assertEqual(result["status"], "PYNECORE_REAL_MARKET_EXECUTED_TV_PARITY_PENDING")
        self.assertGreaterEqual(result["bar_count"], 900)
        self.assertEqual(result["plots_calculated"], result["bar_count"])
        self.assertGreater(result["strategy_closed_trades"], 0)
        self.assertEqual(len(result["chart"]), 260)
        self.assertTrue(any(r.get("Basis") is not None for r in result["chart"]))
        self.assertTrue(any(r.get("Upper") is not None for r in result["chart"]))
        self.assertTrue(any(r.get("Lower") is not None for r in result["chart"]))
        self.assertGreater(result["time_to_ms"], result["time_from_ms"])
        self.assertEqual(result["compiler_source"], "PYNESYS_PUBLIC_PYNECOMP_COMPILED_EXAMPLES")
        self.assertEqual(result["license"], "CC0-1.0")
        for name in ("bollinger_bands.py","sma_crossover.py","EURUSD_1h.csv"):
            self.assertEqual(len(result["sha256"][name]),64)
        self.assertFalse(result["market_data_is_synthetic"])
        self.assertFalse(result["new_pynecomp_compilation"])
        self.assertFalse(result["conversion_validated"])
        self.assertFalse(result["tradingview_chart_validated"])
        self.assertFalse(result["live_orders_enabled"])


if __name__ == "__main__":
    unittest.main()
