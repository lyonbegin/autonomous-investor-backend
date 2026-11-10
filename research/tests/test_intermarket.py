import hashlib
import tempfile
import unittest
from pathlib import Path
from research.intermarket import Parameters, backtest, cme_trade_pnl, read_verified_csv


class IntermarketResearchTests(unittest.TestCase):
    def test_cme_illustrative_contract_pnl(self):
        result = cme_trade_pnl(988.40, 1056.40, 1231.90, 1244.20)
        self.assertEqual(result["pl_pnl_usd"], 6800)
        self.assertEqual(result["gc_pnl_usd"], -1230)
        self.assertEqual(result["gross_pnl_usd"], 5570)

    def test_cost_is_not_ignored(self):
        result = cme_trade_pnl(988.40, 1056.40, 1231.90, 1244.20, commission_usd=18)
        self.assertEqual(result["net_pnl_usd"], 5552)

    def test_no_same_bar_execution(self):
        bars = []
        for i in range(12):
            pl = 100 if i < 5 or i >= 9 else 80
            bars.append({"timestamp": f"2020-01-{i+1:02d}",
                         "pl_open": float(pl), "pl_close": float(pl),
                         "gc_open": 100.0, "gc_close": 100.0})
        outcome = backtest(bars, Parameters(lookback=3, entry_z=1.0))
        self.assertTrue(all(t["timestamp"] != "2020-01-06" for t in outcome["trades"]
                            if t["reason"] == "prior_close_signal"))
        self.assertEqual(outcome["status"], "FUNCTIONAL_BACKTEST_NOT_EXECUTION_VERIFIED")

    def test_refuse_missing_prices(self):
        with self.assertRaises(ValueError):
            backtest([])

    def test_data_checksum_gate(self):
        raw = ("timestamp,pl_open,pl_close,gc_open,gc_close\n"
               "2020-01-01,990,991,1230,1232\n").encode()
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "bars.csv"
            file.write_bytes(raw)
            with self.assertRaises(ValueError):
                read_verified_csv(file, "0" * 64)
            verified = read_verified_csv(file, hashlib.sha256(raw).hexdigest())
            self.assertEqual(len(verified), 1)


if __name__ == "__main__":
    unittest.main()
