"""Bridge to vectorbt native Portfolio constructors and analytics."""

from __future__ import annotations

from typing import Any


class VectorBTBridge:
    """Delegate screening/backtest construction to vectorbt.Portfolio."""

    @staticmethod
    def from_signals(close: Any, entries: Any, exits: Any, **kwargs: Any) -> Any:
        from vectorbt.portfolio.base import Portfolio

        return Portfolio.from_signals(close, entries, exits, **kwargs)

    @staticmethod
    def from_orders(close: Any, **kwargs: Any) -> Any:
        from vectorbt.portfolio.base import Portfolio

        return Portfolio.from_orders(close, **kwargs)

    @staticmethod
    def stats(portfolio: Any, **kwargs: Any) -> Any:
        return portfolio.stats(**kwargs)
