"""Connect our research contract to RD-Agent's existing ExperimentPlan path."""

from __future__ import annotations

import hashlib

from app.core.contracts import Hypothesis, ResearchBundle


def research_instruction_for_rdagent(bundle: ResearchBundle) -> str:
    """Render attributed research as RD-Agent's existing plan.user_instruction."""

    sections: list[str] = [
        f"Instrument: {bundle.instrument}",
        f"Research as-of: {bundle.as_of.isoformat()}",
    ]
    for title, value in (
        ("Market report", bundle.market_report),
        ("News report", bundle.news_report),
        ("Fundamentals report", bundle.fundamentals_report),
        ("Sentiment report", bundle.sentiment_report),
    ):
        if value:
            sections.append(f"{title}:\n{value}")

    if bundle.bull_case:
        sections.append("Bull case:\n" + "\n".join(f"- {x}" for x in bundle.bull_case))
    if bundle.bear_case:
        sections.append("Bear case:\n" + "\n".join(f"- {x}" for x in bundle.bear_case))
    if bundle.uncertainties:
        sections.append("Known uncertainties:\n" + "\n".join(f"- {x}" for x in bundle.uncertainties))

    # Preserve source attribution. Do not flatten opaque structured payloads into
    # claims; the RD loop receives only the evidence summaries here.
    summaries = [
        f"- {item.source}: {item.summary}"
        for item in bundle.evidence
        if item.summary
    ]
    if summaries:
        sections.append("Attributed evidence summaries:\n" + "\n".join(summaries))

    sections.append(
        "Use the research above as external context when choosing the next factor/model hypothesis. "
        "The experiment must still be verified by RD-Agent's normal Qlib coding, running, and feedback loop."
    )
    return "\n\n".join(sections)


def inject_research_into_rdagent(loop: object, bundle: ResearchBundle) -> None:
    """Use RD-Agent's native ExperimentPlan user_instruction field."""

    plan = getattr(loop, "plan", None)
    if not isinstance(plan, dict):
        raise TypeError("RD-Agent loop does not expose the expected ExperimentPlan dictionary")
    plan["user_instruction"] = research_instruction_for_rdagent(bundle)


def hypothesis_from_rdagent(native: object, *, instrument_scope: list[str]) -> Hypothesis:
    """Map a native QlibQuantHypothesis to our stable Hypothesis contract."""

    thesis = str(getattr(native, "hypothesis", "") or "").strip()
    action = str(getattr(native, "action", "") or "").strip()
    if not thesis:
        raise ValueError("RD-Agent hypothesis is empty")
    if action not in {"factor", "model"}:
        raise ValueError(f"Unsupported RD-Agent quant action: {action!r}")

    reason = str(getattr(native, "reason", "") or "").strip()
    observation = str(getattr(native, "concise_observation", "") or "").strip()
    knowledge = str(getattr(native, "concise_knowledge", "") or "").strip()
    concise_reason = str(getattr(native, "concise_reason", "") or "").strip()
    justification = str(getattr(native, "concise_justification", "") or "").strip()

    evidence = [x for x in (observation, knowledge, concise_reason, justification, reason) if x]
    digest = hashlib.sha256(
        (action + "\0" + thesis + "\0" + reason).encode("utf-8")
    ).hexdigest()[:20]

    return Hypothesis(
        hypothesis_id=f"rdagent-{digest}",
        instrument_scope=instrument_scope,
        thesis=thesis,
        action=action,
        evidence=evidence,
        fail_conditions=[],
        market_expectation=None,
        catalyst=None,
    )
