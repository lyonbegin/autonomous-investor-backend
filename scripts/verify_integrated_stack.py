from __future__ import annotations

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

    from lab.bridges.chronos_bridge import ChronosBridge
    from lab.bridges.finrl_bridge import FinRLBridge
    from lab.bridges.finrobot_bridge import FinRobotBridge
    from lab.bridges.nautilus_bridge import NautilusBridge
    from lab.bridges.pypfopt_bridge import PyPortfolioOptBridge
    from lab.bridges.qlib_bridge import QlibBridge
    from lab.bridges.rdagent_bridge import RDAgentQuantBridge
    from lab.bridges.riskfolio_bridge import RiskfolioBridge
    from lab.bridges.rllib_bridge import RLlibBridge
    from lab.bridges.sb3_bridge import StableBaselinesBridge
    from lab.bridges.tradingagents_bridge import TradingAgentsBridge
    from lab.bridges.vectorbt_bridge import VectorBTBridge

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
        ]
    )

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
