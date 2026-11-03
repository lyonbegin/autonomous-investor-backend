"""No-network regression for TradingView chart message parsing."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from official_chart_probe import decode_chart_messages, collect_bars


class ChartCaptureTests(unittest.TestCase):
    def test_transport_multipart_and_typed_ohlcv(self):
        a = '{"m":"timescale_update","p":[{"s1":{"s":[{"v":[1793629800,342.67,343.8,335.82,338.32,64757691]}]}}]}'
        b = '{"m":"study_completed","p":[]}'
        raw = "~m~"+str(len(a))+"~m~"+a+"~m~"+str(len(b))+"~m~"+b
        messages = decode_chart_messages(raw)
        self.assertEqual([x["m"] for x in messages], ["timescale_update", "study_completed"])
        bars = {}
        collect_bars(messages[0]["p"], bars)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[1793629800000]["close"], 338.32)

    def test_reject_impossible_ohlc_and_noise(self):
        payload = [{"v":[1793629800,342.67,330,335.82,338.32,1]},
                   {"v":[1793629800,342.67,343.8,335.82,338.32,1]}]
        bars = {}
        collect_bars(payload, bars)
        self.assertEqual(len(bars), 1)
        self.assertEqual(decode_chart_messages('~m~999999999~m~bad'), [])


if __name__ == "__main__":
    unittest.main()
