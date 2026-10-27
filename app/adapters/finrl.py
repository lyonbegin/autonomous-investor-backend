from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.contracts import TargetPortfolio, TargetWeight


@dataclass(slots=True)
class FinRLRun:
    target: TargetPortfolio
    native_result: Any


class FinRLAdapter:
    """Wraps FinRL-Trading's BaseStrategy -> StrategyResult(weights) boundary."""

    DEFAULT_INSTRUMENT_COLUMNS = ("instrument", "symbol", "ticker", "gvkey")

    @classmethod
    def run(
        cls,
        strategy: Any,
        data: dict[str, Any],
        *,
        target_date: str | None = None,
        as_of: datetime | None = None,
        instrument_column: str | None = None,
        weight_column: str = "weight",
    ) -> FinRLRun:
        result = strategy.generate_weights(data, target_date)
        target = cls.to_target_portfolio(
            result,
            as_of=as_of,
            instrument_column=instrument_column,
            weight_column=weight_column,
        )
        return FinRLRun(target=target, native_result=result)

    @classmethod
    def to_target_portfolio(
        cls,
        result: Any,
        *,
        as_of: datetime | None = None,
        instrument_column: str | None = None,
        weight_column: str = "weight",
    ) -> TargetPortfolio:
        frame = result.weights
        if weight_column not in frame.columns:
            raise ValueError(f"weight column {weight_column!r} not found")

        if instrument_column is None:
            candidates = [c for c in cls.DEFAULT_INSTRUMENT_COLUMNS if c in frame.columns]
            if len(candidates) != 1:
                raise ValueError(
                    "instrument_column must be supplied unless exactly one known "
                    f"instrument column exists; found {candidates}"
                )
            instrument_column = candidates[0]

        if instrument_column not in frame.columns:
            raise ValueError(f"instrument column {instrument_column!r} not found")

        timestamp = as_of or datetime.now(UTC)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        weights = [
            TargetWeight(instrument=str(row[instrument_column]), weight=float(row[weight_column]))
            for _, row in frame.iterrows()
        ]
        return TargetPortfolio(
            strategy_id=str(result.strategy_name),
            as_of=timestamp,
            weights=weights,
            metadata=dict(getattr(result, "metadata", {}) or {}),
        )
