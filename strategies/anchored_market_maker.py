"""Anchored market making around a constant fair value.

The pattern that pays for itself in almost every Prosperity round:

1. **Take** anything on the wrong side of fair value.
2. **Quote** what is left of your position limit one tick inside the touch,
   bounded so you never quote through fair.
3. **Skew** both quotes against your inventory so the book pulls you flat.

The fair value here is a constant because Round-1 osmium genuinely has one
(see ``figures/r1_osmium_anchor.png``). Everything else generalises.
"""
from typing import Dict, List, Tuple

try:  # competition environment
    from datamodel import Order, OrderDepth, TradingState
except ImportError:  # local replay
    from research.datamodel import Order, OrderDepth, TradingState

PRODUCT = "ASH_COATED_OSMIUM"
POSITION_LIMIT = 80
FAIR_VALUE = 10_000

TAKE_EDGE = 0        # take asks strictly below fair, bids strictly above
QUOTE_STEP = 1       # ticks improvement on the touch
INVENTORY_SKEW = 0.06  # ticks of quote shift per unit of inventory
MIN_EDGE = 1         # never quote inside +/- MIN_EDGE of fair


def wall_mid(depth: OrderDepth) -> float:
    """Mid of the deepest level on each side - far less noisy than the touch."""
    bid = max(depth.buy_orders.items(), key=lambda kv: kv[1])[0]
    ask = max(depth.sell_orders.items(), key=lambda kv: -kv[1])[0]
    return (bid + ask) / 2.0


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

    bid_px = int(min(best_bid + QUOTE_STEP, fair - MIN_EDGE) - skew)
    ask_px = int(max(best_ask - QUOTE_STEP, fair + MIN_EDGE) - skew)
    if bid_px >= ask_px:                      # never cross ourselves
        bid_px, ask_px = int(fair - MIN_EDGE), int(fair + MIN_EDGE)

    buy_capacity = max(0, POSITION_LIMIT - position - bought)
    sell_capacity = max(0, POSITION_LIMIT + position - sold)
    if buy_capacity:
        orders.append(Order(PRODUCT, bid_px, buy_capacity))
    if sell_capacity:
        orders.append(Order(PRODUCT, ask_px, -sell_capacity))
    return orders


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        result: Dict[str, List[Order]] = {}
        depth = state.order_depths.get(PRODUCT)
        if depth and depth.buy_orders and depth.sell_orders:
            result[PRODUCT] = make_orders(depth, state.position.get(PRODUCT, 0), FAIR_VALUE)
        return result, 0, ""
