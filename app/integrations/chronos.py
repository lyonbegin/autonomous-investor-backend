"""Bridge to Chronos native pipelines."""

from __future__ import annotations

from typing import Any


class ChronosBridge:
    def __init__(self, pipeline: Any) -> None:
        self.pipeline = pipeline

    @classmethod
    def from_pretrained(
        cls,
        model_name_or_path: str,
        *,
        pipeline_class: str = "auto",
        **kwargs: Any,
    ) -> "ChronosBridge":
        from chronos import BaseChronosPipeline, Chronos2Pipeline

        if pipeline_class == "chronos2":
            pipeline = Chronos2Pipeline.from_pretrained(model_name_or_path, **kwargs)
        elif pipeline_class == "auto":
            pipeline = BaseChronosPipeline.from_pretrained(model_name_or_path, **kwargs)
        else:
            raise ValueError("pipeline_class must be 'auto' or 'chronos2'")
        return cls(pipeline)

    def predict_quantiles(self, inputs: Any, **kwargs: Any) -> Any:
        return self.pipeline.predict_quantiles(inputs=inputs, **kwargs)
