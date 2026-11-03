"""Short, INPUT ONLY comparison: TV OHLCV vs arrays used by generated DDDS Python."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"editor-adapter"))
from investment_free_pyne_chart import compare_same_market_bars

def bars():
    return [
        {"time_ms":1780000000000+i*7200000,"open":100.0+i,"high":102.0+i,
         "low":99.0+i,"close":101.0+i,"volume":10000.0+i}
        for i in range(40)
    ]

def child(data):
    h=hashlib.sha256()
    for r in data:
        h.update(struct.pack("!q5d",r["time_ms"],*[float(r[k])
            for k in ("open","high","low","close","volume")]))
    return {"bars_executed":len(data),
            "market_input_sha256":h.hexdigest(),
            "market_input_close":[float(r["close"]) for r in data]}

class TestMarketInput(unittest.TestCase):
    def test_same_bars_compared_but_not_strategy_parity(self):
        source=bars()
        result=compare_same_market_bars(source,child(source))
        self.assertEqual(result["matching_bars"],40)
        self.assertEqual(result["mismatching_bars"],0)
        self.assertEqual(result["status"],"SAME_TV_MARKET_BARS_USED_BY_PYTHON")
        self.assertFalse(result["tradingview_pine_indicator_parity_verified"])
        self.assertFalse(result["published_bats_snapshot_compared"])

    def test_one_high_value_change_is_caught(self):
        source=bars()
        changed=[dict(row) for row in source]
        changed[17]["high"]+=0.01
        with self.assertRaisesRegex(ValueError,"DDDS_PYTHON_INPUT_OHLCV_MISMATCH"):
            compare_same_market_bars(source,child(changed))

    def test_one_timestamp_change_is_caught(self):
        source=bars()
        changed=[dict(row) for row in source]
        changed[3]["time_ms"]+=1
        with self.assertRaisesRegex(ValueError,"DDDS_PYTHON_INPUT_OHLCV_MISMATCH"):
            compare_same_market_bars(source,child(changed))

    def test_missing_close_series_is_caught(self):
        source=bars()
        proof=child(source)
        proof["market_input_close"]=None
        with self.assertRaisesRegex(ValueError,"DDDS_PYTHON_INPUT_CLOSE_SERIES_MISSING"):
            compare_same_market_bars(source,proof)

    def test_close_series_mismatch_despite_matching_digest_is_caught(self):
        source=bars()
        proof=child(source)
        proof["market_input_close"][20]+=1.0
        with self.assertRaisesRegex(ValueError,"DDDS_PYTHON_INPUT_CLOSE_SERIES_MISMATCH"):
            compare_same_market_bars(source,proof)

    def test_wrong_count_is_caught(self):
        source=bars()
        proof=child(source)
        proof["bars_executed"]-=1
        with self.assertRaisesRegex(ValueError,"DDDS_MARKET_BAR_COUNT_MISMATCH"):
            compare_same_market_bars(source,proof)

if __name__=="__main__":
    unittest.main()
