"""Regression tests: supported Pine subset, exact TV-export numeric parity,
generated Python semantic equivalence and fail-closed unsupported scripts.
All fixtures here are SYNTHETIC, never claimed to come from TradingView.
"""
import io, math, unittest
from engine import parse_pine, read_csv, run_python, analyze, UnsupportedPine, generate_python

PINE="""//@version=6
strategy("MA crossover test", overlay=true)
fastLength = input.int(5, "Fast")
slowLength = input.int(12, "Slow")
fastMA = ta.sma(close, fastLength)
slowMA = ta.ema(close, slowLength)
longCondition = ta.crossover(fastMA, slowMA)
shortCondition = ta.crossunder(fastMA, slowMA)
if (longCondition)
    strategy.entry("Long", strategy.long)
if (shortCondition)
    strategy.entry("Short", strategy.short)
plot(fastMA, title="Fast")
plot(slowMA, title="Slow")
"""
COLS={"fastMA":"Fast TV","slowMA":"Slow TV",
      "longCondition":"Long Signal","shortCondition":"Short Signal"}

def synthetic_csv(reference=True,mismatch=False):
    rows=["time,open,high,low,close,volume"]
    for i in range(120):
        v=100+12*math.sin(i*.17)+6*math.sin(i*.067)+i*.04
        o=v-.6;c=v+.3;h=max(o,c)+1.3;l=min(o,c)-1.1
        rows.append(f"t{i},{o:.12f},{h:.12f},{l:.12f},{c:.12f},100")
    if not reference:return "\n".join(rows)+"\n"
    data,_=read_csv("\n".join(rows))
    spec=parse_pine(PINE)
    series,signals,_=run_python(data,spec)
    out=[rows[0]+",Fast TV,Slow TV,Long Signal,Short Signal"]
    for i,row in enumerate(rows[1:]):
        fast=series["fastMA"][i]
        if mismatch and i==62:fast+=1
        values=["" if fast is None else str(fast),str(series["slowMA"][i]),
                str(int(signals["longCondition"][i])),str(int(signals["shortCondition"][i]))]
        out.append(row+","+",".join(values))
    return "\n".join(out)+"\n"

class PineParity(unittest.TestCase):
    def test_python_generated_code_matches_engine_values(self):
        bars,_=read_csv(synthetic_csv(False))
        spec=parse_pine(PINE)
        src=generate_python(spec)
        env={}
        exec(compile(src,"<audited generated>", "exec"),env)
        generated=env["run_strategy"](bars)
        original=run_python(bars,spec)
        self.assertEqual(generated["series"],original[0])
        self.assertEqual(generated["signals"],original[1])
        self.assertGreater(len(original[2]),3)

    def test_tv_numeric_reference_match_still_requires_visual(self):
        result=analyze(PINE,synthetic_csv(),COLS)
        self.assertTrue(result["numeric_match"])
        self.assertEqual(result["status"],"NUMERIC_MATCH_VISUAL_REVIEW_REQUIRED")
        self.assertEqual(len(result["comparison"]),4)
        self.assertTrue(result["svg"].startswith("<svg"))
        self.assertEqual(result["source"],"PYTHON_STRICT_SUPPORTED_SUBSET")

    def test_mismatch_identifies_bar_and_variable(self):
        result=analyze(PINE,synthetic_csv(mismatch=True),COLS)
        self.assertFalse(result["numeric_match"])
        self.assertEqual(result["status"],"NUMERIC_MISMATCH")
        mismatches=[r for r in result["comparison"] if r["status"]=="MISMATCH"]
        self.assertEqual(len(mismatches),1)
        self.assertEqual(mismatches[0]["variable"],"fastMA")
        self.assertEqual(mismatches[0]["mismatch_bars"][0]["bar_index"],62)

    def test_legal_nonoverlay_and_multiline_strategy_header(self):
        for declaration in (
            'strategy("SMA test", overlay=false)',
            'strategy("SMA test",\n    overlay=false,\n    initial_capital=10000)'
        ):
            source=PINE.replace('strategy("MA crossover test", overlay=true)',declaration)
            spec=parse_pine(source)
            self.assertEqual(len(spec["entries"]),2)
            self.assertEqual(spec["supported_subset"],"PINE_V5_V6_CLOSE_SMA_EMA_CROSS_STRATEGY")

    def test_no_tv_indicator_reference_is_incomplete(self):
        result=analyze(PINE,synthetic_csv(reference=False),{})
        self.assertEqual(result["status"],"REFERENCE_COLUMNS_REQUIRED")
        self.assertFalse(result["numeric_match"])

    def test_refuse_unsupported_pine(self):
        self.assertRaises(UnsupportedPine,parse_pine,PINE+"\nx = request.security(syminfo.tickerid, 'D', close)")
        self.assertRaises(UnsupportedPine,parse_pine,PINE+"\nstrategy.exit('Stop', stop=100)")
        self.assertRaises(UnsupportedPine,parse_pine,PINE.replace("ta.sma","ta.rsi"))
        self.assertRaises(UnsupportedPine,parse_pine,PINE.replace("strategy(","indicator("))

    def test_strict_same_market_data_input(self):
        bad=synthetic_csv(False).replace("t4,","t3,")
        self.assertRaisesRegex(ValueError,"DUPLICATE_TIMESTAMPS",read_csv,bad)
        self.assertRaisesRegex(ValueError,"TV_CSV_REQUIRES",read_csv,"time,close\n0,10\n")

if __name__=="__main__":unittest.main()
