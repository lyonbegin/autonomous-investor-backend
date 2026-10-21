from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from app.core.contracts import TargetPortfolio, TargetWeight


def _timestamp(as_of: datetime | None) -> datetime:
    ts = as_of or datetime.now(UTC)
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


class PortfolioAdapter:
    """Converts native optimizer weight outputs into TargetPortfolio only."""

    @staticmethod
    def from_riskfolio(
        weights: Any,
        *,
        strategy_id: str,
        as_of: datetime | None = None,
        weight_column: str | None = None,
    ) -> TargetPortfolio:
        if getattr(weights, "shape", (0, 0))[1] != 1 and weight_column is None:
            raise ValueError("Riskfolio weights must have one column or weight_column must be supplied")
        column = weight_column or weights.columns[0]
        items = [
            TargetWeight(instrument=str(index), weight=float(value))
            for index, value in weights[column].items()
        ]
        return TargetPortfolio(
            strategy_id=strategy_id,
            as_of=_timestamp(as_of),
            weights=items,
            metadata={"source": "Riskfolio-Lib"},
        )

    @staticmethod
    def from_pyportfolioopt(
        weights: Mapping[str, float],
        *,
        strategy_id: str,
        as_of: datetime | None = None,
    ) -> TargetPortfolio:
        return TargetPortfolio(
            strategy_id=strategy_id,
            as_of=_timestamp(as_of),
            weights=[
                TargetWeight(instrument=str(instrument), weight=float(weight))
                for instrument, weight in weights.items()
            ],
            metadata={"source": "PyPortfolioOpt"},
        )
