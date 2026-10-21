from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd

from app.adapters.chronos import ChronosAdapter
from app.adapters.finrl import FinRLAdapter
from app.adapters.finrobot import FinRobotAdapter
from app.adapters.nautilus import RebalancePlanner
from app.adapters.portfolio import PortfolioAdapter
from app.adapters.qlib import QlibAdapter
from app.adapters.rdagent import RDAgentAdapter
from app.adapters.rllib import RLlibAdapter
from app.adapters.sb3 import StableBaselinesAdapter
from app.adapters.tradingagents import TradingAgentsAdapter
from app.core.contracts import TargetPortfolio, TargetWeight


def test_tradingagents_preserves_native_and_maps_reports():
    state = {
        "company_of_interest": "AAPL",
        "trade_date": "2026-10-21",
        "market_report": "market",
        "sentiment_report": "sentiment",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
        "investment_debate_state": {"bull_history": "bull", "bear_history": "bear"},
        "investment_plan": "plan",
        "trader_investment_plan": "trade plan",
        "final_trade_decision": "decision",
        "memory_note": "",
    }

    class Graph:
        def propagate(self, *args, **kwargs):
            return state, "Buy"

    run = TradingAgentsAdapter(Graph()).run("AAPL", "2026-10-21")
    assert run.native_state is state
    assert run.native_rating == "Buy"
    assert run.research.market_report == "market"
    assert run.research.bull_case == ["bull"]


def test_finrobot_maps_known_equity_research_steps_without_losing_native():
    result = SimpleNamespace(
        steps={
            "technical_analysis": "technical",
            "catalyst_analysis": "catalyst",
            "financial_modeling": "financial",
            "thesis": "thesis",
        },
        structured_data={"native": object()},
        failed_validations=[{"step": "x", "reason": "warning"}],
    )
    research = FinRobotAdapter.to_research_bundle(
        result,
        ticker="AAPL",
        as_of=datetime(2026, 10, 21, tzinfo=UTC),
    )
    assert research.market_report == "technical"
    assert research.news_report == "catalyst"
    assert research.fundamentals_report == "financial"
    assert len(research.evidence) == 4


def test_finrl_strategy_result_to_target_portfolio():
    result = SimpleNamespace(
        strategy_name="equal_weight",
        weights=pd.DataFrame({"gvkey": ["A", "B"], "weight": [0.4, 0.6]}),
        metadata={"source": "native"},
    )
    target = FinRLAdapter.to_target_portfolio(
        result,
        as_of=datetime(2026, 10, 21, tzinfo=UTC),
    )
    assert [x.instrument for x in target.weights] == ["A", "B"]
    assert [x.weight for x in target.weights] == [0.4, 0.6]


def test_qlib_does_not_guess_signal_semantics():
    native = pd.Series([0.1, -0.2])

    class Model:
        def predict(self, dataset, segment="test"):
            return native

    prediction = QlibAdapter.predict(Model(), object())
    assert prediction.native_prediction is native


def test_chronos_preserves_native_forecast():
    quantiles = object()
    mean = object()

    class Pipeline:
        def predict_quantiles(self, **kwargs):
            return quantiles, mean

    result = ChronosAdapter.forecast(Pipeline(), inputs=[1, 2, 3], prediction_length=2)
    assert result.quantiles is quantiles
    assert result.mean is mean
    assert result.prediction_length == 2


def test_portfolio_native_weight_outputs():
    rf = pd.DataFrame({"weights": [0.25, 0.75]}, index=["A", "B"])
    riskfolio_target = PortfolioAdapter.from_riskfolio(rf, strategy_id="riskfolio")
    assert riskfolio_target.weights[1].weight == 0.75

    pypf_target = PortfolioAdapter.from_pyportfolioopt(
        {"A": 0.3, "B": 0.7},
        strategy_id="pypfopt",
    )
    assert pypf_target.weights[0].instrument == "A"


def test_rebalance_planner_is_separate_from_nautilus_native_execution():
    target = TargetPortfolio(
        strategy_id="test",
        as_of=datetime(2026, 10, 21, tzinfo=UTC),
        weights=[
            TargetWeight(instrument="A", weight=0.6),
            TargetWeight(instrument="B", weight=0.4),
        ],
    )
    intents = RebalancePlanner.plan(
        target,
        equity=1000,
        prices={"A": 100, "B": 50},
        current_quantities={"A": 2, "B": 0},
    )
    assert intents[0].target_quantity == 6
    assert intents[0].quantity_delta == 4
    assert intents[1].target_quantity == 8


def test_rdagent_uses_native_loop_run_and_preserves_trace():
    trace = object()

    class Loop:
        def __init__(self):
            self.trace = trace
            self.args = None

        async def run(self, **kwargs):
            self.args = kwargs

    loop = Loop()
    result = asyncio.run(RDAgentAdapter.run(loop, loop_n=1))
    assert result.native_loop is loop
    assert result.native_trace is trace
    assert loop.args["loop_n"] == 1


def test_sb3_adapter_calls_native_predict():
    class Model:
        def predict(self, observation, **kwargs):
            return "action", "state"

    result = StableBaselinesAdapter.predict(Model(), [1, 2], deterministic=True)
    assert result.action == "action"
    assert result.state == "state"


def test_rllib_adapter_keeps_algorithm_native():
    module = object()

    class Algorithm:
        def train(self):
            return {"episode_return_mean": 1.2}

        def get_module(self, module_id=None):
            return module

    algo = Algorithm()
    trained = RLlibAdapter.train_once(algo)
    assert trained.result["episode_return_mean"] == 1.2
    assert RLlibAdapter.module(algo) is module
