from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.contracts import EvidenceItem, ResearchBundle


@dataclass(slots=True)
class FinRobotRun:
    research: ResearchBundle
    native_result: Any


class FinRobotAdapter:
    """Uses FinRobot V2's public SDK and preserves PipelineResult unchanged."""

    def __init__(self, agent: Any | None = None, **agent_kwargs: Any) -> None:
        self.agent = agent
        self.agent_kwargs = agent_kwargs

    async def research(
        self,
        ticker: str,
        *,
        as_of: datetime | None = None,
        progress: Any = None,
    ) -> FinRobotRun:
        if self.agent is not None:
            result = await self.agent.aresearch(ticker, progress=progress)
        else:
            from finrobot import FinRobot

            async with FinRobot(**self.agent_kwargs) as agent:
                result = await agent.aresearch(ticker, progress=progress)

        return FinRobotRun(
            research=self.to_research_bundle(result, ticker=ticker, as_of=as_of),
            native_result=result,
        )

    @staticmethod
    def to_research_bundle(
        result: Any,
        *,
        ticker: str,
        as_of: datetime | None = None,
    ) -> ResearchBundle:
        as_of = as_of or datetime.now(UTC)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=UTC)

        steps: dict[str, str] = dict(getattr(result, "steps", {}) or {})
        failures = list(getattr(result, "failed_validations", []) or [])

        evidence = [
            EvidenceItem(
                source=f"FinRobot:{name}",
                as_of=as_of,
                summary=text,
                payload={"step": name},
            )
            for name, text in steps.items()
        ]

        return ResearchBundle(
            instrument=ticker,
            as_of=as_of,
            market_report=steps.get("technical_analysis"),
            news_report=steps.get("catalyst_analysis"),
            fundamentals_report=steps.get("financial_modeling") or steps.get("data_collection"),
            uncertainties=[str(item) for item in failures],
            evidence=evidence,
        )
