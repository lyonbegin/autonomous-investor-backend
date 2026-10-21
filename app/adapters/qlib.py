from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from app.core.contracts import Signal


@dataclass(slots=True)
class QlibPrediction:
    native_prediction: Any
    model: Any
    segment: Any


class QlibAdapter:
    """Preserves Qlib model outputs; signal conversion is explicit, never guessed."""

    @staticmethod
    def predict(model: Any, dataset: Any, *, segment: Any = "test") -> QlibPrediction:
        prediction = model.predict(dataset, segment=segment)
        return QlibPrediction(
            native_prediction=prediction,
            model=model,
            segment=segment,
        )

    @staticmethod
    def to_signals(
        prediction: QlibPrediction,
        converter: Callable[[Any], Iterable[Signal]],
    ) -> list[Signal]:
        return list(converter(prediction.native_prediction))
