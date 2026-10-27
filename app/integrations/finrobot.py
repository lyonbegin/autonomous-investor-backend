"""Bridge to FinRobot V2's public SDK."""

from __future__ import annotations

from typing import Any


class FinRobotBridge:
    def __init__(self, *, model: str | None = None, **settings: Any) -> None:
        from finrobot import FinRobot

        self.agent = FinRobot(model=model, **settings)

    async def research(self, ticker: str, *, progress: Any | None = None) -> Any:
        return await self.agent.aresearch(ticker, progress=progress)

    async def dcf(self, ticker: str, *, progress: Any | None = None) -> Any:
        return await self.agent.adcf(ticker, progress=progress)

    async def comps(self, ticker: str, *, progress: Any | None = None) -> Any:
        return await self.agent.acomps(ticker, progress=progress)

    async def earnings(self, ticker: str, *, progress: Any | None = None) -> Any:
        return await self.agent.aearnings(ticker, progress=progress)

    async def ic_memo(self, ticker: str, *, progress: Any | None = None) -> Any:
        return await self.agent.aic_memo(ticker, progress=progress)

    async def close(self) -> None:
        await self.agent.close()
