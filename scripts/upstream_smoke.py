from __future__ import annotations

import importlib

CHECKS = {
    "TradingAgents": ("tradingagents.graph.trading_graph", ("TradingAgentsGraph",)),
    "FinRobot": ("finrobot", ("FinRobot",)),
    "RD-Agent": ("rdagent.app.qlib_rd_loop.quant", ("QuantRDLoop",)),
    "Qlib": ("qlib.model.base", ("BaseModel",)),
    "Chronos": ("chronos", ("BaseChronosPipeline",)),
    "Stable-Baselines3": ("stable_baselines3.common.base_class", ("BaseAlgorithm",)),
    "RLlib": ("ray.rllib.algorithms.algorithm", ("Algorithm", "AlgorithmConfig")),
    "vectorbt": ("vectorbt.portfolio.base", ("Portfolio",)),
    "FinRL-Trading": ("strategies.base_strategy", ("StrategyResult", "BaseStrategy")),
    "Riskfolio-Lib": ("riskfolio", ("Portfolio",)),
    "PyPortfolioOpt": ("pypfopt.efficient_frontier", ("EfficientFrontier",)),
    "NautilusTrader": ("nautilus_trader", ()),
}

failed = []
for name, (module_name, symbols) in CHECKS.items():
    try:
        module = importlib.import_module(module_name)
        missing = [symbol for symbol in symbols if not hasattr(module, symbol)]
        if missing:
            failed.append(f"{name}: missing {missing} in {module_name}")
            print("FAIL", name, module_name, missing)
        else:
            print("OK", name, module_name, getattr(module, "__file__", None))
    except Exception as exc:
        failed.append(f"{name}: {type(exc).__name__}: {exc}")
        print("FAIL", name, type(exc).__name__, exc)

for adapter in (
    "app.adapters.tradingagents",
    "app.adapters.finrobot",
    "app.adapters.rdagent",
    "app.adapters.qlib",
    "app.adapters.chronos",
    "app.adapters.sb3",
    "app.adapters.rllib",
    "app.adapters.finrl",
    "app.adapters.portfolio",
    "app.adapters.nautilus",
):
    importlib.import_module(adapter)
    print("ADAPTER_OK", adapter)

if failed:
    raise SystemExit("\n".join(failed))
