"""Validated integration bridges for the autonomous investor backend."""

from .tradingagents import TradingAgentsBridge, TradingAgentsRun
from .finrobot import FinRobotBridge
from .rdagent import RDAgentQuantBridge
from .qlib import QlibBridge
from .chronos import ChronosBridge
from .sb3 import StableBaselinesBridge
from .rllib import RLlibBridge
from .vectorbt import VectorBTBridge
from .finrl import FinRLBridge
from .riskfolio import RiskfolioBridge
from .pypfopt import PyPortfolioOptBridge
from .nautilus import NautilusBridge

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
    "FinRLBridge",
    "RiskfolioBridge",
    "PyPortfolioOptBridge",
    "NautilusBridge",
]
