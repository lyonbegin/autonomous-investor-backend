"""Bridge to Qlib's native initialization and backtest APIs."""

from __future__ import annotations

from typing import Any


class QlibBridge:
    """Keep Qlib's own provider/model/strategy/executor lifecycle intact."""

    @staticmethod
    def initialize(*, default_conf: str = "client", **kwargs: Any) -> None:
        import qlib

        qlib.init(default_conf=default_conf, **kwargs)

    @staticmethod
    def backtest(
        *,
        start_time: Any,
        end_time: Any,
        strategy: Any,
        executor: Any,
        benchmark: str = "SH000300",
        account: Any = 1e9,
        exchange_kwargs: dict[str, Any] | None = None,
        pos_type: str = "Position",
    ) -> Any:
        from qlib.backtest import backtest

        return backtest(
            start_time=start_time,
            end_time=end_time,
            strategy=strategy,
            executor=executor,
            benchmark=benchmark,
            account=account,
            exchange_kwargs=exchange_kwargs or {},
            pos_type=pos_type,
        )
