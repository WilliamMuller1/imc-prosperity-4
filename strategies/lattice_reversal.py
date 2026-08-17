"""Fade a rounding-lattice crossing.

Some Round-5 mids are the latent price rounded onto a 100-wide grid. A printed
move of exactly ±100 therefore means the latent value has just crossed a grid
boundary, and by a simple martingale argument it is far more likely to cross
back than to keep going: empirically 87% on ROBOT_DISHES
(``figures/r5_lattice.png``).

Two properties make this worth trading where a correlation-based signal is not:

* it comes from a *mechanism* (rounding), not from a p-value, so it is immune
  to the multiple-testing problem that eats most Round-5 "cointegration"; and
* the payoff is asymmetric - a win is ~100 ticks, a loss is bounded by the same
  lattice, and the cost of entry is half a spread (~4 ticks).

The detector is deliberately generic: it is armed for *every* product, not just
the four that showed the pattern in the sample data. A regime that was absent on
one sample day showed up on another, so hard-coding the product list would have
been a bet on which day we were given.
"""
from typing import Dict, List, Tuple

try:
    from datamodel import Order, OrderDepth, TradingState
except ImportError:
    from research.datamodel import Order, OrderDepth, TradingState

import jsonpickle

POSITION_LIMIT = 10
LATTICE = 100.0
JUMP_THRESHOLD = 0.8 * LATTICE   # tolerate a couple of ticks of quote noise
PASSIVE_EDGE = 1                 # ticks inside the touch when idle


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        try:
            store = jsonpickle.decode(state.traderData) if state.traderData else {}
        except Exception:
            store = {}
        prev_mid: Dict[str, float] = store.get("m", {})
        last_jump: Dict[str, str] = store.get("j", {})

        result: Dict[str, List[Order]] = {}
        for product, depth in state.order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                continue
            best_bid, best_ask = max(depth.buy_orders), min(depth.sell_orders)
            mid = (best_bid + best_ask) / 2.0

            if product in prev_mid:
                move = mid - prev_mid[product]
                if move >= JUMP_THRESHOLD:
                    last_jump[product] = "up"
                elif move <= -JUMP_THRESHOLD:
                    last_jump[product] = "down"
            prev_mid[product] = mid

            pos = state.position.get(product, 0)
            buy_room = POSITION_LIMIT - pos
            sell_room = POSITION_LIMIT + pos
            orders: List[Order] = []

            direction = last_jump.get(product)
            if direction == "up" and sell_room > 0:
                # crossed up -> expect the crossing back down: get short, aggressively
                orders.append(Order(product, best_bid, -sell_room))
            elif direction == "down" and buy_room > 0:
                orders.append(Order(product, best_ask, buy_room))
            else:
                # no crossing seen yet on this product today: quote passively
                spread = best_ask - best_bid
                bid = best_bid + PASSIVE_EDGE if spread > 2 * PASSIVE_EDGE else best_bid
                ask = best_ask - PASSIVE_EDGE if spread > 2 * PASSIVE_EDGE else best_ask
                if buy_room > 0:
                    orders.append(Order(product, bid, buy_room))
                if sell_room > 0:
                    orders.append(Order(product, ask, -sell_room))

            if orders:
                result[product] = orders

        store["m"], store["j"] = prev_mid, last_jump
        return result, 0, jsonpickle.encode(store)
