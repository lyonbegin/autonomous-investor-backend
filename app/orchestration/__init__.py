"""Thin cross-engine orchestration.

Upstream engines keep their native lifecycle. Modules here only translate
validated native outputs at explicit engine boundaries.
"""

from .research import merge_finrobot_result, research_bundle_from_tradingagents
from .allocation import (
    target_portfolio_from_finrl,
    target_portfolio_from_mapping,
    target_portfolio_from_riskfolio,
)

__all__ = [
    "research_bundle_from_tradingagents",
    "merge_finrobot_result",
    "target_portfolio_from_finrl",
    "target_portfolio_from_mapping",
    "target_portfolio_from_riskfolio",
]
