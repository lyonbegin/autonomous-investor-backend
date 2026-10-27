"""Translate native allocation-engine outputs into TargetPortfolio."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from app.core.contracts import TargetPortfolio, TargetWeight


def _as_of(value: datetime | None) -> datetime:
    current = value or datetime.now(UTC)
    return current if current.tzinfo is not None else current.replace(tzinfo=UTC)


def target_portfolio_from_mapping(
    weights: Mapping[str, float],
    *,
    strategy_id: str,
    as_of: datetime | None = None,
    cash_weight: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> TargetPortfolio:
    return TargetPortfolio(
        strategy_id=strategy_id,
        as_of=_as_of(as_of),
        weights=[
            TargetWeight(instrument=str(instrument), weight=float(weight))
            for instrument, weight in weights.items()
        ],
        cash_weight=float(cash_weight),
        metadata=metadata or {},
    )


def target_portfolio_from_finrl(
    result: Any,
    *,
    as_of: datetime | None = None,
    instrument_column: str = "gvkey",
    weight_column: str = "weight",
    cash_weight: float = 0.0,
) -> TargetPortfolio:
    """Map FinRL-Trading StrategyResult(weights: DataFrame) exactly at its native boundary."""

    frame = result.weights
    missing = {instrument_column, weight_column} - set(frame.columns)
    if missing:
        raise ValueError(f"FinRL StrategyResult weights missing columns: {sorted(missing)}")

    weights = {
        str(row[instrument_column]): float(row[weight_column])
        for _, row in frame.iterrows()
    }
    return target_portfolio_from_mapping(
        weights,
        strategy_id=str(result.strategy_name),
        as_of=as_of,
        cash_weight=cash_weight,
        metadata={"source": "FinRL-Trading", **dict(result.metadata or {})},
    )


def target_portfolio_from_riskfolio(
    weights: Any,
    *,
    strategy_id: str,
    as_of: datetime | None = None,
    cash_weight: float = 0.0,
) -> TargetPortfolio:
    """Map Riskfolio's optimization DataFrame (index assets, column weights)."""

    if hasattr(weights, "columns") and "weights" in weights.columns:
        mapping = {str(idx): float(val) for idx, val in weights["weights"].items()}
    elif isinstance(weights, Mapping):
        mapping = {str(k): float(v) for k, v in weights.items()}
    else:
        raise TypeError("Riskfolio output must be a DataFrame with 'weights' or a mapping")

    return target_portfolio_from_mapping(
        mapping,
        strategy_id=strategy_id,
        as_of=as_of,
        cash_weight=cash_weight,
        metadata={"source": "Riskfolio-Lib"},
    )
