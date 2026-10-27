"""Translate native research-engine outputs into our stable research contract."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from app.core.contracts import EvidenceItem, ResearchBundle


def _as_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(k): _as_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_as_dict(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return {"type": type(value).__name__, "repr": repr(value)}


def _nonempty_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def research_bundle_from_tradingagents(
    final_state: Mapping[str, Any],
    *,
    instrument: str | None = None,
) -> ResearchBundle:
    """Map the native TradingAgents final AgentState without reinterpreting it."""

    ticker = instrument or str(final_state.get("company_of_interest") or "").strip()
    if not ticker:
        raise ValueError("TradingAgents final_state has no company_of_interest/instrument")

    trade_date = str(final_state.get("trade_date") or "").strip()
    try:
        as_of = datetime.strptime(trade_date, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(f"Invalid TradingAgents trade_date: {trade_date!r}") from exc

    debate = final_state.get("investment_debate_state") or {}
    bull = _nonempty_text(debate.get("bull_history") if isinstance(debate, Mapping) else None)
    bear = _nonempty_text(debate.get("bear_history") if isinstance(debate, Mapping) else None)

    memory_note = _nonempty_text(final_state.get("memory_note"))
    final_decision = _nonempty_text(final_state.get("final_trade_decision"))
    investment_plan = _nonempty_text(final_state.get("investment_plan"))
    trader_plan = _nonempty_text(final_state.get("trader_investment_plan"))
    final_rating = _nonempty_text(final_state.get("final_rating"))

    payload = {
        "asset_type": final_state.get("asset_type"),
        "instrument_context": final_state.get("instrument_context"),
        "investment_plan": investment_plan,
        "trader_investment_plan": trader_plan,
        "final_trade_decision": final_decision,
        "final_rating": final_rating,
        "risk_debate_state": _as_dict(final_state.get("risk_debate_state") or {}),
        "portfolio_context": final_state.get("portfolio_context"),
        "past_context": final_state.get("past_context"),
    }

    return ResearchBundle(
        instrument=ticker,
        as_of=as_of,
        market_report=_nonempty_text(final_state.get("market_report")),
        news_report=_nonempty_text(final_state.get("news_report")),
        fundamentals_report=_nonempty_text(final_state.get("fundamentals_report")),
        sentiment_report=_nonempty_text(final_state.get("sentiment_report")),
        bull_case=[bull] if bull else [],
        bear_case=[bear] if bear else [],
        uncertainties=[memory_note] if memory_note else [],
        evidence=[
            EvidenceItem(
                source="TradingAgents",
                as_of=as_of,
                summary=final_decision or investment_plan,
                payload=payload,
            )
        ],
    )


def merge_finrobot_result(
    bundle: ResearchBundle,
    result: Any,
    *,
    pipeline: str = "research",
) -> ResearchBundle:
    """Append a native FinRobot PipelineResult to an existing ResearchBundle."""

    steps = dict(getattr(result, "steps", {}) or {})
    structured = dict(getattr(result, "structured_data", {}) or {})
    failures = list(getattr(result, "failed_validations", []) or [])
    warnings = list(getattr(result, "warnings", []) or [])
    artifact_id = getattr(result, "artifact_id", None)

    if hasattr(result, "collect_warnings"):
        collected = list(result.collect_warnings())
    else:
        collected = [str(x) for x in warnings]

    payload = {
        "pipeline": pipeline,
        "steps": steps,
        "structured_data": _as_dict(structured),
        "failed_validations": _as_dict(failures),
        "warnings": collected,
        "artifact_id": artifact_id,
    }

    summary = result.format_summary() if hasattr(result, "format_summary") else None
    evidence = EvidenceItem(
        source=f"FinRobot:{pipeline}",
        as_of=bundle.as_of,
        summary=_nonempty_text(summary),
        payload=payload,
    )

    # Preserve the original TradingAgents reports. FinRobot remains separately
    # attributable evidence instead of being concatenated into an upstream report.
    return bundle.model_copy(
        update={
            "uncertainties": [*bundle.uncertainties, *collected],
            "evidence": [*bundle.evidence, evidence],
        }
    )
