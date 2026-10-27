"""Bridge to vectorbt native Portfolio APIs."""

from __future__ import annotations

from typing import Any


class VectorBTBridge:
    @staticmethod
    def from_signals(close: Any, entries: Any, exits: Any, **kwargs: Any) -> Any:
        from vectorbt.portfolio.base import Portfolio

        return Portfolio.from_signals(close, entries, exits, **kwargs)

    @staticmethod
    def from_orders(close: Any, **kwargs: Any) -> Any:
        from vectorbt.portfolio.base import Portfolio

        return Portfolio.from_orders(close, **kwargs)
