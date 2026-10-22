"""Plan target-weight rebalances and hand native order construction to NautilusTrader."""

from __future__ import annotations

from typing import Mapping

from app.core.contracts import OrderIntent, TargetPortfolio


def plan_rebalance(
    target: TargetPortfolio,
    *,
    equity: float,
    prices: Mapping[str, float],
    current_quantities: Mapping[str, float] | None = None,
    min_notional: float = 0.0,
) -> list[OrderIntent]:
    """Convert target weights to quantity deltas using current marks.

    This planner deliberately does not round quantities. Nautilus instrument
    metadata owns quantity precision/lot normalization through instrument.make_qty().
    """

    if equity <= 0:
        raise ValueError("equity must be positive")
    if min_notional < 0:
        raise ValueError("min_notional must be non-negative")

    current = {str(k): float(v) for k, v in (current_quantities or {}).items()}
    target_weights = {row.instrument: float(row.weight) for row in target.weights}
    instruments = sorted(set(target_weights) | set(current))

    intents: list[OrderIntent] = []
    for instrument in instruments:
        if instrument not in prices:
            raise KeyError(f"missing reference price for {instrument}")
        price = float(prices[instrument])
        if price <= 0:
            raise ValueError(f"reference price must be positive for {instrument}")

        target_weight = target_weights.get(instrument, 0.0)
        current_qty = current.get(instrument, 0.0)
        target_notional = equity * target_weight
        target_qty = target_notional / price
        delta = target_qty - current_qty
        notional_delta = delta * price

        if delta == 0.0 or abs(notional_delta) < min_notional:
            continue

        intents.append(
            OrderIntent(
                instrument=instrument,
                side="buy" if delta > 0 else "sell",
                quantity=abs(delta),
                target_weight=target_weight,
                current_quantity=current_qty,
                target_quantity=target_qty,
                reference_price=price,
                notional_delta=notional_delta,
                metadata={
                    "strategy_id": target.strategy_id,
                    "target_as_of": target.as_of.isoformat(),
                    "source": "TargetPortfolio",
                },
            )
        )

    return intents
