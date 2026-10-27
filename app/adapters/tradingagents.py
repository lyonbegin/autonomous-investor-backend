from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Mapping

from app.core.contracts import EvidenceItem, ResearchBundle


@dataclass(slots=True)
class TradingAgentsRun:
    research: ResearchBundle
    native_state: Mapping[str, Any]
    native_rating: str


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class TradingAgentsAdapter:
    """Calls TradingAgentsGraph without changing TradingAgents internals."""

    def __init__(self, graph: Any) -> None:
        self.graph = graph

    def run(
        self,
        instrument: str,
        trade_date: str | date | datetime,
        *,
        asset_type: str = "stock",
        portfolio: Any = None,
    ) -> TradingAgentsRun:
        final_state, rating = self.graph.propagate(
            instrument,
            trade_date,
            asset_type=asset_type,
            portfolio=portfolio,
        )
        return TradingAgentsRun(
            research=self.to_research_bundle(final_state, rating),
            native_state=final_state,
            native_rating=rating,
        )

    @staticmethod
    def to_research_bundle(
        final_state: Mapping[str, Any],
        rating: str,
    ) -> ResearchBundle:
        debate = final_state.get("investment_debate_state") or {}
        uncertainties: list[str] = []
        if note := final_state.get("memory_note"):
            uncertainties.append(str(note))

        evidence = [
            EvidenceItem(
                source="TradingAgents",
                as_of=_as_datetime(final_state["trade_date"]),
                summary="TradingAgents final investment/risk decision",
                payload={
                    "final_rating": rating,
                    "final_trade_decision": final_state.get("final_trade_decision"),
                    "investment_plan": final_state.get("investment_plan"),
                    "trader_investment_plan": final_state.get("trader_investment_plan"),
                },
            )
        ]

        return ResearchBundle(
            instrument=str(final_state["company_of_interest"]),
            as_of=_as_datetime(final_state["trade_date"]),
            market_report=final_state.get("market_report"),
            sentiment_report=final_state.get("sentiment_report"),
            news_report=final_state.get("news_report"),
            fundamentals_report=final_state.get("fundamentals_report"),
            bull_case=[str(debate["bull_history"])] if debate.get("bull_history") else [],
            bear_case=[str(debate["bear_history"])] if debate.get("bear_history") else [],
            uncertainties=uncertainties,
            evidence=evidence,
        )
