"""Source-faithful cross-engine coordinators.

These coordinators never replace an upstream engine's internal lifecycle.
They only call validated bridge entry points and translate data at the
explicit boundaries already covered by unit/integration tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.core.contracts import OrderIntent, ResearchBundle, TargetPortfolio
from app.orchestration.research import (
    merge_finrobot_result,
    research_bundle_from_tradingagents,
)
from app.orchestration.rdagent import inject_research_into_rdagent
from app.orchestration.runtime import plan_rebalance


@dataclass(slots=True)
class ResearchFlowResult:
    bundle: ResearchBundle
    tradingagents_signal: str
    finrobot_result: Any | None = None


class ResearchCoordinator:
    """TradingAgents -> ResearchBundle -> optional FinRobot enrichment."""

    def __init__(self, tradingagents: Any, finrobot: Any | None = None) -> None:
        self.tradingagents = tradingagents
        self.finrobot = finrobot

    async def run(
        self,
        instrument: str,
        trade_date: str,
        *,
        asset_type: str = "stock",
        portfolio: Any | None = None,
        run_finrobot: bool = True,
    ) -> ResearchFlowResult:
        native = self.tradingagents.run(
            instrument,
            trade_date,
            asset_type=asset_type,
            portfolio=portfolio,
        )
        bundle = research_bundle_from_tradingagents(
            native.final_state,
            instrument=instrument,
        )

        # Preserve TradingAgents' native final signal as attributed upstream data.
        first = bundle.evidence[0]
        payload = dict(first.payload)
        payload["native_signal"] = native.signal
        bundle = bundle.model_copy(
            update={
                "evidence": [
                    first.model_copy(update={"payload": payload}),
                    *bundle.evidence[1:],
                ]
            }
        )

        finrobot_result = None
        if run_finrobot and self.finrobot is not None:
            finrobot_result = await self.finrobot.research(instrument)
            bundle = merge_finrobot_result(bundle, finrobot_result, pipeline="research")

        return ResearchFlowResult(
            bundle=bundle,
            tradingagents_signal=native.signal,
            finrobot_result=finrobot_result,
        )


class RDAgentCoordinator:
    """Inject external research into RD-Agent's native ExperimentPlan path."""

    def __init__(self, rdagent: Any) -> None:
        self.rdagent = rdagent

    def inject_research(self, bundle: ResearchBundle) -> None:
        inject_research_into_rdagent(self.rdagent.loop, bundle)

    async def run(
        self,
        bundle: ResearchBundle,
        *,
        step_n: int | None = None,
        loop_n: int | None = None,
        all_duration: str | None = None,
        base_features_path: str | None = None,
    ) -> Any:
        self.inject_research(bundle)
        return await self.rdagent.run(
            step_n=step_n,
            loop_n=loop_n,
            all_duration=all_duration,
            base_features_path=base_features_path,
        )


@dataclass(slots=True)
class ExecutionFlowResult:
    target: TargetPortfolio
    intents: list[OrderIntent]
    native_orders: list[Any]


class NautilusExecutionCoordinator:
    """TargetPortfolio -> OrderIntent -> native Nautilus market orders."""

    def __init__(self, nautilus: Any) -> None:
        self.nautilus = nautilus

    def plan(
        self,
        target: TargetPortfolio,
        *,
        equity: float,
        prices: Mapping[str, float],
        current_quantities: Mapping[str, float] | None = None,
        min_notional: float = 0.0,
    ) -> list[OrderIntent]:
        return plan_rebalance(
            target,
            equity=equity,
            prices=prices,
            current_quantities=current_quantities,
            min_notional=min_notional,
        )

    def submit(
        self,
        strategy: Any,
        target: TargetPortfolio,
        *,
        equity: float,
        prices: Mapping[str, float],
        current_quantities: Mapping[str, float] | None = None,
        min_notional: float = 0.0,
        instrument_id_map: Mapping[str, str] | None = None,
    ) -> ExecutionFlowResult:
        intents = self.plan(
            target,
            equity=equity,
            prices=prices,
            current_quantities=current_quantities,
            min_notional=min_notional,
        )
        native_ids = dict(instrument_id_map or {})
        missing = [intent.instrument for intent in intents if intent.instrument not in native_ids]
        if instrument_id_map is not None and missing:
            raise KeyError(f"missing Nautilus InstrumentId mapping for: {sorted(missing)}")

        orders = [
            self.nautilus.submit_market_intent(
                strategy,
                intent,
                native_instrument_id=native_ids.get(intent.instrument),
            )
            for intent in intents
        ]
        return ExecutionFlowResult(
            target=target,
            intents=intents,
            native_orders=orders,
        )

@dataclass(slots=True)
class QuantFlowResult:
    qlib_scores: list[Any]
    chronos_forecasts: list[Any]
    sb3_action: Any | None = None
    rllib_output: Any | None = None


