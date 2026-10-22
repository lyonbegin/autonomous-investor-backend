"""Translate native quant/model outputs without inventing trading semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable

from app.core.contracts import Forecast, ForecastQuantile, ModelScore, PolicyAction


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if hasattr(value, "to_pydatetime"):
        dt = value.to_pydatetime()
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    return datetime.fromisoformat(str(value)).replace(tzinfo=UTC)


def model_scores_from_qlib(predictions: Any, *, model_id: str) -> list[ModelScore]:
    """Map Qlib's native prediction Series/DataFrame rows to raw model scores.

    Qlib scores are deliberately not treated as expected returns or buy/sell
    directions here. Their meaning depends on the model label and strategy.
    """

    if hasattr(predictions, "ndim") and predictions.ndim == 2:
        if len(predictions.columns) != 1:
            raise ValueError("Qlib multi-column predictions need an explicit score column")
        predictions = predictions.iloc[:, 0]

    rows: list[ModelScore] = []
    for index, value in predictions.items():
        if isinstance(index, tuple) and len(index) >= 2:
            ts, instrument = index[0], index[1]
        else:
            raise ValueError("Qlib predictions must be indexed by (datetime, instrument)")

        rows.append(
            ModelScore(
                instrument=str(instrument),
                timestamp=_timestamp(ts),
                model_id=model_id,
                score=float(value),
                metadata={"source": "Qlib"},
            )
        )
    return rows


def forecasts_from_chronos_df(
    frame: Any,
    *,
    model_id: str,
    horizon: str,
    id_column: str = "item_id",
    timestamp_column: str = "timestamp",
) -> list[Forecast]:
    """Map Chronos predict_df output exactly: predictions + numeric quantile columns."""

    required = {id_column, timestamp_column, "target_name", "predictions"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Chronos forecast frame missing columns: {sorted(missing)}")

    quantile_columns: list[tuple[float, str]] = []
    for column in frame.columns:
        try:
            q = float(column)
        except (TypeError, ValueError):
            continue
        if 0.0 < q < 1.0:
            quantile_columns.append((q, column))

    rows: list[Forecast] = []
    for _, row in frame.iterrows():
        rows.append(
            Forecast(
                instrument=str(row[id_column]),
                timestamp=_timestamp(row[timestamp_column]),
                model_id=model_id,
                horizon=horizon,
                target=str(row["target_name"]),
                point_forecast=float(row["predictions"]),
                quantiles=[
                    ForecastQuantile(quantile=q, value=float(row[column]))
                    for q, column in quantile_columns
                ],
                metadata={"source": "Chronos", "forecast_semantics": "mean"},
            )
        )
    return rows


def policy_action(
    action: Any,
    *,
    policy_id: str,
    timestamp: datetime | None = None,
    instrument_scope: Iterable[str] = (),
    metadata: dict[str, Any] | None = None,
) -> PolicyAction:
    """Wrap an SB3/RLlib native action; interpretation remains environment-specific."""

    if hasattr(action, "tolist"):
        action = action.tolist()

    return PolicyAction(
        policy_id=policy_id,
        timestamp=timestamp or datetime.now(UTC),
        action=action,
        instrument_scope=[str(x) for x in instrument_scope],
        metadata=metadata or {},
    )
