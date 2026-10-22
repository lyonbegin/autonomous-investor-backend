"""Bridge to NautilusTrader Rust/PyO3 facade."""

from __future__ import annotations

from typing import Any


class NautilusBridge:
    @staticmethod
    def risk_config(**kwargs: Any) -> Any:
        from nautilus_trader.risk import RiskEngineConfig

        return RiskEngineConfig(**kwargs)

    @staticmethod
    def execution_config(**kwargs: Any) -> Any:
        from nautilus_trader.execution import ExecutionEngineConfig

        return ExecutionEngineConfig(**kwargs)

    @staticmethod
    def backtest_engine_config(
        *,
        risk_engine: Any | None = None,
        exec_engine: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        from nautilus_trader.backtest import BacktestEngineConfig

        return BacktestEngineConfig(risk_engine=risk_engine, exec_engine=exec_engine, **kwargs)

    @staticmethod
    def market_order(
        strategy: Any,
        *,
        instrument_id: Any,
        order_side: Any,
        quantity: Any,
        **kwargs: Any,
    ) -> Any:
        return strategy.order_factory.market(
            instrument_id=instrument_id,
            order_side=order_side,
            quantity=quantity,
            **kwargs,
        )

    @staticmethod
    def submit_order(strategy: Any, order: Any, **kwargs: Any) -> None:
        strategy.submit_order(order, **kwargs)
