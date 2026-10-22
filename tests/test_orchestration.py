from __future__ import annotations

from datetime import UTC, datetime

from app.core.contracts import TargetPortfolio, TargetWeight
from app.orchestration.allocation import target_portfolio_from_finrl
from app.orchestration.research import merge_finrobot_result, research_bundle_from_tradingagents
from app.orchestration.rdagent import hypothesis_from_rdagent, inject_research_into_rdagent
from app.orchestration.runtime import plan_rebalance


class _FakeFrame:
    columns = ["gvkey", "weight"]

    def iterrows(self):
        yield 0, {"gvkey": "A", "weight": 0.6}
        yield 1, {"gvkey": "B", "weight": 0.4}


class _FakeStrategyResult:
    strategy_name = "native-finrl"
    weights = _FakeFrame()
    metadata = {"native": True}


class _FakePipelineResult:
    steps = {"summary": "FinRobot result"}
    structured_data = {"valuation": {"pe": 12.5}}
    failed_validations = []
    warnings = ["sample warning"]
    artifact_id = "artifact-1"

    def collect_warnings(self):
        return list(self.warnings)

    def format_summary(self):
        return "# FinRobot Analysis Report"


def test_tradingagents_state_maps_without_reinterpreting_reports():
    state = {
        "company_of_interest": "AAPL",
        "trade_date": "2026-10-22",
        "asset_type": "stock",
        "market_report": "market",
        "sentiment_report": "sentiment",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
        "investment_debate_state": {
            "bull_history": "bull evidence",
            "bear_history": "bear evidence",
        },
        "investment_plan": "plan",
        "trader_investment_plan": "trade plan",
        "final_trade_decision": "decision",
        "final_rating": "Buy",
        "risk_debate_state": {"history": "risk"},
    }

    bundle = research_bundle_from_tradingagents(state)

    assert bundle.instrument == "AAPL"
    assert bundle.market_report == "market"
    assert bundle.bull_case == ["bull evidence"]
    assert bundle.bear_case == ["bear evidence"]
    assert bundle.evidence[0].payload["final_rating"] == "Buy"


def test_finrobot_result_is_kept_as_attributed_evidence():
    bundle = research_bundle_from_tradingagents(
        {
            "company_of_interest": "AAPL",
            "trade_date": "2026-10-22",
            "investment_debate_state": {},
        }
    )

    merged = merge_finrobot_result(bundle, _FakePipelineResult())

    assert merged.market_report is None
    assert merged.evidence[-1].source == "FinRobot:research"
    assert merged.evidence[-1].payload["artifact_id"] == "artifact-1"
    assert "sample warning" in merged.uncertainties


def test_finrl_native_weight_boundary_maps_to_target_portfolio():
    target = target_portfolio_from_finrl(
        _FakeStrategyResult(),
        as_of=datetime(2026, 10, 22, tzinfo=UTC),
    )

    assert target.strategy_id == "native-finrl"
    assert [(x.instrument, x.weight) for x in target.weights] == [("A", 0.6), ("B", 0.4)]
    assert target.metadata["source"] == "FinRL-Trading"


def test_rebalance_planner_closes_removed_positions_and_opens_targets():
    target = TargetPortfolio(
        strategy_id="s1",
        as_of=datetime(2026, 10, 22, tzinfo=UTC),
        weights=[
            TargetWeight(instrument="A", weight=0.6),
            TargetWeight(instrument="B", weight=0.4),
        ],
    )

    intents = plan_rebalance(
        target,
        equity=1000.0,
        prices={"A": 10.0, "B": 20.0, "C": 5.0},
        current_quantities={"A": 20.0, "C": 10.0},
    )
    by_instrument = {x.instrument: x for x in intents}

    assert by_instrument["A"].side == "buy"
    assert by_instrument["A"].quantity == 40.0
    assert by_instrument["B"].side == "buy"
    assert by_instrument["B"].quantity == 20.0
    assert by_instrument["C"].side == "sell"
    assert by_instrument["C"].quantity == 10.0
    assert by_instrument["C"].target_weight == 0.0

def test_research_bundle_uses_rdagent_native_user_instruction_plan():
    bundle = research_bundle_from_tradingagents(
        {
            "company_of_interest": "AAPL",
            "trade_date": "2026-10-22",
            "market_report": "market evidence",
            "investment_debate_state": {},
        }
    )

    class FakeLoop:
        plan = {"features": {}, "feature_codes": {}}

    loop = FakeLoop()
    inject_research_into_rdagent(loop, bundle)

    assert "user_instruction" in loop.plan
    assert "AAPL" in loop.plan["user_instruction"]
    assert "market evidence" in loop.plan["user_instruction"]


def test_native_rdagent_hypothesis_maps_without_inventing_fail_condition():
    class NativeHypothesis:
        hypothesis = "Momentum conditioned on volatility improves IC"
        action = "factor"
        reason = "Observed regime behavior"
        concise_reason = "regime"
        concise_observation = "momentum dispersion"
        concise_justification = "testable in Qlib"
        concise_knowledge = "volatility interaction"

    mapped = hypothesis_from_rdagent(NativeHypothesis(), instrument_scope=["AAPL"])

    assert mapped.action == "factor"
    assert mapped.instrument_scope == ["AAPL"]
    assert mapped.fail_conditions == []
    assert mapped.market_expectation is None
    assert mapped.thesis == NativeHypothesis.hypothesis

