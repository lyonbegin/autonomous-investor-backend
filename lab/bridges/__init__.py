"""Thin integration bridges for validated upstream engines.

These modules deliberately do not reimplement upstream internals. Each bridge
keeps the upstream project's canonical programmatic entry point intact and only
adapts our caller to that entry point.
"""

from .tradingagents_bridge import TradingAgentsBridge, TradingAgentsRun
from .finrobot_bridge import FinRobotBridge
from .rdagent_bridge import RDAgentQuantBridge
from .qlib_bridge import QlibBridge

__all__ = [
    "TradingAgentsBridge",
    "TradingAgentsRun",
    "FinRobotBridge",
    "RDAgentQuantBridge",
    "QlibBridge",
]
