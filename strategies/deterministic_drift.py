from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, TradingState

PRODUCT = "INTARIAN_PEPPER_ROOT"
POSITION_LIMIT = 80

DRIFT_PER_TICK = 1e-3
BASE_FAIR = 12_000.0
DAY_STEP = 1_000.0
DAY = 0
TARGET_INVENTORY = 76
ENTRY_PREMIUM = 12
BID_EDGE = 2
ASK_EDGE = 15
INVENTORY_SKEW = 0.0


def fair_value(timestamp: int) -> float:
    return BASE_FAIR + DAY_STEP * DAY + DRIFT_PER_TICK * timestamp


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        result: Dict[str, List[Order]] = {}
        depth = state.order_depths.get(PRODUCT)
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return result, 0, ""

        pos = state.position.get(PRODUCT, 0)
        fair = fair_value(state.timestamp)
        orders: List[Order] = []
        working = pos
        bought = sold = 0

        take_limit = fair + (ENTRY_PREMIUM if working < TARGET_INVENTORY else 0)
        for ask in sorted(depth.sell_orders):
            if ask >= take_limit or working >= TARGET_INVENTORY:
                break
            qty = min(-depth.sell_orders[ask], TARGET_INVENTORY - working)
            if qty > 0:
                orders.append(Order(PRODUCT, int(ask), qty))
                working += qty
                bought += qty

        for bid in sorted(depth.buy_orders, reverse=True):
            if bid <= fair + ASK_EDGE:
                break
            qty = min(depth.buy_orders[bid], POSITION_LIMIT + working)
            if qty > 0:
                orders.append(Order(PRODUCT, int(bid), -qty))
                working -= qty
                sold += qty

        skew = INVENTORY_SKEW * (pos - TARGET_INVENTORY)
        bid_px = int((fair - BID_EDGE - skew) // 1)
        ask_px = -int((-(fair + ASK_EDGE - skew)) // 1)

        buy_capacity = max(0, TARGET_INVENTORY - pos - bought)
        sell_capacity = max(0, POSITION_LIMIT + pos - sold)
        if buy_capacity:
            orders.append(Order(PRODUCT, bid_px, buy_capacity))
        if sell_capacity:
            orders.append(Order(PRODUCT, ask_px, -sell_capacity))

        result[PRODUCT] = orders
        return result, 0, ""
