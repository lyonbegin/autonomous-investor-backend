from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SB3Prediction:
    action: Any
    state: Any
    native_model: Any


class StableBaselinesAdapter:
    """Thin wrapper around Stable-Baselines3 BaseAlgorithm.predict()."""

    @staticmethod
    def predict(
        model: Any,
        observation: Any,
        *,
        state: Any = None,
        episode_start: Any = None,
        deterministic: bool = True,
    ) -> SB3Prediction:
        action, next_state = model.predict(
            observation,
            state=state,
            episode_start=episode_start,
            deterministic=deterministic,
        )
        return SB3Prediction(action=action, state=next_state, native_model=model)
