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
one sample day showed up on another (`ROBOT_IRONING`: 56 jumps on day 2, none on
day 4; `ROBOT_DISHES`: the reverse), so hard-coding the product list would have
been a bet on which day we were given.

Generic does not mean unconditional, though, and this is where the decoy lives.
`PEBBLES_XL` prints 261 moves of ±100 across three days - *more* than most of the
genuine lattice products - and alternates at 50.4%. It is a volatile product
whose moves happen to be large, not a lattice, and a detector that arms on jump
size alone puts it straight into the basket and loses money on it. So the arming
test is the mechanism itself, asked as three questions of the tape and answered
per product, online, with no allowlist:

1. is the price *pinned* to multiples of 100? (85% of `ROBOT_DISHES` snapshots)
2. are the moves *exactly* ±100? (98-102 at the 1st-99th percentile)
3. does the sign *alternate*? (87.3% against `PEBBLES_XL`'s 50.4%)

Question 2 is the entry filter; 1 and 3 are the arming filters, and both need a
warm-up before they mean anything - so the product is market-made passively
until it has earned the right to be traded as a lattice.
"""
from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, TradingState

import jsonpickle

POSITION_LIMIT = 10
LATTICE = 100.0
JUMP_MIN = 0.8 * LATTICE         # tolerate a couple of ticks of quote noise
JUMP_MAX = 1.2 * LATTICE         # ...but a 300-tick move is not a grid crossing
LATTICE_TOL = 5.0                # how close to a grid line counts as "pinned"
PINNED_MIN = 0.5                 # share of snapshots on the grid before arming
MIN_SNAPSHOTS = 200              # warm-up for the pinning test
ALTERNATION_MIN = 0.6            # share of jumps that reverse the previous one
MIN_JUMPS = 20                   # warm-up for the alternation test
PASSIVE_EDGE = 1                 # ticks inside the touch when idle


def off_lattice(mid: float) -> float:
    """Distance from the nearest multiple of LATTICE."""
    r = mid % LATTICE
    return min(r, LATTICE - r)


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        try:
            store = jsonpickle.decode(state.traderData) if state.traderData else {}
        except Exception:
            store = {}
        book: Dict[str, dict] = store.get("b", {})

        result: Dict[str, List[Order]] = {}
        for product, depth in state.order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                continue
            best_bid, best_ask = max(depth.buy_orders), min(depth.sell_orders)
            mid = (best_bid + best_ask) / 2.0

            st = book.setdefault(product, {"n": 0, "p": 0, "j": 0, "a": 0,
                                           "d": None, "m": None})

            # --- question 1: is the price pinned to the grid? ---------------- #
            st["n"] += 1
            if off_lattice(mid) <= LATTICE_TOL:
                st["p"] += 1

            # --- question 2: is this move exactly one grid step? ------------- #
            if st["m"] is not None:
                move = mid - st["m"]
                if JUMP_MIN <= abs(move) <= JUMP_MAX:
                    direction = "up" if move > 0 else "down"
                    # --- question 3: does the sign alternate? ---------------- #
                    if st["d"] is not None:
                        st["j"] += 1
                        if direction != st["d"]:
                            st["a"] += 1
                    st["d"] = direction
            st["m"] = mid

            pinned = st["n"] >= MIN_SNAPSHOTS and st["p"] / st["n"] >= PINNED_MIN
            alternating = st["j"] < MIN_JUMPS or st["a"] / st["j"] >= ALTERNATION_MIN
            armed = pinned and alternating

            pos = state.position.get(product, 0)
            buy_room = POSITION_LIMIT - pos
            sell_room = POSITION_LIMIT + pos
            orders: List[Order] = []

            direction = st["d"] if armed else None
            if direction == "up":
                # crossed up -> expect the crossing back down: get short,
                # aggressively. If we are already fully short there is nothing
                # to do: quoting passively here would buy the position back.
                if sell_room > 0:
                    orders.append(Order(product, best_bid, -sell_room))
            elif direction == "down":
                if buy_room > 0:
                    orders.append(Order(product, best_ask, buy_room))
            else:
                # not a lattice, or no crossing seen yet: quote passively
                spread = best_ask - best_bid
                bid = best_bid + PASSIVE_EDGE if spread > 2 * PASSIVE_EDGE else best_bid
                ask = best_ask - PASSIVE_EDGE if spread > 2 * PASSIVE_EDGE else best_ask
                if buy_room > 0:
                    orders.append(Order(product, bid, buy_room))
                if sell_room > 0:
                    orders.append(Order(product, ask, -sell_room))

            if orders:
                result[product] = orders

        store["b"] = book
        return result, 0, jsonpickle.encode(store)
