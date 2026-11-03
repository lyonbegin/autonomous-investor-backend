"""Original WF-02 center: browser-origin official chart OHLCV -> genuine PyneCore.

Pinned public AAPL 1D only. Published PyneSys CC0 example code is fixed and
bundled, never arbitrary user code, and NO TradingView Strategy Tester order
data is inferred. The underlying browser observes normal chart traffic.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import sqlite3
import threading
import urllib.request

DATA_DIR = Path(os.environ.get("STUDIO_DB_PATH", "/data/studio.sqlite3")).parent
_BROWSER = "https://autonomous-investor-tradingview-browser-production.up.railway.app/v1/inspect/official-chart-wf02"
_SAMPLES = Path(__file__).resolve().parent / "pynecore_samples"
_GATE = threading.Lock()


def _finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DATA_DIR / "tv_wf02_evidence.sqlite3"), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS wf02_public_chart_checks (
        sid TEXT PRIMARY KEY, observed_at TEXT NOT NULL, result_json TEXT NOT NULL
    )""")
    return conn


def latest(sid: str) -> dict:
    with _db() as db:
        row = db.execute("SELECT result_json FROM wf02_public_chart_checks WHERE sid=?", (sid,)).fetchone()
    if row is None:
        return {"status": "NO_EXECUTION_YET", "tv_strategy_parity_verified": False}
    return json.loads(row["result_json"])


def execute(sid: str) -> dict:
    if not _GATE.acquire(blocking=False):
        raise ValueError("WF02_OFFICIAL_CHART_VERIFICATION_ALREADY_RUNNING")
    try:
        return _execute(sid)
    finally:
        _GATE.release()


