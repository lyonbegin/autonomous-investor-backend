from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class EvidenceItem(BaseModel):
    source: str
    as_of: datetime | None = None
    uri: str | None = None
    summary: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ResearchBundle(BaseModel):
    instrument: str
    as_of: datetime
    market_report: str | None = None
    macro_report: str | None = None
    news_report: str | None = None
    fundamentals_report: str | None = None
    sentiment_report: str | None = None
    valuation_metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
    bull_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class Hypothesis(BaseModel):
    hypothesis_id: str
    instrument_scope: list[str]
    thesis: str
    action: Literal["factor", "model", "strategy", "allocation", "execution"]
    evidence: list[str] = Field(default_factory=list)
    fail_conditions: list[str] = Field(default_factory=list)
    market_expectation: str | None = None
    catalyst: str | None = None


class ExperimentResult(BaseModel):
    experiment_id: str
    hypothesis_id: str
    status: Literal["queued", "running", "passed", "failed", "rejected"]
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    observations: list[str] = Field(default_factory=list)


class ModelScore(BaseModel):
    instrument: str
    timestamp: datetime
    model_id: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ForecastQuantile(BaseModel):
    quantile: float = Field(gt=0.0, lt=1.0)
    value: float


class Forecast(BaseModel):
    instrument: str
    timestamp: datetime
    model_id: str
    horizon: str
    target: str
    point_forecast: float | None = None
    quantiles: list[ForecastQuantile] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyAction(BaseModel):
    policy_id: str
    timestamp: datetime
    action: Any
    instrument_scope: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Signal(BaseModel):
    instrument: str
    timestamp: datetime
    horizon: str
    direction: Literal[-1, 0, 1]
    expected_return: float | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty: float | None = Field(default=None, ge=0.0, le=1.0)
    model_id: str
    evidence: list[str] = Field(default_factory=list)


class TargetWeight(BaseModel):
    instrument: str
    weight: float


class TargetPortfolio(BaseModel):
    strategy_id: str
    as_of: datetime
    weights: list[TargetWeight]
    cash_weight: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("weights")
    @classmethod
    def unique_instruments(cls, value: list[TargetWeight]) -> list[TargetWeight]:
        names = [x.instrument for x in value]
        if len(names) != len(set(names)):
            raise ValueError("duplicate instruments in target weights")
        return value

    @property
    def gross_exposure(self) -> float:
        return sum(abs(x.weight) for x in self.weights)

    @property
    def net_exposure(self) -> float:
        return sum(x.weight for x in self.weights)


class OrderIntent(BaseModel):
    instrument: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0.0)
    target_weight: float
    current_quantity: float
    target_quantity: float
    reference_price: float = Field(gt=0.0)
    notional_delta: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskDecision(BaseModel):
    approved: bool
    target: TargetPortfolio
    violations: list[str] = Field(default_factory=list)
    limits: dict[str, float | int | str | bool] = Field(default_factory=dict)


class ExecutionReport(BaseModel):
    execution_id: str
    mode: Literal["backtest", "paper", "live"]
    accepted: bool
    submitted_orders: int = 0
    rejected_orders: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
