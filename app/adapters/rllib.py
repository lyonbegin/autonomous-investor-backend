from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class RLlibTrainResult:
    result: dict[str, Any]
    native_algorithm: Any


class RLlibAdapter:
    """Keeps RLlib's Algorithm/AlgorithmConfig as the native control surface.

    Inference is deliberately supplied by the caller because current RLlib is
    migrating away from Algorithm.compute_single_action toward RLModule.
    """

    @staticmethod
    def train_once(algorithm: Any) -> RLlibTrainResult:
        return RLlibTrainResult(result=algorithm.train(), native_algorithm=algorithm)

    @staticmethod
    def module(algorithm: Any, module_id: str | None = None) -> Any:
        return algorithm.get_module(module_id) if module_id is not None else algorithm.get_module()

    @staticmethod
    def infer(
        algorithm: Any,
        inference: Callable[[Any], Any],
    ) -> Any:
        return inference(RLlibAdapter.module(algorithm))
