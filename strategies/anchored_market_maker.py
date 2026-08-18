from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, TradingState

import jsonpickle

PRODUCT = "ASH_COATED_OSMIUM"
POSITION_LIMIT = 80
FAIR_VALUE = 10_000

TAKE_EDGE = 0
QUOTE_STEP = 1
INVENTORY_SKEW = 0.06
MIN_EDGE = 1

PIN_TICKS = 300
BLEND_RATE = 0.01


def wall_mid(depth: OrderDepth) -> float:
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

    skew = INVENTORY_SKEW * position
    best_bid = max(depth.buy_orders) if depth.buy_orders else fair - 8
    best_ask = min(depth.sell_orders) if depth.sell_orders else fair + 8

    bid_px = _floor(min(best_bid + QUOTE_STEP, fair - MIN_EDGE) - skew)
    ask_px = _ceil(max(best_ask - QUOTE_STEP, fair + MIN_EDGE) - skew)
    if bid_px >= ask_px:
        bid_px, ask_px = _floor(fair - MIN_EDGE), _ceil(fair + MIN_EDGE)

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

        pinned = store.get("pinned", 0) + 1 if abs(position) >= POSITION_LIMIT else 0
        store["pinned"] = pinned
        if pinned > PIN_TICKS:
            assumed = store.get("fair", float(FAIR_VALUE))
            fair = (1 - BLEND_RATE) * assumed + BLEND_RATE * wall_mid(depth)
        else:
            fair = float(FAIR_VALUE)
        store["fair"] = fair

        result[PRODUCT] = make_orders(depth, position, fair)
        return result, 0, jsonpickle.encode(store)
