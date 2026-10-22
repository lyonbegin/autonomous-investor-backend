"""Thin integration bridges for validated upstream engines.

These modules deliberately do not reimplement upstream internals. Each bridge
keeps the upstream project's canonical programmatic entry point intact and only
adapts our caller to that entry point.
"""

from .tradingagents_bridge import TradingAgentsBridge, TradingAgentsRun
from .finrobot_bridge import FinRobotBridge
from .rdagent_bridge import RDAgentQuantBridge
from .qlib_bridge import QlibBridge
from .chronos_bridge import ChronosBridge
from .sb3_bridge import StableBaselinesBridge
from .rllib_bridge import RLlibBridge
from .vectorbt_bridge import VectorBTBridge
from .finrl_bridge import FinRLBridge
from .riskfolio_bridge import RiskfolioBridge
from .pypfopt_bridge import PyPortfolioOptBridge
from .nautilus_bridge import NautilusBridge

__all__ = [
    "TradingAgentsBridge",
    "TradingAgentsRun",
    "FinRobotBridge",
    "RDAgentQuantBridge",
    "QlibBridge",
    "ChronosBridge",
    "StableBaselinesBridge",
    "RLlibBridge",
    "VectorBTBridge",
    "PyPortfolioOptBridge",
    "NautilusBridge",
    "RiskfolioBridge",
    "FinRLBridge",
]