class QuantCoordinator:
    """Keep Qlib, Chronos, SB3 and RLlib outputs distinct and attributable."""

    def __init__(
        self,
        *,
        qlib: Any | None = None,
        chronos: Any | None = None,
        sb3: Any | None = None,
        rllib: Any | None = None,
    ) -> None:
        self.qlib = qlib
        self.chronos = chronos
        self.sb3 = sb3
        self.rllib = rllib

    def qlib_scores(
        self,
        model: Any,
        dataset: Any,
        *,
        model_id: str,
        segment: Any = "test",
    ) -> list[Any]:
        if self.qlib is None:
            raise RuntimeError("Qlib bridge is not configured")
        from app.orchestration.quant import model_scores_from_qlib

        native = self.qlib.predict(model, dataset, segment=segment)
        return model_scores_from_qlib(native, model_id=model_id)

    def chronos_forecasts(
        self,
        frame: Any,
        *,
        model_id: str,
        horizon: str,
        **predict_kwargs: Any,
    ) -> list[Any]:
        if self.chronos is None:
            raise RuntimeError("Chronos bridge is not configured")
        from app.orchestration.quant import forecasts_from_chronos_df

        native = self.chronos.predict_df(frame, **predict_kwargs)
        return forecasts_from_chronos_df(native, model_id=model_id, horizon=horizon)

    def sb3_action(
        self,
        model: Any,
        observation: Any,
        *,
        policy_id: str,
        instrument_scope: list[str] | None = None,
        deterministic: bool = True,
    ) -> Any:
        if self.sb3 is None:
            raise RuntimeError("SB3 bridge is not configured")
        from app.orchestration.quant import policy_action

        native = self.sb3.predict(model, observation, deterministic=deterministic)
        action = native[0] if isinstance(native, tuple) else native
        return policy_action(
            action,
            policy_id=policy_id,
            instrument_scope=instrument_scope or [],
            metadata={"source": "Stable-Baselines3"},
        )

    def rllib_inference(
        self,
        algorithm: Any,
        batch: Any,
        *,
        module_id: str | None = None,
    ) -> Any:
        if self.rllib is None:
            raise RuntimeError("RLlib bridge is not configured")
        return self.rllib.forward_inference(
            algorithm,
            batch,
            module_id=module_id,
        )

class AllocationCoordinator:
    """Run native allocation engines and map only their explicit weight outputs."""

    def __init__(
        self,
        *,
        finrl: Any | None = None,
        riskfolio: Any | None = None,
        pypfopt: Any | None = None,
    ) -> None:
        self.finrl = finrl
        self.riskfolio = riskfolio
        self.pypfopt = pypfopt

    def from_finrl(
        self,
        strategy: Any,
        data: dict[str, Any],
        *,
        as_of: Any = None,
        target_date: str | None = None,
        cash_weight: float = 0.0,
    ) -> TargetPortfolio:
        if self.finrl is None:
            raise RuntimeError("FinRL bridge is not configured")
        from app.orchestration.allocation import target_portfolio_from_finrl

        native = self.finrl.generate_weights(
            strategy,
            data,
            target_date=target_date,
        )
        return target_portfolio_from_finrl(
            native,
            as_of=as_of,
            cash_weight=cash_weight,
        )

    def from_riskfolio(
        self,
        returns: Any,
        *,
        strategy_id: str,
        as_of: Any = None,
        estimate_kwargs: dict[str, Any] | None = None,
        optimize_kwargs: dict[str, Any] | None = None,
        cash_weight: float = 0.0,
    ) -> TargetPortfolio:
        if self.riskfolio is None:
            raise RuntimeError("Riskfolio bridge is not configured")
        from app.orchestration.allocation import target_portfolio_from_riskfolio

        portfolio = self.riskfolio.portfolio(returns)
        self.riskfolio.estimate(portfolio, **(estimate_kwargs or {}))
        native = self.riskfolio.optimize(portfolio, **(optimize_kwargs or {}))
        return target_portfolio_from_riskfolio(
            native,
            strategy_id=strategy_id,
            as_of=as_of,
            cash_weight=cash_weight,
        )

    def from_pypfopt(
        self,
        expected_returns: Any,
        cov_matrix: Any,
        *,
        strategy_id: str,
        as_of: Any = None,
        objective: str = "min_volatility",
        objective_kwargs: dict[str, Any] | None = None,
        frontier_kwargs: dict[str, Any] | None = None,
        cash_weight: float = 0.0,
    ) -> TargetPortfolio:
        if self.pypfopt is None:
            raise RuntimeError("PyPortfolioOpt bridge is not configured")
        from app.orchestration.allocation import target_portfolio_from_mapping

        frontier = self.pypfopt.efficient_frontier(
            expected_returns,
            cov_matrix,
            **(frontier_kwargs or {}),
        )
        kwargs = objective_kwargs or {}
        if objective == "min_volatility":
            self.pypfopt.min_volatility(frontier)
        elif objective == "max_sharpe":
            self.pypfopt.max_sharpe(frontier, **kwargs)
        else:
            raise ValueError(f"unsupported PyPortfolioOpt objective: {objective}")

        weights = self.pypfopt.clean_weights(frontier)
        return target_portfolio_from_mapping(
            weights,
            strategy_id=strategy_id,
            as_of=as_of,
            cash_weight=cash_weight,
            metadata={"source": "PyPortfolioOpt", "objective": objective},
        )
