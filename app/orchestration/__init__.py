"""Thin cross-engine orchestration.

Upstream engines keep their native lifecycle. Modules here only translate
validated native outputs at explicit engine boundaries.
"""

from .research import merge_finrobot_result, research_bundle_from_tradingagents
from .rdagent import (
    hypothesis_from_rdagent,
    inject_research_into_rdagent,
    research_instruction_for_rdagent,
)
from .runtime import plan_rebalance
from .quant import forecasts_from_chronos_df, model_scores_from_qlib, policy_action
from .allocation import (
    target_portfolio_from_finrl,
    target_portfolio_from_mapping,
    target_portfolio_from_riskfolio,
)

__all__ = [
    "research_bundle_from_tradingagents",
    "merge_finrobot_result",
    "research_instruction_for_rdagent",
    "inject_research_into_rdagent",
    "hypothesis_from_rdagent",
    "target_portfolio_from_finrl",
    "target_portfolio_from_mapping",
    "target_portfolio_from_riskfolio",
    "plan_rebalance",
    "policy_action",
    "model_scores_from_qlib",
    "forecasts_from_chronos_df",
]
