"""Read-only, genuine PyneComp-published PyneCore execution on actual market OHLCV.

Public samples are CC0 upstream PyneSys/pynecore-examples:
https://github.com/PyneSys/pynecore-examples/tree/main/01-standalone

This verifies runtime integration and trade-list generation, NOT a fresh API
conversion and NOT a TradingView reference comparison. No synthetic data, no
arbitrary Python upload, no broker actions, no backtest-result approval.
"""
import csv
import hashlib
import math
import threading
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent / "demo"
_REQUIRED = ("bollinger_bands.py", "sma_crossover.py", "EURUSD_1h.csv")
_LOCK = threading.Lock()


def _numeric(value):
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _files():
    for name in _REQUIRED:
        path = DATA / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size < 100:
            raise RuntimeError("PINNED_DEMO_SOURCE_MISSING:" + name)
    return {name: hashlib.sha256((DATA / name).read_bytes()).hexdigest() for name in _REQUIRED}


def execute_demo(*, export_all=False):
    """Compute both indicator plots and real strategy closed trades every call."""
    if not _LOCK.acquire(blocking=False):
        raise RuntimeError("DEMO_EXECUTION_ALREADY_IN_PROGRESS")
    try:
        hashes = _files()
        # Import only these pinned, bundled dependencies; never execute
        # user-supplied or remotely downloaded Python in the public server.
        from pynecore.core.script_runner import ScriptRunner
        from pynecore.core.syminfo import SymInfo
        from pynecore.types.ohlcv import OHLCV
        from importlib.metadata import version as package_version

        market = []
        feed = []
        with (DATA / "EURUSD_1h.csv").open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                timestamp = datetime.fromisoformat(row["time"])
                if timestamp.tzinfo is None:
                    raise RuntimeError("SAMPLE_MARKET_TIMEZONE_MISSING")
                values = {k: float(row[k]) for k in ("open", "high", "low", "close")}
                volume = float(row["Volume"])
                ms = int(timestamp.timestamp() * 1000)
                market.append({"time_ms": ms, **values, "volume": volume})
                feed.append(OHLCV(timestamp=ms, volume=volume, **values))
        if not 900 <= len(feed) <= 2000:
            raise RuntimeError("MARKET_FEED_UNEXPECTED_COUNT")
        if any(a["time_ms"] >= b["time_ms"] for a, b in zip(market, market[1:])):
            raise RuntimeError("MARKET_BARS_NOT_CHRONOLOGICAL")

        syminfo = SymInfo(
            prefix="FX", ticker="EURUSD", description="PyneSys public EURUSD dataset",
            currency="USD", basecurrency="EUR", period="60", type="forex",
            mintick=0.00001, pricescale=100000, minmove=1, mincontract=1.0,
            pointvalue=1.0, timezone="America/New_York", volumetype="base",
            opening_hours=[], session_starts=[], session_ends=[]
        )
        indicator = ScriptRunner(
            script_path=DATA / "bollinger_bands.py", ohlcv_iter=feed, syminfo=syminfo
        )
        plots = []
        for idx, output in enumerate(indicator.run_iter()):
            if len(output) not in (2, 3):
                raise RuntimeError("INDICATOR_PYNECORE_OUTPUT_INVALID")
            plot_values = dict(output[1])
            plots.append({k: _numeric(v) for k, v in plot_values.items()
                          if k in ("Basis", "Upper", "Lower")})
        if len(plots) != len(market):
            raise RuntimeError("INDICATOR_BAR_COUNT_MISMATCH")
        if not any("Basis" in row and row["Basis"] is not None for row in plots):
            raise RuntimeError("PYNECORE_BOLLINGER_PLOT_NOT_EMITTED")

        strategy_runner = ScriptRunner(
            script_path=DATA / "sma_crossover.py", ohlcv_iter=feed, syminfo=syminfo
        )
        trades = []
        for idx, record in enumerate(strategy_runner.run_iter()):
            if len(record) != 3:
                raise RuntimeError("STRATEGY_TRADE_OUTPUT_MISSING")
            for trade in record[2]:
                row = {
                    "close_bar_index": idx,
                    "direction": "LONG" if trade.size > 0 else "SHORT",
                    "entry_price": _numeric(trade.entry_price),
                    "exit_price": _numeric(trade.exit_price),
                    "profit": _numeric(trade.profit),
                    "cum_profit": _numeric(trade.cum_profit),
                }
                trades.append(row)
        if not trades:
            raise RuntimeError("REAL_STRATEGY_EMITTED_NO_CLOSED_TRADES")
        output_rows = [
            {"time_ms": m["time_ms"], "open": m["open"],
             "high": m["high"], "low": m["low"], "close": m["close"],
             "volume": m["volume"],
             **p}
            for m, p in zip(market, plots)
        ]
        return {
            "status": "PYNECORE_REAL_MARKET_EXECUTED_TV_PARITY_PENDING",
            "live_orders_enabled": False, "paper_trading_enabled": False,
            "conversion_validated": False, "tradingview_chart_validated": False,
            "compiler_source": "PYNESYS_PUBLIC_PYNECOMP_COMPILED_EXAMPLES",
            "new_pynecomp_compilation": False,
            "market_dataset": "PyneSys CC0 EURUSD 1h historical 2022",
            "market_data_is_synthetic": False,
            "tradingview_reference_present": False,
            "provenance_url": "https://github.com/PyneSys/pynecore-examples/tree/main/01-standalone",
            "license": "CC0-1.0",
            "sha256": hashes,
            "pynecore_version": package_version("pynesys-pynecore"),
            "bar_count": len(market), "strategy_closed_trades": len(trades),
            "strategy_trades": trades[-80:],
            "time_from_ms": market[0]["time_ms"], "time_to_ms": market[-1]["time_ms"],
            "plots_calculated": len(plots),
            "chart": output_rows[-260:],
            "full_chart": output_rows if export_all else None,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "not_verified_reason": "A genuine TradingView plot/trade reference and exact chart settings were not provided."
        }
    finally:
        _LOCK.release()


if __name__ == "__main__":
    import json
    d = execute_demo()
    print(json.dumps({k: v for k, v in d.items() if k not in ("chart", "strategy_trades")}, ensure_ascii=False))
