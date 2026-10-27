"""Bridge to Riskfolio-Lib's native Portfolio optimizer."""

from __future__ import annotations

from typing import Any


class RiskfolioBridge:
    @staticmethod
    def portfolio(returns: Any, **kwargs: Any) -> Any:
        import riskfolio as rp

        return rp.Portfolio(returns=returns, **kwargs)

    @staticmethod
    def estimate(portfolio: Any, **kwargs: Any) -> Any:
        return portfolio.assets_stats(**kwargs)

    @staticmethod
    def optimize(portfolio: Any, **kwargs: Any) -> Any:
        return portfolio.optimization(**kwargs)
