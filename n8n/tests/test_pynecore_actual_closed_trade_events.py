"""Actual PyneCore trade-event bridge regression. Test uses real PyneSys
published SMA sample on explicitly synthetic prices, NOT the DDDS strategy
and not TradingView reference. It validates genuine ScriptRunner events.
"""
import csv
import hashlib
import io
import os
from pathlib import Path
import sys
import unittest
import math
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"pine-parity"))
from pynecore_bridge import run_compiled_pynecore

SAMPLE=Path(__file__).resolve().parents[1]/"pine-parity"/"demo"/"sma_crossover.py"
SYMBOL={
 "prefix":"NASDAQ","ticker":"AAPL","description":"synthetic CI AAPL-like bars, not actual Nasdaq",
 "currency":"USD","basecurrency":"USD","period":"D","type":"stock",
 "mintick":0.01,"pricescale":100,"minmove":1,"pointvalue":1.,
 "mincontract":1.,"timezone":"America/New_York","volumetype":"base",
 "opening_hours":[],"session_starts":[],"session_ends":[]
}


def synthetic_market():
    buffer=io.StringIO()
    writer=csv.DictWriter(buffer,fieldnames=["time","open","high","low","close","volume"])
    writer.writeheader()
    for n in range(350):
        close=170+0.2*n+18*math.sin(n*0.18)
        writer.writerow({
          "time":(datetime(2025,1,1,tzinfo=timezone.utc)+
                  timedelta(days=n)).isoformat(),
          "open":close-.5,"high":close+1,"low":close-1,"close":close,
          "volume":1000+n})
    return buffer.getvalue()


class GenuinePyneCoreBrokerEvents(unittest.TestCase):
    def test_sample_strategy_uses_real_runner_and_emits_actual_closed_trades(self):
        sha=hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
        with patch.dict(os.environ,{
            "INVESTMENT_ISOLATED_PYNECORE_WORKER":"1",
            "INVESTMENT_PYNECORE_ARTIFACT_ROOT":str(SAMPLE.parent)
        }):
            result=run_compiled_pynecore(SAMPLE,sha,synthetic_market(),
                                          SYMBOL,{})
        self.assertEqual(result["status"],"NO_TV_PLOT_REFERENCE_TRADE_PARITY_UNVERIFIED")
        self.assertFalse(result["numeric_plot_match"])
        self.assertEqual(result["trade_events_source"],"ACTUAL_PYNECORE_SCRIPT_RUNNER")
        self.assertGreater(len(result["closed_trades"]),0)
        self.assertEqual(result["closed_trades_not_yet_compared"],
                         len(result["closed_trades"]))
        trade=result["closed_trades"][0]
        self.assertEqual(trade["source"],"ACTUAL_PYNECORE_SCRIPT_RUNNER_CLOSED_TRADE")
        self.assertIn(trade["direction"],("LONG","SHORT"))
        self.assertGreater(trade["entry_price"],0)
        self.assertGreater(trade["exit_price"],0)
        self.assertGreater(trade["entry_time_ms"],0)
        self.assertGreaterEqual(trade["exit_time_ms"],trade["entry_time_ms"])
        self.assertGreaterEqual(trade["exit_bar_index"],trade["entry_bar_index"])
        self.assertFalse(result["trade_order_parity_verified"])
        self.assertFalse(result["live_orders_enabled"])

if __name__=="__main__":
    unittest.main()
