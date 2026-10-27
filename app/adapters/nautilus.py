from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.core.contracts import RiskDecision, TargetPortfolio


@dataclass(frozen=True, slots=True)
class OrderIntent:
    instrument: str
    quantity_delta: float
    target_weight: float
    current_quantity: float
    target_quantity: float


class RebalancePlanner:
    """Translate target weights into unit deltas before entering Nautilus."""

    @staticmethod
    def plan(
        target: TargetPortfolio,
        *,
        equity: float,
        prices: Mapping[str, float],
        current_quantities: Mapping[str, float] | None = None,
    ) -> list[OrderIntent]:
        current_quantities = current_quantities or {}
        intents: list[OrderIntent] = []
        for item in target.weights:
            price = float(prices[item.instrument])
            if price <= 0:
                raise ValueError(f"non-positive price for {item.instrument}: {price}")
            current = float(current_quantities.get(item.instrument, 0.0))
            target_quantity = equity * float(item.weight) / price
            delta = target_quantity - current
            intents.append(
                OrderIntent(
                    instrument=item.instrument,
                    quantity_delta=delta,
                    target_weight=float(item.weight),
                    current_quantity=current,
                    target_quantity=target_quantity,
                )
            )
        return intents


class NautilusAdapter:
    """Submit pre-approved OrderIntents through Nautilus Strategy APIs.

    This follows Nautilus' native path:
    Strategy.order_factory.market(...) -> Strategy.submit_order(...).
    Nautilus' RiskEngine remains in that native execution path.
    """

    @staticmethod
    def submit_market_intents(strategy: Any, intents: list[OrderIntent]) -> list[Any]:
        from nautilus_trader.model import InstrumentId, OrderSide

        submitted: list[Any] = []
        for intent in intents:
            if intent.quantity_delta == 0:
                continue
            instrument_id = InstrumentId.from_str(intent.instrument)
            instrument = strategy.cache.instrument(instrument_id)
            if instrument is None:
                raise LookupError(f"Nautilus instrument not found in cache: {intent.instrument}")

            side = OrderSide.BUY if intent.quantity_delta > 0 else OrderSide.SELL
            quantity = instrument.make_qty(abs(intent.quantity_delta))
            order = strategy.order_factory.market(
                instrument_id=instrument_id,
                order_side=side,
                quantity=quantity,
            )
            strategy.submit_order(order)
            submitted.append(order)
        return submitted

    @staticmethod
    def plan_approved(
        decision: RiskDecision,
        *,
        equity: float,
        prices: Mapping[str, float],
        current_quantities: Mapping[str, float] | None = None,
    ) -> list[OrderIntent]:
        if not decision.approved:
            raise PermissionError("RiskDecision is not approved")
        return RebalancePlanner.plan(
            decision.target,
            equity=equity,
            prices=prices,
            current_quantities=current_quantities,
        )
