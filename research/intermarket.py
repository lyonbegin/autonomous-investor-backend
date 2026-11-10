"""Independent 2-leg futures spread research; NOT Pine conversion or CME signal."""
from __future__ import annotations
import csv
import hashlib
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PL_OZ = 50
GC_OZ = 100
PL_CONTRACTS = 2
GC_CONTRACTS = -1


def cme_trade_pnl(pl_entry: float, pl_exit: float, gc_entry: float, gc_exit: float,
                  commission_usd: float = 0.0) -> dict[str, float]:
    """Reproduce CME's illustrative trade calculation, not a backtest."""
    pl_pnl = PL_CONTRACTS * PL_OZ * (pl_exit - pl_entry)
    gc_pnl = GC_CONTRACTS * GC_OZ * (gc_exit - gc_entry)
    return {"pl_pnl_usd": round(pl_pnl, 2), "gc_pnl_usd": round(gc_pnl, 2),
            "gross_pnl_usd": round(pl_pnl + gc_pnl, 2),
            "net_pnl_usd": round(pl_pnl + gc_pnl - commission_usd, 2)}


def read_verified_csv(path: Path, expected_sha256: str) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256.lower():
        raise ValueError(f"Market data SHA-256 mismatch: actual={actual}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "pl_open", "pl_close", "gc_open", "gc_close"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Required CSV columns: {sorted(required)}")
        bars: list[dict[str, Any]] = []
        prev = ""
        for row in reader:
            stamp = row["timestamp"]
            if not stamp or stamp <= prev:
                raise ValueError("Duplicate, out-of-order or missing timestamp")
            prev = stamp
            bar: dict[str, Any] = {"timestamp": stamp}
            for field in required - {"timestamp"}:
                value = float(row[field])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(f"Invalid {field} at {stamp}")
                bar[field] = value
            bars.append(bar)
    if not bars:
        raise ValueError("Market data is empty")
    return bars


@dataclass(frozen=True)
class Parameters:
    lookback: int = 20
    entry_z: float = 2.0
    exit_z: float = 0.0
    commission_usd_per_contract: float = 0.0
    slippage_usd_per_oz: float = 0.0

    def __post_init__(self) -> None:
        if (self.lookback < 3 or self.entry_z <= 0 or self.exit_z < 0 or
                self.exit_z >= self.entry_z):
            raise ValueError("Invalid rolling z-score parameters")
        if self.commission_usd_per_contract < 0 or self.slippage_usd_per_oz < 0:
            raise ValueError("Negative costs not allowed")


def backtest(bars: list[dict[str, Any]], cfg: Parameters = Parameters()) -> dict[str, Any]:
    """Completed-close signal; execute at next bar open. No margin/partial-fill model.

    Spread = platinum minus gold per oz. Position = 2 PL and -1 GC contracts.
    All z-score windows use only PRIOR completed bars, never the current value.
    """
    if len(bars) < cfg.lookback + 2:
        raise ValueError("Not enough synchronized bars")
    for i, bar in enumerate(bars):
        if i and bar["timestamp"] <= bars[i - 1]["timestamp"]:
            raise ValueError("Non-monotonic timestamps")
        for field in ("pl_open", "pl_close", "gc_open", "gc_close"):
            if not math.isfinite(bar[field]) or bar[field] <= 0:
                raise ValueError(f"Invalid {field} at {i}")
    cash = 0.0
    position = 0
    pending: int | None = None
    ledger: list[dict[str, Any]] = []
    candles: list[dict[str, Any]] = []
    spreads = [float(b["pl_close"] - b["gc_close"]) for b in bars]

    def execute(target: int, pl_price: float, gc_price: float,
                when: str, reason: str) -> None:
        nonlocal cash, position
        delta = target - position
        if delta == 0:
            return
        pl_qty, gc_qty = PL_CONTRACTS * delta, GC_CONTRACTS * delta
        pl_fill = pl_price + (1 if pl_qty > 0 else -1) * cfg.slippage_usd_per_oz
        gc_fill = gc_price + (1 if gc_qty > 0 else -1) * cfg.slippage_usd_per_oz
        fees = (abs(pl_qty) + abs(gc_qty)) * cfg.commission_usd_per_contract
        cash -= pl_qty * PL_OZ * pl_fill + gc_qty * GC_OZ * gc_fill + fees
        ledger.append({"timestamp": when, "from": position, "to": target,
                       "pl_contract_delta": pl_qty, "gc_contract_delta": gc_qty,
                       "pl_fill": round(pl_fill, 6), "gc_fill": round(gc_fill, 6),
                       "fees_usd": round(fees, 4), "reason": reason})
        position = target

    for i, b in enumerate(bars):
        if pending is not None:
            execute(pending, b["pl_open"], b["gc_open"], b["timestamp"],
                    "prior_close_signal")
            pending = None
        z = None
        if i >= cfg.lookback:
            prior = spreads[i-cfg.lookback:i]
            stdev = statistics.pstdev(prior)
            if stdev > 1e-12:
                z = (spreads[i] - statistics.mean(prior)) / stdev
                if position == 0:
                    if z <= -cfg.entry_z:
                        pending = 1
                    elif z >= cfg.entry_z:
                        pending = -1
                elif position == 1 and z >= -cfg.exit_z:
                    pending = 0
                elif position == -1 and z <= cfg.exit_z:
                    pending = 0
        mark = PL_CONTRACTS * PL_OZ * b["pl_close"] + GC_CONTRACTS * GC_OZ * b["gc_close"]
        candles.append({"timestamp": b["timestamp"], "pl_close": b["pl_close"],
                        "gc_close": b["gc_close"], "spread_close": spreads[i],
                        "zscore": None if z is None else round(z, 8),
                        "spread_position": position,
                        "equity_usd": round(cash + position * mark, 4)})
    if position:
        last = bars[-1]
        execute(0, last["pl_close"], last["gc_close"],
                last["timestamp"], "assumed_terminal_liquidation")
        candles[-1]["spread_position"] = 0
        candles[-1]["equity_usd"] = round(cash, 4)
    return {"status": "FUNCTIONAL_BACKTEST_NOT_EXECUTION_VERIFIED",
            "rule_origin": "DEVELOPMENT_ASSUMPTION_NOT_CME_OR_PINE",
            "net_pnl_usd": round(cash, 4),
            "trades": ledger, "chart_series": candles,
            "execution_assumptions": [
                "signal at completed close; fill at next bar open",
                "simultaneous leg fills assumed; no partial-fill or margin simulation",
                "last-close terminal liquidation assumed"]}
