"""Run a real PyneCore ScriptRunner on synthetic, explicitly labeled bars."""
import csv
import hashlib
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pine-parity"))
from pynecore_bridge import ParityInputError, read_reference, run_compiled_pynecore

# A hand-authored PyneCore test fixture; NOT claimed to be PyneComp output.
FIXTURE = '''"""
@pyne
"""
from pynecore.lib import script, close, plot

@script.indicator("Worker Test", overlay=True)
def main():
    plot(close, "Price")
'''


def bars_csv(*, corrupt_reference=False):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "time", "open", "high", "low", "close", "volume", "TV Price"
    ])
    writer.writeheader()
    for n in range(20):
        timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=n)
        close = float(100 + n)
        writer.writerow({
            "time": timestamp.isoformat(), "open": close - 0.5,
            "high": close + 1, "low": close - 1,
            "close": close, "volume": 1000 + n,
            "TV Price": close + (1.0 if corrupt_reference and n == 9 else 0.0)
        })
    return buf.getvalue()


SYMBOL = {
    "prefix": "TEST", "ticker": "TEST", "description": "Synthetic CI bars",
    "currency": "USD", "basecurrency": "USD", "period": "60", "type": "stock",
    "mintick": 0.01, "pricescale": 100, "minmove": 1, "pointvalue": 1.0,
    "mincontract": 1.0,
    "timezone": "UTC", "volumetype": "base",
    "opening_hours": [], "session_starts": [], "session_ends": [],
}


class TestRealPyneCoreRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "compiled.py"
        self.path.write_text(FIXTURE, encoding="utf-8")
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.env = patch.dict(os.environ, {
            "INVESTMENT_ISOLATED_PYNECORE_WORKER": "1",
            "INVESTMENT_PYNECORE_ARTIFACT_ROOT": self.tmp.name,
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_worker(self, csv_text=None):
        return run_compiled_pynecore(self.path, self.sha, csv_text or bars_csv(),
                                      SYMBOL, {"Price": "TV Price"})

    def test_real_script_runner_matches_price_plot(self):
        result = self.run_worker()
        self.assertEqual(result["status"], "NUMERIC_MATCH_TRADE_PARITY_UNVERIFIED")
        self.assertTrue(result["numeric_plot_match"])
        self.assertEqual(result["bar_count"], 20)
        self.assertEqual(result["comparison"][0]["bars_compared"], 20)
        self.assertFalse(result["conversion_validated"])
        self.assertFalse(result["paper_enabled"])
        self.assertEqual(result["series"][10]["plots"]["Price"], 110.0)

    def test_real_runner_detects_plot_mismatch_on_exact_bar(self):
        result = self.run_worker(bars_csv(corrupt_reference=True))
        self.assertEqual(result["status"], "NUMERIC_MISMATCH")
        self.assertEqual(result["comparison"][0]["mismatch_count"], 1)
        self.assertEqual(result["comparison"][0]["first_mismatches"][0]["bar_index"], 9)

    def test_never_run_without_isolation(self):
        with patch.dict(os.environ, {"INVESTMENT_ISOLATED_PYNECORE_WORKER": "0"}):
            with self.assertRaisesRegex(ParityInputError, "ISOLATED_PYNECORE_WORKER_REQUIRED"):
                self.run_worker()

    def test_never_run_changed_generated_code(self):
        with self.assertRaisesRegex(ParityInputError, "HASH_MISMATCH"):
            run_compiled_pynecore(self.path, "0" * 64, bars_csv(),
                                  SYMBOL, {"Price": "TV Price"})

    def test_reject_timestamp_without_timezone(self):
        source = bars_csv().replace("+00:00", "")
        with self.assertRaisesRegex(ParityInputError, "TIMEZONE_REQUIRED"):
            read_reference(source)


if __name__ == "__main__":
    unittest.main()