def _execute(sid):
    req = urllib.request.Request(_BROWSER, data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=70) as response:
        if response.status != 200:
            raise RuntimeError("TRADINGVIEW_BROWSER_WORKER_HTTP_FAILURE")
        raw = response.read(200_000)
    provider = json.loads(raw)
    if provider.get("status") != "OFFICIAL_CHART_OHLCV_CAPTURED":
        raise ValueError("TV_BROWSER_CAPTURE_INCOMPLETE")
    if provider.get("provenance") != "TRADINGVIEW_PUBLIC_CHART_PASSIVE_WEBSOCKET":
        raise ValueError("TV_PROVENANCE_INVALID")
    if provider.get("symbol") != "NASDAQ:AAPL" or provider.get("timeframe") != "1D":
        raise ValueError("TV_INSTRUMENT_OR_PERIOD_MISMATCH")
    original_bars = provider.get("bars")
    if not isinstance(original_bars, list) or not 20 <= len(original_bars) <= 300:
        raise ValueError("TV_CHART_BARS_OUT_OF_RANGE")
    bars = []
    for x in original_bars:
        if not isinstance(x, dict):
            raise ValueError("TV_BAR_OBJECT_REQUIRED")
        ts = x.get("time_ms")
        if isinstance(ts, bool) or not isinstance(ts, int):
            raise ValueError("TV_TIMESTAMP_INVALID")
        values = {k: _finite(x.get(k)) for k in ("open", "high", "low", "close")}
        if any(v is None for v in values.values()):
            raise ValueError("TV_NONFINITE_OHLCV")
        if values["low"] > min(values["open"], values["close"]) or values["high"] < max(values["open"], values["close"]):
            raise ValueError("TV_INVALID_OHLC")
        if bars and bars[-1]["time_ms"] >= ts:
            raise ValueError("TV_BARS_NOT_CHRONOLOGICAL")
        volume = _finite(x.get("volume"))
        bars.append({"time_ms": ts, **values, "volume": volume})
    if len(bars) != provider["bar_count"]:
        raise ValueError("TV_PROVIDER_BAR_COUNT_MISMATCH")

    from pynecore.core.script_runner import ScriptRunner
    from pynecore.core.syminfo import SymInfo
    from pynecore.types.ohlcv import OHLCV
    from importlib.metadata import version as installed_version

    symbol = SymInfo(prefix="NASDAQ", ticker="AAPL", currency="USD", basecurrency="USD",
                     description="NASDAQ AAPL official public chart", period="D", type="stock",
                     mintick=0.01, pricescale=100, minmove=1, mincontract=1.0,
                     pointvalue=1.0, timezone="America/New_York", volumetype="base",
                     opening_hours=[], session_starts=[], session_ends=[])
    ohlcv = [OHLCV(timestamp=x["time_ms"], open=x["open"], high=x["high"], low=x["low"],
                  close=x["close"], volume=x["volume"] or 0) for x in bars]

    # One strategy, one chart. Do not juxtapose an unrelated Bollinger study
    # with a standalone SMA strategy. The line below is the exact SMA9 formula
    # used by the published translated strategy, calculated for drawing only.
    # Trade fills/entries come exclusively from the PyneCore broker emulator.
    strategy_path = _SAMPLES / "sma_crossover.py"
    if not strategy_path.is_file():
        raise ValueError("PINNED_PYNECORE_STRATEGY_MISSING")
    closes = [b["close"] for b in bars]
    sma9 = [None if i < 8 else sum(closes[i-8:i+1]) / 9.0
            for i in range(len(bars))]

    strategy = ScriptRunner(script_path=strategy_path, ohlcv_iter=ohlcv, syminfo=symbol)
    trade_rows = []
    executed = 0
    for record in strategy.run_iter():
        executed += 1
        if len(record) != 3:
            raise ValueError("PYNECORE_STRATEGY_TRADE_OUTPUT_MISSING")
        for trade in record[2]:
            trade_rows.append({
                "close_bar_index": executed - 1,
                "time_ms": bars[executed - 1]["time_ms"],
                "direction": "LONG" if trade.size > 0 else "SHORT",
                "size": _finite(trade.size),
                "entry_price": _finite(trade.entry_price),
                "exit_price": _finite(trade.exit_price),
                "entry_time_ms": int(trade.entry_time),
                "exit_time_ms": int(trade.exit_time),
                "entry_bar_index": int(trade.entry_bar_index),
                "exit_bar_index": int(trade.exit_bar_index),
                "profit": _finite(trade.profit),
                "cum_profit": _finite(trade.cum_profit)
            })
    if executed != len(bars):
        raise ValueError("TV_TO_PYNECORE_STRATEGY_BAR_MISMATCH")

    plotted = [
        {"time_ms": bar["time_ms"], "tv_close": bar["close"],
         "SMA9": moving_average}
        for bar, moving_average in zip(bars, sma9)
    ]
    result = {
        "status": "OFFICIAL_CHART_OHLCV_PYNECORE_EXECUTED",
        "provenance": provider["provenance"],
        "symbol": "NASDAQ:AAPL", "timeframe": "1D",
        "bars_from_official_chart": len(bars),
        "bars_executed_by_pynecore": executed,
        "closed_trades_from_pynecore": len(trade_rows),
        "pynecore_version": installed_version("pynesys-pynecore"),
        "pynecore_strategy": "PyneSys public SMA Crossover sample",
        "strategy_indicator": "Same Pine strategy's ta.sma(close, 9), for display",
        "source_hashes": {
            "sample_strategy_sha256": hashlib.sha256(strategy_path.read_bytes()).hexdigest()
        },
        "strategy_identity": "PyneSys published MovingAvg Cross PyneComp sample",
        "strategy_source_url": "https://github.com/PyneSys/pynecore-examples/blob/main/01-standalone/sma_crossover.py",
        "strategy_input_length": 9,
        "strategy_input_confirm_bars": 1,
        "strategy_display_plot": "SMA9",
        "official_tv_widget_pine_strategy_supported": False,
        "source_pine_strategy_tester_reference": False,
        "new_pynecomp_compilation": False,
        "user_selected_source_converted": False,
        "tv_strategy_tester_orders_available": False,
        "tv_strategy_parity_verified": False,
        "paper_enabled": False,
        "live_orders_enabled": False,
        "chart": plotted,
        "pynecore_trades": trade_rows[-40:],
        "browser_probe_cache_hit": bool(provider.get("cache_hit")),
        "executed_at": datetime.now(timezone.utc).isoformat()
    }
    with _db() as db:
        db.execute("""INSERT INTO wf02_public_chart_checks (sid,observed_at,result_json)
                      VALUES (?,?,?) ON CONFLICT(sid) DO UPDATE SET
                      observed_at=excluded.observed_at,result_json=excluded.result_json""",
                   (sid, result["executed_at"], json.dumps(result, ensure_ascii=False, allow_nan=False)))
    return result
