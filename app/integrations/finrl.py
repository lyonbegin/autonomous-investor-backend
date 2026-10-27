"""Bridge to FinRL-Trading native StrategyResult weight contract."""

from __future__ import annotations

from typing import Any


class FinRLBridge:
    @staticmethod
    def generate_weights(
        strategy: Any,
        data: dict[str, Any],
        *,
        target_date: str | None = None,
    ) -> Any:
        return strategy.generate_weights(data, target_date=target_date)

    @staticmethod
    def equal_weight(name: str = "equal_weight") -> Any:
        from strategies.base_strategy import EqualWeightStrategy, StrategyConfig

        return EqualWeightStrategy(StrategyConfig(name=name))
