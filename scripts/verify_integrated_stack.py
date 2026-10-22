from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd


def main() -> None:
    import chronos
    import finrobot
    import nautilus_trader
    import pypfopt
    import qlib
    import ray
    import rdagent
    import riskfolio
    import stable_baselines3
    import tradingagents
    import vectorbt

    from chronos import Chronos2Pipeline
    from finrobot import FinRobot
    from nautilus_trader.backtest import BacktestEngineConfig, BacktestNode
    from nautilus_trader.execution import ExecutionEngineConfig
    from nautilus_trader.risk import RiskEngineConfig
    from nautilus_trader.trading import Strategy, StrategyConfig
    from pypfopt import EfficientFrontier
    from qlib.model.base import BaseModel
    from ray.rllib.algorithms.ppo import PPOConfig
    from rdagent.app.qlib_rd_loop.quant import QuantRDLoop
    from riskfolio import Portfolio as RiskfolioPortfolio
    from stable_baselines3 import PPO
    from strategies.base_strategy import StrategyResult
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from vectorbt.portfolio.base import Portfolio

    assert all(
        [
            TradingAgentsGraph,
            FinRobot,
            QuantRDLoop,
            BaseModel,
            Chronos2Pipeline,
            PPO,
            PPOConfig,
            Portfolio,
            StrategyResult,
            RiskfolioPortfolio,
            EfficientFrontier,
            Strategy,
            StrategyConfig,
            BacktestNode,
            BacktestEngineConfig,
            RiskEngineConfig,
            ExecutionEngineConfig,
        ]
    )

    from app.integrations.chronos import ChronosBridge
    from app.integrations.finrl import FinRLBridge
    from app.integrations.finrobot import FinRobotBridge
    from app.integrations.nautilus import NautilusBridge
    from app.integrations.pypfopt import PyPortfolioOptBridge
    from app.integrations.qlib import QlibBridge
    from app.integrations.rdagent import RDAgentQuantBridge
    from app.integrations.riskfolio import RiskfolioBridge
    from app.integrations.rllib import RLlibBridge
    from app.integrations.sb3 import StableBaselinesBridge
    from app.integrations.tradingagents import TradingAgentsBridge
    from app.integrations.vectorbt import VectorBTBridge
    from app.orchestration.pipeline import (
        AllocationCoordinator,
        NautilusExecutionCoordinator,
        QuantCoordinator,
        RDAgentCoordinator,
        ResearchCoordinator,
    )

    close = pd.Series([1.0, 2.0, 1.5, 3.0])
    pf = VectorBTBridge.from_signals(
        close,
        pd.Series([True, False, True, False]),
        pd.Series([False, True, False, True]),
    )
    assert float(pf.total_return()) == 3.0

    strategy = FinRLBridge.equal_weight("eq")
    result = FinRLBridge.generate_weights(
        strategy,
        {"fundamentals": pd.DataFrame({"gvkey": ["A", "B", "C"]})},
    )
    assert result.weights.shape[0] == 3

    returns = pd.DataFrame(
        {
            "A": [0.01, -0.01, 0.02, 0.00, 0.01],
            "B": [0.00, 0.01, -0.01, 0.02, 0.01],
            "C": [0.02, 0.00, 0.01, -0.01, 0.00],
        }
    )
    rp = RiskfolioBridge.portfolio(returns)
    RiskfolioBridge.estimate(rp, method_mu="hist", method_cov="hist")
    assert RiskfolioBridge.optimize(rp, model="Classic", rm="MV", obj="MinRisk", hist=True) is not None

    mu = pd.Series([0.10, 0.12, 0.08], index=["A", "B", "C"])
    cov = pd.DataFrame(np.diag([0.04, 0.05, 0.03]), index=mu.index, columns=mu.index)
    ef = PyPortfolioOptBridge.efficient_frontier(mu, cov)
    PyPortfolioOptBridge.min_volatility(ef)
    assert abs(sum(PyPortfolioOptBridge.clean_weights(ef).values()) - 1.0) < 1e-6

    risk = NautilusBridge.risk_config()
    execution = NautilusBridge.execution_config()
    backtest = NautilusBridge.backtest_engine_config(risk_engine=risk, exec_engine=execution)
    assert backtest.risk_engine is not None
    assert backtest.exec_engine is not None

    assert all(
        [
            TradingAgentsBridge,
            FinRobotBridge,
            RDAgentQuantBridge,
            QlibBridge,
            ChronosBridge,
            StableBaselinesBridge,
            RLlibBridge,
            ResearchCoordinator,
            RDAgentCoordinator,
            QuantCoordinator,
            AllocationCoordinator,
            NautilusExecutionCoordinator,
        ]
    )

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["python"].startswith("3.13.")

    response = client.get("/api/v1/integrations?probe_runtime=true")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 12
    failures = [
        row for row in payload["integrations"]
        if not row.get("installed") or not row.get("import_ok")
    ]
    assert failures == [], failures

    print("FASTAPI_TWELVE_PROBES_OK")
    print("ALL_TWELVE_NATIVE_IMPORTS_OK")
    print("ALL_BRIDGES_OK")
    print("nautilus_trader", nautilus_trader.__version__)
    print("ray", ray.__version__)
    print("vectorbt", vectorbt.__version__)
    print("riskfolio", riskfolio.__version__)
    print("pypfopt", pypfopt.__version__)
    print("qlib", qlib.__version__)
    print("chronos", chronos.__version__)
    print("stable_baselines3", stable_baselines3.__version__)


if __name__ == "__main__":
    main()
