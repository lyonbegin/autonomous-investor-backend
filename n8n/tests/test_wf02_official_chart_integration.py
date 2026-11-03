"""Original WF-02 page integration tests, deliberately synthetic fixture for contract only."""
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor-adapter"))
import investment_tv_chart_integration as chart


class FakeResponse:
    status = 200
    def __init__(self, data):
        self.payload = json.dumps(data).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n):
        return self.payload[:n]


def contract_bars():
    first = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [{
        "time_ms": int((first + timedelta(days=i)).timestamp() * 1000),
        "open": 100+i, "high": 102+i, "low": 99+i,
        "close": 101+i+((i % 7)-3)*1.3, "volume": 1_000_000+i
    } for i in range(90)]


def provider(state="OFFICIAL_CHART_OHLCV_CAPTURED"):
    bars = contract_bars()
    return {
        "status":state,
        "provenance":"TRADINGVIEW_PUBLIC_CHART_PASSIVE_WEBSOCKET",
        "symbol":"NASDAQ:AAPL", "timeframe":"1D",
        "bar_count":len(bars), "bars":bars
    }


class TestWF02OfficialChartIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old_root, self.old_samples = chart.DATA_DIR, chart._SAMPLES
        chart.DATA_DIR = self.root
        chart._SAMPLES = Path(__file__).resolve().parents[1] / "pine-parity" / "demo"
        self.addCleanup(self.restore)

    def restore(self):
        chart.DATA_DIR, chart._SAMPLES = self.old_root, self.old_samples

    def test_real_pynecore_consumes_exact_90_contract_bars_and_saves_session(self):
        response = FakeResponse(provider())
        with patch.object(chart.urllib.request, "urlopen", return_value=response):
            result = chart.execute("session-only")
        self.assertEqual(result["status"], "OFFICIAL_CHART_OHLCV_PYNECORE_EXECUTED")
        self.assertEqual(result["bars_from_official_chart"], 90)
        self.assertEqual(result["bars_executed_by_pynecore"], 90)
        self.assertEqual(len(result["chart"]), 90)
        self.assertTrue(any(x.get("Basis") is not None for x in result["chart"]))
        self.assertFalse(result["tv_strategy_parity_verified"])
        self.assertFalse(result["user_selected_source_converted"])
        self.assertFalse(result["live_orders_enabled"])
        self.assertEqual(chart.latest("session-only")["bars_executed_by_pynecore"], 90)
        self.assertEqual(chart.latest("different-sid")["status"], "NO_EXECUTION_YET")

    def test_never_accept_wrong_provenance_as_official(self):
        data = provider()
        data["provenance"] = "VELA_PINETS_CHART_CONTROL"
        with patch.object(chart.urllib.request,"urlopen",return_value=FakeResponse(data)):
            with self.assertRaisesRegex(ValueError,"TV_PROVENANCE_INVALID"):
                chart.execute("session-only")
        self.assertEqual(chart.latest("session-only")["status"], "NO_EXECUTION_YET")

    def test_never_accept_chronological_errors(self):
        data = provider()
        data["bars"][5]["time_ms"] = data["bars"][4]["time_ms"]
        with patch.object(chart.urllib.request,"urlopen",return_value=FakeResponse(data)):
            with self.assertRaisesRegex(ValueError,"TV_BARS_NOT_CHRONOLOGICAL"):
                chart.execute("session-only")


if __name__ == "__main__":
    unittest.main()
