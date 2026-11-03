"""Real PyneCore bar-by-bar numerical comparison for an *isolated* worker.

Never call this from the public editor/API process: generated Python is executable
code. The worker must run without broker credentials or network access.
No handwritten SMA/RSI fallback, fake reference bars, or automatic PAPER approval.
"""
import csv
import hashlib
import io
import math
import os
from datetime import datetime
from pathlib import Path

MAX_CSV_BYTES = 1_000_000
MAX_BARS = 5_000
REQUIRED = ("time", "open", "high", "low", "close", "volume")


class ParityInputError(ValueError):
    pass


def _timestamp_ms(value):
    s = str(value or "").strip()
    if s.isdigit() and len(s) == 13:
        return int(s)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise ParityInputError("TIMESTAMP_MUST_BE_ISO8601_WITH_TIMEZONE_OR_EPOCH_MS") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ParityInputError("TIMESTAMP_TIMEZONE_REQUIRED")
    return int(round(dt.timestamp() * 1000))


def _number(value, field):
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ParityInputError("INVALID_NUMERIC_FIELD:" + field) from None
    if not math.isfinite(number):
        raise ParityInputError("NONFINITE_NUMERIC_FIELD:" + field)
    return number


def read_reference(csv_text):
    """Require TV-exported (or explicitly labeled test) OHLCV plus plot columns."""
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise ParityInputError("REFERENCE_CSV_REQUIRED")
    if len(csv_text.encode("utf-8")) > MAX_CSV_BYTES:
        raise ParityInputError("REFERENCE_CSV_TOO_LARGE")
    reader = csv.DictReader(io.StringIO(csv_text))
    fields = reader.fieldnames or []
    if len(fields) != len(set(fields)) or any(key not in fields for key in REQUIRED):
        raise ParityInputError("REFERENCE_NEEDS_TIME_OHLCV_UNIQUE_HEADERS")
    rows = []
    previous = None
    for row in reader:
        if len(rows) >= MAX_BARS:
            raise ParityInputError("MAX_BARS_EXCEEDED")
        timestamp = _timestamp_ms(row["time"])
        if previous is not None and timestamp <= previous:
            raise ParityInputError("TIMESTAMPS_NOT_STRICTLY_INCREASING")
        previous = timestamp
        nums = {k: _number(row[k], k) for k in REQUIRED[1:]}
        if not (nums["low"] <= min(nums["open"], nums["close"]) <=
                max(nums["open"], nums["close"]) <= nums["high"]):
            raise ParityInputError("INVALID_OHLC")
        rows.append({"timestamp": timestamp, **nums, "raw": row})
    if len(rows) < 12:
        raise ParityInputError("MINIMUM_12_BARS")
    return rows, fields


def _float_or_na(value):
    if value is None or str(value).strip().lower() in ("", "nan", "na", "none"):
        return None
    try:
        x = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ParityInputError("NONNUMERIC_PLOT_VALUE") from None
    return x if math.isfinite(x) else None


def compare_plot_values(bars, actual, mapping, *, abs_tol=1e-6, rel_tol=1e-6):
    """Compare only explicitly mapped numeric plots, aligned to identical bars."""
    if not isinstance(mapping, dict) or not mapping:
        raise ParityInputError("TV_PLOT_COLUMN_MAPPING_REQUIRED")
    if len(actual) != len(bars):
        raise ParityInputError("PYNECORE_BAR_COUNT_MISMATCH")
    comparison = []
    for plot_name, reference_name in mapping.items():
        if not isinstance(plot_name, str) or not plot_name.strip() or not isinstance(reference_name, str):
            raise ParityInputError("INVALID_PLOT_MAPPING")
        if reference_name not in bars[0]["raw"]:
            raise ParityInputError("REFERENCE_PLOT_COLUMN_MISSING:" + reference_name)
        mismatches = []
        compared = 0
        for i, (bar, plots) in enumerate(zip(bars, actual)):
            if plot_name not in plots:
                raise ParityInputError("PYNECORE_PLOT_MISSING:" + plot_name)
            target = _float_or_na(bar["raw"][reference_name])
            obtained = _float_or_na(plots[plot_name])
            if target is not None and obtained is not None:
                compared += 1
            if target is None and obtained is None:
                continue
            if target is None or obtained is None or not math.isclose(target, obtained, abs_tol=abs_tol, rel_tol=rel_tol):
                mismatches.append({"bar_index": i, "time_ms": bar["timestamp"],
                                   "tradingview": target, "pynecore": obtained})
        comparison.append({"plot": plot_name, "reference_column": reference_name,
                           "bars_compared": compared,
                           "mismatch_count": len(mismatches),
                           "first_mismatches": mismatches[:12],
                           "match": compared > 0 and not mismatches})
    return comparison


