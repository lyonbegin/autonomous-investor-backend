from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RDAgentRun:
    native_loop: Any
    native_trace: Any


class RDAgentAdapter:
    """Runs RD-Agent's own LoopBase.run; RD-Agent keeps its full internal workflow."""

    @staticmethod
    async def run(
        loop: Any,
        *,
        step_n: int | None = None,
        loop_n: int | None = 1,
        all_duration: str | None = None,
    ) -> RDAgentRun:
        await loop.run(step_n=step_n, loop_n=loop_n, all_duration=all_duration)
        return RDAgentRun(native_loop=loop, native_trace=loop.trace)
