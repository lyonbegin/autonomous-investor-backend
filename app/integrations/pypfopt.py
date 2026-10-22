"""Bridge to PyPortfolioOpt native EfficientFrontier."""

from __future__ import annotations

from typing import Any


class PyPortfolioOptBridge:
    @staticmethod
    def efficient_frontier(expected_returns: Any, cov_matrix: Any, **kwargs: Any) -> Any:
        from pypfopt import EfficientFrontier

        return EfficientFrontier(expected_returns, cov_matrix, **kwargs)

    @staticmethod
    def min_volatility(frontier: Any) -> Any:
        return frontier.min_volatility()

    @staticmethod
    def max_sharpe(frontier: Any, risk_free_rate: float = 0.0) -> Any:
        return frontier.max_sharpe(risk_free_rate=risk_free_rate)