def run_compiled_pynecore(script_path, expected_python_sha256, csv_text, syminfo_values,
                          plot_mapping, *, inputs=None):
    """Execute a pinned PyneCore file only inside a dedicated, offline worker.

    No request may supply script code to the editor as executable source.
    SymInfo (including session, period and fees encoded in the script) must
    describe the exact TradingView chart; defaults are not invented here.
    """
    if os.getenv("INVESTMENT_ISOLATED_PYNECORE_WORKER") != "1":
        raise ParityInputError("ISOLATED_PYNECORE_WORKER_REQUIRED")
    path = Path(script_path).resolve(strict=True)
    root = os.getenv("INVESTMENT_PYNECORE_ARTIFACT_ROOT")
    if not root or not path.is_relative_to(Path(root).resolve(strict=True)):
        raise ParityInputError("COMPILED_ARTIFACT_OUTSIDE_WORKER_ROOT")
    if path.suffix != ".py" or path.is_symlink():
        raise ParityInputError("COMPILED_PYTHON_FILE_REQUIRED")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_python_sha256:
        raise ParityInputError("COMPILED_PYTHON_HASH_MISMATCH")
    rows, _ = read_reference(csv_text)
    if not isinstance(syminfo_values, dict):
        raise ParityInputError("EXPLICIT_SYMBOL_METADATA_REQUIRED")
    required_sym = ("prefix", "ticker", "currency", "period", "type",
                    "mintick", "pricescale", "minmove", "pointvalue", "mincontract", "timezone",
                    "volumetype", "opening_hours", "session_starts", "session_ends")
    if any(x not in syminfo_values for x in required_sym):
        raise ParityInputError("EXPLICIT_SYMBOL_METADATA_REQUIRED")
    # All imports occur only after the isolation, hash and input checks.
    from pynecore.core.script_runner import ScriptRunner
    from pynecore.core.syminfo import SymInfo
    from pynecore.types.ohlcv import OHLCV

    candles = [OHLCV(timestamp=r["timestamp"], open=r["open"], high=r["high"],
                     low=r["low"], close=r["close"], volume=r["volume"]) for r in rows]
    meta = SymInfo(**syminfo_values)
    runner = ScriptRunner(script_path=path, ohlcv_iter=candles, syminfo=meta, inputs=inputs)
    plots = []
    closed_trades = 0
    executed_trades = []
    for record in runner.run_iter():
        if len(record) not in (2, 3):
            raise ParityInputError("UNEXPECTED_PYNECORE_RUNNER_OUTPUT")
        plots.append(dict(record[1]))
        if len(record) == 3:
            closed_trades += len(record[2])
            for trade in record[2]:
                # Genuine PyneCore broker events, not a copy of TV CSV.
                # Trade timestamps and bar indexes come from ScriptRunner.
                try:
                    direction = "LONG" if trade.size > 0 else "SHORT"
                    event = {
                        "direction": direction,
                        "size": float(trade.size),
                        "entry_price": float(trade.entry_price),
                        "exit_price": float(trade.exit_price),
                        "entry_time_ms": int(trade.entry_time),
                        "exit_time_ms": int(trade.exit_time),
                        "entry_bar_index": int(trade.entry_bar_index),
                        "exit_bar_index": int(trade.exit_bar_index),
                        "profit": _float_or_na(trade.profit),
                        "cum_profit": _float_or_na(trade.cum_profit),
                        "source": "ACTUAL_PYNECORE_SCRIPT_RUNNER_CLOSED_TRADE"
                    }
                except (TypeError,ValueError,AttributeError) as exc:
                    raise ParityInputError("PYNECORE_BROKER_TRADE_NORMALIZATION_FAILED") from exc
                if (event["entry_time_ms"]<=0 or event["exit_time_ms"]<event["entry_time_ms"] or
                    event["entry_price"]<=0 or event["exit_price"]<=0):
                    raise ParityInputError("PYNECORE_BROKER_TRADE_INVALID_PRICE_OR_TIME")
                executed_trades.append(event)
            if len(executed_trades)>10000:
                raise ParityInputError("PYNECORE_TOO_MANY_CLOSED_TRADES")

    if not isinstance(plot_mapping, dict):
        raise ParityInputError("EXPLICIT_PLOT_MAPPING_REQUIRED")
    result = compare_plot_values(rows, plots, plot_mapping) if plot_mapping else []
    matches = bool(result) and all(x["match"] for x in result)
    status = ("NO_TV_PLOT_REFERENCE_TRADE_PARITY_UNVERIFIED" if not result
              else "NUMERIC_MATCH_TRADE_PARITY_UNVERIFIED" if matches else "NUMERIC_MISMATCH")
    return {
        "status": status,
        "data_type": "TV_REFERENCE_PROVIDED_BY_CALLER_NOT_AUTHENTICATED",
        "python_sha256": digest,
        "bar_count": len(rows),
        "closed_trades_not_yet_compared": closed_trades,
        "closed_trades": executed_trades,
        "trade_events_source": "ACTUAL_PYNECORE_SCRIPT_RUNNER",
        "trade_order_parity_verified": False,
        "comparison": result,
        "numeric_plot_match": matches,
        "tradingview_chart_validated": False,
        "conversion_validated": False,
        "paper_enabled": False,
        "live_orders_enabled": False,
        "series": [{"time_ms": bar["timestamp"], "close": bar["close"],
                    "plots": {k: _float_or_na(v) for k, v in data.items()
                              if k in plot_mapping}} for bar, data in zip(rows, plots)],
    }
