from __future__ import annotations

from datetime import UTC, datetime

from app.core.contracts import TargetPortfolio, TargetWeight
from app.orchestration.allocation import target_portfolio_from_finrl
from app.orchestration.research import merge_finrobot_result, research_bundle_from_tradingagents
from app.orchestration.rdagent import hypothesis_from_rdagent, inject_research_into_rdagent
from app.orchestration.runtime import plan_rebalance
from app.orchestration.quant import forecasts_from_chronos_df, model_scores_from_qlib, policy_action


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

def test_qlib_prediction_remains_raw_model_score():
    class Predictions:
        def items(self):
            yield (datetime(2026, 10, 22, tzinfo=UTC), "AAPL"), 0.123

    rows = model_scores_from_qlib(Predictions(), model_id="qlib-lgb")
    assert rows[0].instrument == "AAPL"
    assert rows[0].score == 0.123
    assert not hasattr(rows[0], "expected_return")


def test_chronos_predict_df_maps_mean_and_quantiles_without_trade_direction():
    class ForecastFrame:
        columns = ["item_id", "timestamp", "target_name", "predictions", "0.1", "0.5", "0.9"]

        def iterrows(self):
            yield 0, {
                "item_id": "AAPL",
                "timestamp": datetime(2026, 10, 23, tzinfo=UTC),
                "target_name": "close",
                "predictions": 101.0,
                "0.1": 98.0,
                "0.5": 100.5,
                "0.9": 104.0,
            }

    rows = forecasts_from_chronos_df(ForecastFrame(), model_id="chronos2", horizon="1d")
    assert rows[0].point_forecast == 101.0
    assert [(q.quantile, q.value) for q in rows[0].quantiles] == [
        (0.1, 98.0),
        (0.5, 100.5),
        (0.9, 104.0),
    ]


def test_rl_action_is_kept_uninterpreted_until_environment_adapter():
    wrapped = policy_action(
        [0.25, -0.5],
        policy_id="ppo-1",
        timestamp=datetime(2026, 10, 22, tzinfo=UTC),
        instrument_scope=["AAPL", "MSFT"],
    )
    assert wrapped.action == [0.25, -0.5]
    assert wrapped.instrument_scope == ["AAPL", "MSFT"]

def test_research_coordinator_runs_native_tradingagents_then_finrobot():
    import asyncio
    from types import SimpleNamespace

    from app.orchestration.pipeline import ResearchCoordinator

    class TradingAgents:
        def run(self, instrument, trade_date, *, asset_type="stock", portfolio=None):
            assert instrument == "AAPL"
            assert trade_date == "2026-10-22"
            return SimpleNamespace(
                final_state={
                    "company_of_interest": instrument,
                    "trade_date": trade_date,
                    "asset_type": asset_type,
                    "market_report": "market",
                    "investment_debate_state": {},
                },
                signal="BUY",
            )

    class FinRobot:
        async def research(self, ticker):
            assert ticker == "AAPL"
            return _FakePipelineResult()

    out = asyncio.run(ResearchCoordinator(TradingAgents(), FinRobot()).run("AAPL", "2026-10-22"))

    assert out.tradingagents_signal == "BUY"
    assert out.bundle.instrument == "AAPL"
    assert out.bundle.evidence[0].payload["native_signal"] == "BUY"
    assert out.bundle.evidence[-1].source == "FinRobot:research"


def test_rdagent_coordinator_uses_native_loop_plan_then_runs_bridge():
    import asyncio

    from app.orchestration.pipeline import RDAgentCoordinator

    bundle = research_bundle_from_tradingagents(
        {
            "company_of_interest": "AAPL",
            "trade_date": "2026-10-22",
            "market_report": "market evidence",
            "investment_debate_state": {},
        }
    )

    class Bridge:
        def __init__(self):
            self.loop = type("Loop", (), {"plan": {"features": {}, "feature_codes": {}}})()
            self.called = None

        async def run(self, **kwargs):
            self.called = kwargs
            return {"trace": "native"}

    bridge = Bridge()
    result = asyncio.run(RDAgentCoordinator(bridge).run(bundle, step_n=2))

    assert result == {"trace": "native"}
    assert bridge.called["step_n"] == 2
    assert "AAPL" in bridge.loop.plan["user_instruction"]


def test_nautilus_execution_coordinator_plans_then_submits_native_orders():
    from app.orchestration.pipeline import NautilusExecutionCoordinator

    target = TargetPortfolio(
        strategy_id="s1",
        as_of=datetime(2026, 10, 22, tzinfo=UTC),
        weights=[
            TargetWeight(instrument="A", weight=0.6),
            TargetWeight(instrument="B", weight=0.4),
        ],
    )

    class Nautilus:
        def __init__(self):
            self.intents = []

        def submit_market_intent(self, strategy, intent):
            self.intents.append(intent)
            return {"instrument": intent.instrument, "side": intent.side}

    native = Nautilus()
    result = NautilusExecutionCoordinator(native).submit(
        object(),
        target,
        equity=1000.0,
        prices={"A": 10.0, "B": 20.0},
        current_quantities={"A": 20.0},
    )

    assert [(x.instrument, x.side, x.quantity) for x in result.intents] == [
        ("A", "buy", 40.0),
        ("B", "buy", 20.0),
    ]
    assert result.native_orders == [
        {"instrument": "A", "side": "buy"},
        {"instrument": "B", "side": "buy"},
    ]
    assert native.intents == result.intents

