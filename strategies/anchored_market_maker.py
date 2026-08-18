"""Anchored market making around a constant fair value.

The pattern that pays for itself in almost every Prosperity round:

1. **Take** anything on the wrong side of fair value.
2. **Quote** what is left of your position limit one tick inside the touch,
   bounded so you never quote through fair.
3. **Skew** both quotes against your inventory so the book pulls you flat.

The fair value here is a constant because Round-1 osmium genuinely has one:
the AR(1) mean is 9,998.2 / 10,000.8 / 10,001.6 across the three sample days
(see ``figures/r1_osmium_anchor.png``). Everything else generalises.

A constant is still a risk, though: the scored day is out of sample by
construction, and hard-coding 10,000 with no fallback means a single
mis-estimated anchor pins inventory at the limit for the entire day with no
way to recover mid-round. So the anchor carries the fail-safe the write-up
prescribes rather than a better estimate: if inventory sits at the limit for
more than ``PIN_TICKS`` snapshots, blend the assumed fair value toward the
observed *wall* mid until it unpins. That is the only thing the wall mid is
used for here - the point of osmium is that you do not have to estimate the
level, only to notice when your assumed level is wrong.
"""
from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, TradingState

import jsonpickle

PRODUCT = "ASH_COATED_OSMIUM"
POSITION_LIMIT = 80
FAIR_VALUE = 10_000

TAKE_EDGE = 0        # take asks strictly below fair, bids strictly above
QUOTE_STEP = 1       # ticks improvement on the touch
INVENTORY_SKEW = 0.06  # ticks of quote shift per unit of inventory
MIN_EDGE = 1         # never quote inside +/- MIN_EDGE of fair

PIN_TICKS = 300      # snapshots stuck at the limit before we distrust the anchor
BLEND_RATE = 0.01    # per-snapshot pull of the assumed fair toward the wall mid


def wall_mid(depth: OrderDepth) -> float:
    """Mid of the deepest level on each side - far less noisy than the touch."""
    bid = max(depth.buy_orders.items(), key=lambda kv: kv[1])[0]
    ask = max(depth.sell_orders.items(), key=lambda kv: -kv[1])[0]
    return (bid + ask) / 2.0


def _floor(x: float) -> int:
    return int(x // 1)


def _ceil(x: float) -> int:
    return -int((-x) // 1)


def make_orders(depth: OrderDepth, position: int, fair: float) -> List[Order]:
    orders: List[Order] = []
    pos = position
    bought = sold = 0

    # ---- 1. take everything through fair --------------------------------- #
    for ask in sorted(depth.sell_orders):
        if ask >= fair - TAKE_EDGE:
            break
        qty = min(-depth.sell_orders[ask], POSITION_LIMIT - pos)
        if qty > 0:
            orders.append(Order(PRODUCT, ask, qty))
            pos += qty
            bought += qty

    for bid in sorted(depth.buy_orders, reverse=True):
        if bid <= fair + TAKE_EDGE:
            break
        qty = min(depth.buy_orders[bid], POSITION_LIMIT + pos)
        if qty > 0:
            orders.append(Order(PRODUCT, bid, -qty))
            pos -= qty
            sold += qty

    # ---- 2. quote the rest ----------------------------------------------- #
    skew = INVENTORY_SKEW * position
    best_bid = max(depth.buy_orders) if depth.buy_orders else fair - 8
    best_ask = min(depth.sell_orders) if depth.sell_orders else fair + 8

    # Floor the bid and ceil the ask. Rounding both the same way silently eats
    # the inventory skew on one side of the book.
    bid_px = _floor(min(best_bid + QUOTE_STEP, fair - MIN_EDGE) - skew)
    ask_px = _ceil(max(best_ask - QUOTE_STEP, fair + MIN_EDGE) - skew)
    if bid_px >= ask_px:                      # never cross ourselves
        bid_px, ask_px = _floor(fair - MIN_EDGE), _ceil(fair + MIN_EDGE)

    # Capacity is checked per side against the *current* position: the takes
    # above may not fill, so a resting order sized off the post-take position
    # can breach the limit on its own.
    buy_capacity = max(0, POSITION_LIMIT - position - bought)
    sell_capacity = max(0, POSITION_LIMIT + position - sold)
    if buy_capacity:
        orders.append(Order(PRODUCT, bid_px, buy_capacity))
    if sell_capacity:
        orders.append(Order(PRODUCT, ask_px, -sell_capacity))
    return orders


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        try:
            store = jsonpickle.decode(state.traderData) if state.traderData else {}
        except Exception:
            store = {}

        result: Dict[str, List[Order]] = {}
        depth = state.order_depths.get(PRODUCT)
        if not (depth and depth.buy_orders and depth.sell_orders):
            return result, 0, jsonpickle.encode(store)

        position = state.position.get(PRODUCT, 0)

        # ---- fail-safe: a book we cannot get out of means the anchor, not the
        # market, is wrong.
        pinned = store.get("pinned", 0) + 1 if abs(position) >= POSITION_LIMIT else 0
        store["pinned"] = pinned
        if pinned > PIN_TICKS:
            assumed = store.get("fair", float(FAIR_VALUE))
            fair = (1 - BLEND_RATE) * assumed + BLEND_RATE * wall_mid(depth)
        else:
            fair = float(FAIR_VALUE)          # unpinned: snap back to the anchor
        store["fair"] = fair

        result[PRODUCT] = make_orders(depth, position, fair)
        return result, 0, jsonpickle.encode(store)
