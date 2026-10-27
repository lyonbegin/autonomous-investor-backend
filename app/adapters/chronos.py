from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ChronosForecast:
    quantiles: Any
    mean: Any
    prediction_length: int | None
    quantile_levels: tuple[float, ...]
    native_pipeline: Any


class ChronosAdapter:
    """Calls BaseChronosPipeline/Chronos2Pipeline without interpreting forecasts."""

    @staticmethod
    def forecast(
        pipeline: Any,
        inputs: Any,
        *,
        prediction_length: int | None = None,
        quantile_levels: list[float] | tuple[float, ...] = (0.1, 0.5, 0.9),
        **kwargs: Any,
    ) -> ChronosForecast:
        levels = list(quantile_levels)
        quantiles, mean = pipeline.predict_quantiles(
            inputs=inputs,
            prediction_length=prediction_length,
            quantile_levels=levels,
            **kwargs,
        )
        return ChronosForecast(
            quantiles=quantiles,
            mean=mean,
            prediction_length=prediction_length,
            quantile_levels=tuple(levels),
            native_pipeline=pipeline,
        )
