"""Bridge to RD-Agent(Q)'s native QuantRDLoop."""

from __future__ import annotations

from typing import Any


class RDAgentQuantBridge:
    def __init__(self, prop_setting: Any | None = None) -> None:
        from rdagent.app.qlib_rd_loop.conf import QUANT_PROP_SETTING
        from rdagent.app.qlib_rd_loop.quant import QuantRDLoop

        self.loop = QuantRDLoop(prop_setting or QUANT_PROP_SETTING)

    async def run(
        self,
        *,
        step_n: int | None = None,
        loop_n: int | None = None,
        all_duration: str | None = None,
        base_features_path: str | None = None,
        research_bundle: Any | None = None,
    ) -> Any:
        if research_bundle is not None:
            from app.orchestration.rdagent import inject_research_into_rdagent

            inject_research_into_rdagent(self.loop, research_bundle)
        self.loop._init_base_features(base_features_path)
        await self.loop.run(step_n=step_n, loop_n=loop_n, all_duration=all_duration)
        return self.loop.trace

    @property
    def trace(self) -> Any:
        return self.loop.trace
