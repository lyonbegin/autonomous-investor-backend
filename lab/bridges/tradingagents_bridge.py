"""Bridge to TradingAgents without changing its native graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TradingAgentsRun:
    final_state: dict[str, Any]
    signal: str


class TradingAgentsBridge:
    """Own one native TradingAgentsGraph and delegate runs to propagate()."""

    def __init__(
        self,
        *,
        selected_analysts: tuple[str, ...] = ("market", "social", "news", "fundamentals"),
        debug: bool = False,
        config: dict[str, Any] | None = None,
        callbacks: list[Any] | None = None,
    ) -> None:
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        self.graph = TradingAgentsGraph(
            selected_analysts=selected_analysts,
            debug=debug,
            config=config,
            callbacks=callbacks,
        )

    def run(
        self,
        instrument: str,
        trade_date: str,
        *,
        asset_type: str = "stock",
        portfolio: Any | None = None,
    ) -> TradingAgentsRun:
        final_state, signal = self.graph.propagate(
            instrument,
            trade_date,
            asset_type=asset_type,
            portfolio=portfolio,
        )
        return TradingAgentsRun(final_state=final_state, signal=signal)
