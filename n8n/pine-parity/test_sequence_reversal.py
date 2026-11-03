"""Deterministic tests for a *restricted* RSI reversal-run Pine compiler.

Test candles are synthetic; no TradingView parity is implied.
"""
import unittest
from sequence_reversal import (parse_sequence_pine,generate_sequence_python,
                               _rsi_wilder,UnsupportedSequencePine)
PINE='''//@version=6
strategy("RSI reversal signals", overlay=true)
runLength = input.int(2, "run length", options=[2,3,4,5])
tolerancePct = input.float(0.05, "wobble")
useRsiFilter = input.bool(false, "RSI")
rsiLen = input.int(3, "length")
rsiMinLong = input.int(40, "long")
rsiMaxShort = input.int(60, "short")
takeProfitR = input.string("1.5R", "reward")
enableLongTrades = input.bool(true, "long")
enableShortTrades = input.bool(false, "short")
rrMultiple = switch takeProfitR
    "0.5R" => 0.5
    "1R"   => 1.0
    "1.5R" => 1.5
    "2R"   => 2.0
    => 1.5
rsiVal = ta.rsi(close, rsiLen)
rsiRising = rsiVal > rsiVal[1]
rsiFalling = rsiVal < rsiVal[1]
rsiOkLong = not useRsiFilter or (rsiVal > rsiMinLong and rsiRising)
rsiOkShort = not useRsiFilter or (rsiVal < rsiMaxShort and rsiFalling)
reversalWasDown = close[runLength] < open[runLength]
reversalWasUp = close[runLength] > open[runLength]
bool runIsBullish = true
for i = 0 to runLength - 1
    if close[i] <= open[i]
        runIsBullish := false
    if low[i] <= low[runLength]
        runIsBullish := false
    if i < runLength - 1
        floorClose = close[i + 1] * (1 - tolerancePct / 100)
        if close[i] <= floorClose
            runIsBullish := false
bool runIsBearish = true
for i = 0 to runLength - 1
    if close[i] >= open[i]
        runIsBearish := false
    if high[i] >= high[runLength]
        runIsBearish := false
    if i < runLength - 1
        ceilClose = close[i + 1] * (1 + tolerancePct / 100)
        if close[i] >= ceilClose
            runIsBearish := false
longSetup = reversalWasDown and runIsBullish and rsiOkLong
shortSetup = reversalWasUp and runIsBearish and rsiOkShort
if enableLongTrades and longSetup and strategy.position_size == 0
    stopLossPrice := low[runLength]
    riskPts = close - stopLossPrice
    takeProfitPrice := close + riskPts * rrMultiple
    strategy.entry("Long", strategy.long)
if enableShortTrades and shortSetup and strategy.position_size == 0
    stopLossPrice := high[runLength]
    riskPts = stopLossPrice - close
    takeProfitPrice := close - riskPts * rrMultiple
    strategy.entry("Short", strategy.short)
strategy.exit("Long Exit", from_entry = "Long", stop = stopLossPrice, limit = takeProfitPrice)
strategy.exit("Short Exit", from_entry = "Short", stop = stopLossPrice, limit = takeProfitPrice)
'''
def bar(i,o,c,l=None,h=None):
    return {"time":f"t{i}","open":float(o),"close":float(c),
            "low":float(min(o,c)-2 if l is None else l),
            "high":float(max(o,c)+2 if h is None else h)}
def fixture():
    bars=[bar(i,100,100) for i in range(4)]
    bars.extend([bar(4,110,100,95,112),bar(5,100,107,97,109),
                 bar(6,107,115,98,117),bar(7,116,118,112,121),
                 bar(8,118,130,117,151)])
    return bars

class RSISequenceConversion(unittest.TestCase):
    def test_source_to_python_signals_and_stop_target(self):
        spec=parse_sequence_pine(PINE)
        self.assertEqual(spec["inputs"]["reward_multiple"],1.5)
        code=generate_sequence_python(spec)
        self.assertNotIn("strategy.entry(",code)
        namespace={}
        exec(compile(code,"<trusted generated strategy>","exec"),namespace)
        output=namespace["run_strategy"](fixture())
        self.assertTrue(output["signals"]["longSetup"][6])
        self.assertEqual(output["signals"]["shortSetup"][6],False)
        self.assertEqual(output["orders"][0]["stop"],95)
        self.assertEqual(output["orders"][0]["target"],145)
        self.assertEqual(output["trades"][0]["time"],"t7")
        self.assertEqual(output["trades"][0]["fill_price"],116)
        self.assertEqual(output["exits"][0]["time"],"t8")
        self.assertEqual(output["exits"][0]["reason"],"TARGET")
        self.assertEqual(output["status"],"SIGNALS_EXECUTED_NO_TV_PARITY")

    def test_changed_entry_or_loop_requires_new_converter(self):
        for changed in (PINE.replace("low[i] <= low[runLength]","low[i] < low[runLength]"),
                        PINE.replace("takeProfitPrice := close + riskPts * rrMultiple",
                                     "takeProfitPrice := close + riskPts * 4"),
                        PINE+"\nstrategy.cancel(\"Long\")"):
            with self.assertRaises(UnsupportedSequencePine):
                parse_sequence_pine(changed)

    def test_rsi_wilder_warmup_and_zero_loss(self):
        series=_rsi_wilder([float(x) for x in range(1,26)],14)
        self.assertIsNone(series[13])
        self.assertEqual(series[14],100.0)
        self.assertEqual(series[-1],100.0)

    def test_chart_renders_signal_without_inventing_tradingview_baseline(self):
        from engine import analyze
        rows=["time,open,high,low,close"]
        extended=fixture()+[bar(i,100,100) for i in range(9,16)]
        for i,b in enumerate(extended):
            rows.append(f"{b['time']},{b['open']},{b['high']},{b['low']},{b['close']}")
        report=analyze(PINE,"\n".join(rows)+"\n",{},"Synthetic candle check")
        self.assertEqual(report["status"],"REFERENCE_COLUMNS_REQUIRED")
        self.assertEqual(report["source"],"PYTHON_RSI_REVERSAL_RUN_RESTRICTED")
        self.assertFalse(report["numeric_match"])
        self.assertEqual(report["trade_count"],1)
        self.assertTrue(report["svg"].startswith("<svg"))
        self.assertIn("def run_strategy(bars):",report["python_code"])
        self.assertIn("NOT_TV_PARITY",report["execution_model"])

    def test_reject_malformed_market_data(self):
        namespace={}
        exec(generate_sequence_python(parse_sequence_pine(PINE)),namespace)
        with self.assertRaisesRegex(ValueError,"BAD_OHLC"):
            namespace["run_strategy"]([{"time":"t","open":10,"high":3,"low":9,"close":8}])

if __name__=="__main__":
    unittest.main()
