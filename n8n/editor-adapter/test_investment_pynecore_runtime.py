"""Real installed PyneCore ScriptRunner smoke on non-TradingView synthetic OHLCV.

Must NEVER be reported as a true Pine->Python conversion or TV parity result.
"""
import os,sys,unittest,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from investment_pynecore_runtime import run_generated,PyneCoreRuntimeError

SIMPLE_PYNE='''"""
@pyne
"""
from pynecore.lib import script,close,plot

@script.indicator(title="Python-PyneCore runtime test")
def main():
    plot(close,"Closing Price")
'''
class PyneCoreRuntimeTests(unittest.TestCase):
    def test_reject_non_pynecode_and_invalid_prices(self):
        with self.assertRaisesRegex(PyneCoreRuntimeError,"MAGIC_HEADER"):
            run_generated("def foo():pass",[],symbol="NASDAQ:NVDA",timeframe="2h")
    @unittest.skipUnless(importlib.util.find_spec("pynecore"),"PyneCore optional in unit-only environment")
    def test_real_script_runner_with_plot_csv(self):
        rows=[{"timestamp":1704067200000+i*3600000,"open":100+i,
             "high":102+i,"low":99+i,"close":101+i,"volume":1000+i}
              for i in range(25)]
        result=run_generated(SIMPLE_PYNE,rows,symbol="NASDAQ:NVDA",timeframe="1h")
        self.assertEqual(result["status"],"PYNECORE_EXECUTED_NOT_TV_VALIDATED")
        self.assertEqual(result["bars_processed"],25)
        self.assertIn("Closing Price",result["plot_csv"])
        self.assertFalse(result["tradingview_parity_verified"])
if __name__=="__main__":unittest.main()
