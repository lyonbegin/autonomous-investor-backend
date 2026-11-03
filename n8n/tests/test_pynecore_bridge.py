"""Run a real PyneCore ScriptRunner on synthetic, explicitly labeled bars."""
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pine-parity"))
from pynecore_bridge import ParityInputError, read_reference, run_compiled_pynecore
from pynecore_worker import execute_job
from keypoint_parity import compare_keypoints

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

    def test_existing_keypoint_comparator_reports_real_pynecore_mismatch(self):
        data_root = Path(self.tmp.name) / "data"
        result_root = Path(self.tmp.name) / "results"
        data_root.mkdir()
        result_root.mkdir()
        reference = data_root / "tv.csv"
        reference.write_text(bars_csv(corrupt_reference=True), encoding="utf-8")
        job = data_root / "job.json"
        job.write_text(json.dumps({
            "job_id": "mismatch-worker-ci-1",
            "compiled_python": str(self.path),
            "python_sha256": self.sha,
            "reference_csv": str(reference),
            "syminfo": SYMBOL,
            "plot_mapping": {"Price": "TV Price"},
        }), encoding="utf-8")
        with patch.dict(os.environ, {
            "INVESTMENT_PYNECORE_DATA_ROOT": str(data_root),
            "INVESTMENT_PYNECORE_RESULT_ROOT": str(result_root),
        }):
            output = execute_job(job)
            result = json.loads(output.read_text(encoding="utf-8"))
            actual = Path(result["pynecore_csv_path"]).read_text(encoding="utf-8")
            check = compare_keypoints(reference.read_text(encoding="utf-8"), actual)
        self.assertEqual(check["status"], "KEYPOINTS_DIFFER")
        self.assertEqual(check["mismatch_total"], 1)
        self.assertEqual(check["keypoints"][0]["group"], "PLOT")
        self.assertEqual(check["keypoints"][0]["field"], "tv price")
        self.assertFalse(check["verified"])

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

    def test_isolated_job_writes_real_result_and_blocks_duplicate(self):
        data_root = Path(self.tmp.name) / "data"
        result_root = Path(self.tmp.name) / "results"
        data_root.mkdir()
        result_root.mkdir()
        reference = data_root / "reference.csv"
        reference.write_text(bars_csv(), encoding="utf-8")
        job = data_root / "job.json"
        job.write_text(json.dumps({
            "job_id": "pynecore-worker-ci-1",
            "compiled_python": str(self.path),
            "python_sha256": self.sha,
            "reference_csv": str(reference),
            "syminfo": SYMBOL,
            "plot_mapping": {"Price": "TV Price"},
            "compiler_reference": "HANDWRITTEN_PYNECORE_CI_FIXTURE",
        }), encoding="utf-8")
        with patch.dict(os.environ, {
            "INVESTMENT_PYNECORE_DATA_ROOT": str(data_root),
            "INVESTMENT_PYNECORE_RESULT_ROOT": str(result_root),
        }):
            output_path = execute_job(job)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(result["numeric_plot_match"])
            self.assertFalse(result["conversion_validated"])
            self.assertEqual(result["job_id"], "pynecore-worker-ci-1")
            exported_csv = Path(result["pynecore_csv_path"]).read_text(encoding="utf-8")
            from keypoint_parity import compare_keypoints
            compared = compare_keypoints(reference.read_text(encoding="utf-8"), exported_csv)
            self.assertEqual(compared["mismatch_total"], 0)
            self.assertEqual(compared["aligned_bars"], 20)
            self.assertEqual(compared["comparison_columns"]["plots"], ["tv price"])
            self.assertEqual(compared["status"], "KEYPOINTS_PARTIAL_NO_ORDER_OR_PLOT_EXPORT")
            self.assertFalse(compared["verified"])
            with self.assertRaises(FileExistsError):
                execute_job(job)


if __name__ == "__main__":
    unittest.main()
