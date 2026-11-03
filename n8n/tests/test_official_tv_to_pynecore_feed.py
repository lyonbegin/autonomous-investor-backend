"""One-off verified bridge: public TradingView chart OHLCV -> real PyneCore.

This intentionally proves *data transport and ScriptRunner execution*, not
TradingView Strategy Tester trade equivalence. The PyneCore program is a
published PyneSys example, not a compilation of a user-selected TV strategy.
"""
import csv
import json
import os
import sys
from pathlib import Path

reference=Path(os.environ["TV_OFFICIAL_TEST_CSV"])
core=Path(os.environ["TV_PYNECORE_CHECKOUT"])
sys.path.insert(0,str(core/"n8n"/"pine-parity"))
from pynecore_bridge import read_reference
from pynecore.core.script_runner import ScriptRunner
from pynecore.core.syminfo import SymInfo
from pynecore.types.ohlcv import OHLCV

raw=reference.read_text(encoding="utf-8")
bars,headers=read_reference(raw)
assert 20<=len(bars)<=500, "Unexpected chart series depth"
assert len(bars)==len({b["timestamp"] for b in bars}), "Duplicate time"
assert len(bars)==sum(1 for _ in csv.DictReader(raw.splitlines())), "CSV mismatch"
assert bars[-1]["close"] > 0

metadata=SymInfo(prefix="NASDAQ",ticker="AAPL",description="NASDAQ AAPL public TradingView chart",
 currency="USD",basecurrency="USD",period="D",type="stock",
 mintick=0.01,pricescale=100,minmove=1,mincontract=1.0,pointvalue=1.0,
 timezone="America/New_York",volumetype="base",
 opening_hours=[],session_starts=[],session_ends=[])
ohlcv=[OHLCV(timestamp=b["timestamp"],open=b["open"],high=b["high"],
 low=b["low"],close=b["close"],volume=b["volume"]) for b in bars]
sample=core/"n8n"/"pine-parity"/"demo"/"sma_crossover.py"
assert sample.is_file(), "Previously-tested published PyneCore strategy not found"
runner=ScriptRunner(script_path=sample,ohlcv_iter=ohlcv,syminfo=metadata)
executed=0
plot_bars=0
closed=0
for record in runner.run_iter():
 executed+=1
 if len(record)>1 and record[1]:
  plot_bars+=1
 if len(record)==3:closed+=len(record[2])
assert executed==len(bars), f"Bar count changed on PyneCore execution: {executed} vs {len(bars)}"

result={
 "status":"TV_OFFICIAL_OHLCV_TO_PYNECORE_RUNNER_PASSED",
 "source":"PASSIVELY_CAPTURED_PUBLIC_TRADINGVIEW_CHART",
 "symbol":"NASDAQ:AAPL","timeframe":"1D",
 "bars_loaded":len(bars),"bars_executed":executed,
 "strategy_script":"PYNESYS_PUBLISHED_SMA_CROSSOVER_EXAMPLE",
 "plots_emitted_on_bars":plot_bars,"pynecore_closed_trades":closed,
 "official_tradingview_strategy_tester_data_available":False,
 "tradingview_vs_pynecore_trade_parity_verified":False,
 "new_pynecomp_compilation_performed":False,
 "live_orders_enabled":False,
}
out=reference.parent/"official-tv-to-pynecore-proof.json"
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print("OFFICIAL_TV_TO_REAL_PYNECORE_E2E",json.dumps(result))
