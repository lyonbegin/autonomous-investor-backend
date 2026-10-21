from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IntegrationSpec:
    key: str
    name: str
    repository: str
    pinned_commit: str | None
    role: str
    python_module: str
    symbols: tuple[str, ...] = ()
    required_for_boot: bool = False


SPECS: tuple[IntegrationSpec, ...] = (
    IntegrationSpec("tradingagents", "TradingAgents", "TauricResearch/TradingAgents", "e8f5503e9b86d5c2710b0c76b1f686703968c9df", "market/news/fundamental/sentiment research and bull-bear debate", "tradingagents.graph.trading_graph", ("TradingAgentsGraph",)),
    IntegrationSpec("finrobot", "FinRobot V2", "AI4Finance-Foundation/FinRobot", "2717499b8e30f242640af08c4ad9afd1113c2d45", "deterministic finance computation and typed research pipelines", "finrobot.engine.pipelines.runner", ("Pipeline",)),
    IntegrationSpec("rdagent", "RD-Agent(Q)", "microsoft/RD-Agent", "484776c211e4fbbeef03e0ec00d6bbee7362a4f4", "hypothesis -> experiment -> code -> run -> feedback autonomous R&D", "rdagent.app.qlib_rd_loop.quant", ("QuantRDLoop",)),
    IntegrationSpec("qlib", "Qlib", "microsoft/qlib", "54355232463878d2eebb91fe0ee5fa7fa1f5976c", "features, ML, signals, strategy, validation and backtesting", "qlib"),
    IntegrationSpec("chronos", "Chronos", "amazon-science/chronos-forecasting", "1224fafa91e1ecd6674f5204066b159e40b5e4a1", "time-series foundation model forecasts", "chronos"),
    IntegrationSpec("sb3", "Stable-Baselines3", "DLR-RM/stable-baselines3", "b2878f4b83e21f16a53c54a62def628e05fd2e96", "reinforcement-learning algorithms", "stable_baselines3.common.base_class", ("BaseAlgorithm",)),
    IntegrationSpec("rllib", "Ray RLlib", "ray-project/ray", None, "distributed reinforcement learning", "ray.rllib"),
    IntegrationSpec("vectorbt", "vectorbt", "polakowo/vectorbt", "dd8eb3a3fe9ed918b1cdaf177455759ae4ac68cb", "high-throughput strategy screening", "vectorbt.portfolio.base", ("Portfolio",)),
    IntegrationSpec("finrlx", "FinRL-Trading", "AI4Finance-Foundation/FinRL-Trading", "4409abe925c904e570be78ebfb5e77ac3491dff8", "target-weight strategy contract and trading patterns", "strategies.base_strategy", ("StrategyResult", "BaseStrategy")),
    IntegrationSpec("riskfolio", "Riskfolio-Lib", "dcajasn/Riskfolio-Lib", "7b1b26ac9760974c12ecefe290a9d3bd37b66b7a", "portfolio optimization and risk measures", "riskfolio", ("Portfolio",)),
    IntegrationSpec("pyportfolioopt", "PyPortfolioOpt", "robertmartin8/PyPortfolioOpt", None, "portfolio optimization and allocation", "pypfopt.efficient_frontier", ("EfficientFrontier",)),
    IntegrationSpec("nautilus", "NautilusTrader", "nautechsystems/nautilus_trader", "2ebdbd71da1511c0bf5e808915a79e55a1e877e4", "event-driven backtest, portfolio, risk, paper/live execution runtime", "nautilus_trader"),
)


def probe(spec: IntegrationSpec) -> dict[str, Any]:
    result: dict[str, Any] = asdict(spec)
    try:
        module = importlib.import_module(spec.python_module)
    except Exception as exc:
        result.update(installed=False, import_ok=False, symbols={}, error=f"{type(exc).__name__}: {exc}")
        return result

    symbols: dict[str, bool] = {name: hasattr(module, name) for name in spec.symbols}
    result.update(installed=True, import_ok=all(symbols.values()) if symbols else True, symbols=symbols, error=None, module_file=getattr(module, "__file__", None), module_version=getattr(module, "__version__", None))
    return result


def probe_all() -> list[dict[str, Any]]:
    return [probe(spec) for spec in SPECS]
