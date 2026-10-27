"""Bridge to Chronos native pipeline loading and forecasting APIs."""

from __future__ import annotations

from typing import Any


class ChronosBridge:
    """Load and call a native Chronos pipeline without wrapping model internals."""

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

    def predict_df(self, df: Any, **kwargs: Any) -> Any:
        return self.pipeline.predict_df(df, **kwargs)

    def embed(self, inputs: Any, **kwargs: Any) -> Any:
        if not hasattr(self.pipeline, "embed"):
            raise TypeError(f"{type(self.pipeline).__name__} does not expose embed()")
        return self.pipeline.embed(inputs, **kwargs)
