"""Expressing a mean-reversion view on the underlying through the option chain.

Round-3 velvetfruit reverts around 5,250 with a deviation standard deviation of
15.6 ticks and a half-life of ~377 snapshots. Every voucher is that deviation
multiplied by its delta, so the chain is a set of leveraged expressions of one
view rather than a set of independent instruments.

Why not cross-strike relative value? Because it does not clear the spread. For
the 5000/5400 pair, regressing out the underlying cuts sigma from 12.5 ticks to
1.7, and around its own EWMA mean the residual disperses by only **0.64 ticks**
against an **executable width of 7.42** - eleven times the whole signal. Quoting
instead of taking is not an escape either: `VEV_5000` printed one unit in three
sample days, so the leg with width has no flow and the leg with flow has no
width (``figures/r3_pair_beta_hedge.png``, ``figures/r3_voucher_chain.png``).

So the signal here is the underlying's deviation, and the second leg is a cheap
high strike used to damp the outright delta rather than a relative-value partner.

Three things this file is written to demonstrate:

* the entry test is applied to the price you can actually trade at - the
  ``beta * (S - anchor)`` term appears on *both* sides of the comparison. Mixing
  a raw executable spread with a delta-adjusted reference silently turns the rule
  into a directional one;
* the reference level is an EWMA, not a constant, because the surface re-prices
  as time to expiry shrinks (the hedged residual's own mean walks 3 ticks across
  three sample days);
* both legs are sent in the same tick at prices already resting, so a fill on one
  leg without the other is impossible.
"""
from typing import Dict, List, Tuple

try:
    from datamodel import Order, OrderDepth, TradingState
except ImportError:
    from research.datamodel import Order, OrderDepth, TradingState

import jsonpickle

LEG = "VEV_5000"        # the strike carrying the delta
OFFSET = "VEV_5400"     # cheap high strike, damps the outright delta
SPOT = "VELVETFRUIT_EXTRACT"

ANCHOR = 5_250.0        # velvetfruit's mean-reversion level
BETA = 0.79             # Delta(LEG) - Delta(OFFSET), read off the delta ladder
ENTRY = 23.0            # ticks of |S - ANCHOR| required to open
EXIT = 4.0              # ticks of |S - ANCHOR| at which to close
EWMA_SPAN = 500         # snapshots
POS_LIMIT = 150         # units of the combination
LEG_LIMIT = 300


def touch(d: OrderDepth) -> Tuple[int, int]:
    return max(d.buy_orders), min(d.sell_orders)


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        store = {}
        if state.traderData:
            try:
                store = jsonpickle.decode(state.traderData)
            except Exception:
                store = {}

        depths = {p: state.order_depths.get(p) for p in (LEG, OFFSET, SPOT)}
        if any(d is None or not d.buy_orders or not d.sell_orders for d in depths.values()):
            return {}, 0, jsonpickle.encode(store)

        a_bid, a_ask = touch(depths[LEG])
        b_bid, b_ask = touch(depths[OFFSET])
        s_bid, s_ask = touch(depths[SPOT])
        s_mid = (s_bid + s_ask) / 2.0

        # The combination's fair level, tracked rather than assumed: the surface
        # re-prices as time to expiry shrinks, so a fixed constant decays.
        fair = ((a_bid + a_ask) / 2.0 - (b_bid + b_ask) / 2.0) - BETA * (s_mid - ANCHOR)
        alpha = 2.0 / (EWMA_SPAN + 1.0)
        ref = store.get("ref")
        ref = fair if ref is None else alpha * fair + (1 - alpha) * ref
        store["ref"] = ref

        # The signal is the underlying, not the cross-strike residual.
        dev = s_mid - ANCHOR
        pos = int(store.get("pos", 0))
        pos_a = state.position.get(LEG, 0)
        pos_b = state.position.get(OFFSET, 0)
        orders: Dict[str, List[Order]] = {}

        # Executable prices, delta-adjusted on the same footing as `ref`.
        cost_to_buy = a_ask - b_bid - BETA * dev
        rev_to_sell = a_bid - b_ask - BETA * dev

        def send(px_a, qty_a, px_b, qty_b):
            orders.setdefault(LEG, []).append(Order(LEG, px_a, qty_a))
            orders.setdefault(OFFSET, []).append(Order(OFFSET, px_b, qty_b))

        if dev <= -ENTRY and cost_to_buy <= ref:
            # underlying is cheap: buy delta, offset with the high strike
            q = min(-depths[LEG].sell_orders[a_ask], depths[OFFSET].buy_orders[b_bid],
                    POS_LIMIT - pos, LEG_LIMIT - pos_a, LEG_LIMIT + pos_b)
            if q > 0:
                send(a_ask, q, b_bid, -q)
                store["pos"] = pos + q
        elif dev >= ENTRY and rev_to_sell >= ref:
            q = min(depths[LEG].buy_orders[a_bid], -depths[OFFSET].sell_orders[b_ask],
                    POS_LIMIT + pos, LEG_LIMIT + pos_a, LEG_LIMIT - pos_b)
            if q > 0:
                send(a_bid, -q, b_ask, q)
                store["pos"] = pos - q
        elif pos > 0 and dev >= -EXIT:
            q = min(pos, depths[LEG].buy_orders[a_bid], -depths[OFFSET].sell_orders[b_ask])
            if q > 0:
                send(a_bid, -q, b_ask, q)
                store["pos"] = pos - q
        elif pos < 0 and dev <= EXIT:
            q = min(-pos, -depths[LEG].sell_orders[a_ask], depths[OFFSET].buy_orders[b_bid])
            if q > 0:
                send(a_ask, q, b_bid, -q)
                store["pos"] = pos + q

        return orders, 0, jsonpickle.encode(store)
