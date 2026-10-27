from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IntegrationSpec:
    key: str
    name: str
    repository: str
    pinned_ref: str
    role: str
    python_module: str
    symbols: tuple[str, ...] = ()
    validated: bool = True


SPECS: tuple[IntegrationSpec, ...] = (
    IntegrationSpec(
        "tradingagents",
        "TradingAgents",
        "TauricResearch/TradingAgents",
        "e8f5503e9b86d5c2710b0c76b1f686703968c9df",
        "market/news/fundamental/sentiment research and bull-bear debate",
        "tradingagents.graph.trading_graph",
        ("TradingAgentsGraph",),
    ),
    IntegrationSpec(
        "finrobot",
        "FinRobot V2",
        "AI4Finance-Foundation/FinRobot",
        "2717499b8e30f242640af08c4ad9afd1113c2d45",
        "deterministic finance computation and typed research pipelines",
        "finrobot",
        ("FinRobot",),
    ),
    IntegrationSpec(
        "rdagent",
        "RD-Agent(Q)",
        "microsoft/RD-Agent",
        "484776c211e4fbbeef03e0ec00d6bbee7362a4f4",
        "hypothesis -> experiment -> code -> run -> feedback autonomous R&D",
        "rdagent.app.qlib_rd_loop.quant",
        ("QuantRDLoop",),
    ),
    IntegrationSpec(
        "qlib",
        "Qlib",
        "microsoft/qlib",
        "54355232463878d2eebb91fe0ee5fa7fa1f5976c",
        "features, ML, signals, validation and backtesting",
        "qlib.model.base",
        ("BaseModel",),
    ),
    IntegrationSpec(
        "chronos",
        "Chronos",
        "amazon-science/chronos-forecasting",
        "1224fafa91e1ecd6674f5204066b159e40b5e4a1",
        "time-series foundation model forecasts",
        "chronos",
        ("Chronos2Pipeline",),
    ),
    IntegrationSpec(
        "sb3",
        "Stable-Baselines3",
        "DLR-RM/stable-baselines3",
        "b2878f4b83e21f16a53c54a62def628e05fd2e96",
        "reinforcement-learning algorithms",
        "stable_baselines3",
        ("PPO",),
    ),
    IntegrationSpec(
        "rllib",
        "Ray RLlib",
        "ray-project/ray",
        "ray-2.59.0",
        "distributed reinforcement learning",
        "ray.rllib.algorithms.ppo",
        ("PPOConfig",),
    ),
    IntegrationSpec(
        "vectorbt",
        "vectorbt",
        "polakowo/vectorbt",
        "v1.2.0",
        "high-throughput strategy screening",
        "vectorbt.portfolio.base",
        ("Portfolio",),
    ),
    IntegrationSpec(
        "finrl",
        "FinRL-Trading",
        "AI4Finance-Foundation/FinRL-Trading",
        "4409abe925c904e570be78ebfb5e77ac3491dff8",
        "target-weight strategy contract",
        "strategies.base_strategy",
        ("StrategyResult", "BaseStrategy"),
    ),
    IntegrationSpec(
        "riskfolio",
        "Riskfolio-Lib",
        "dcajasn/Riskfolio-Lib",
        "7b1b26ac9760974c12ecefe290a9d3bd37b66b7a",
        "portfolio optimization and risk measures",
        "riskfolio",
        ("Portfolio",),
    ),
    IntegrationSpec(
        "pyportfolioopt",
        "PyPortfolioOpt",
        "PyPortfolio/PyPortfolioOpt",
        "a6638d2e06dae6f444fd022cfd4b3c528902a85b",
        "efficient-frontier portfolio optimization",
        "pypfopt",
        ("EfficientFrontier",),
    ),
    IntegrationSpec(
        "nautilus",
        "NautilusTrader",
        "nautechsystems/nautilus_trader",
        "69aa8a283c8735cee4a536084078e3b19ac9a1be",
        "event-driven backtest, portfolio, risk, paper/live execution runtime",
        "nautilus_trader.trading",
        ("Strategy", "StrategyConfig"),
    ),
)


def probe(spec: IntegrationSpec) -> dict[str, Any]:
    result: dict[str, Any] = asdict(spec)
    try:
        module = importlib.import_module(spec.python_module)
    except Exception as exc:
        result.update(
            installed=False,
            import_ok=False,
            symbols={},
            error=f"{type(exc).__name__}: {exc}",
        )
        return result

    symbols = {name: hasattr(module, name) for name in spec.symbols}
    result.update(
        installed=True,
        import_ok=all(symbols.values()) if symbols else True,
        symbols=symbols,
        error=None,
        module_file=getattr(module, "__file__", None),
        module_version=getattr(module, "__version__", None),
    )
    return result


def probe_all() -> list[dict[str, Any]]:
    return [probe(spec) for spec in SPECS]
