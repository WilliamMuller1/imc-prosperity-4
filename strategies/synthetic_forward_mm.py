from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, TradingState

SPOT = "VELVETFRUIT_EXTRACT"
VOUCHER = "VEV_4000"
STRIKE = 4_000

SPOT_LIMIT = 200
VOUCHER_LIMIT = 300

QUOTE_EDGE = 4
INVENTORY_SKEW = 0.02
MAX_QUOTE_SIZE = 40
HEDGE_RATIO = 1.0
HEDGE = True


def touch(d: OrderDepth) -> Tuple[int, int]:
    return max(d.buy_orders), min(d.sell_orders)


def wall_mid(d: OrderDepth) -> float:
    bid = max(d.buy_orders.items(), key=lambda kv: kv[1])[0]
    ask = max(d.sell_orders.items(), key=lambda kv: -kv[1])[0]
    return (bid + ask) / 2.0


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        d_s = state.order_depths.get(SPOT)
        d_v = state.order_depths.get(VOUCHER)
        if not (d_s and d_v and d_s.buy_orders and d_s.sell_orders
                and d_v.buy_orders and d_v.sell_orders):
            return {}, 0, ""

        s_bid, s_ask = touch(d_s)
        fair = wall_mid(d_s) - STRIKE

        pos_v = state.position.get(VOUCHER, 0)
        pos_s = state.position.get(SPOT, 0)
        skew = INVENTORY_SKEW * pos_v

        orders: Dict[str, List[Order]] = {VOUCHER: []}
        bid_px = int((fair - QUOTE_EDGE - skew) // 1)
        ask_px = -int((-(fair + QUOTE_EDGE - skew)) // 1)

        buy_size = min(MAX_QUOTE_SIZE, VOUCHER_LIMIT - pos_v)
        sell_size = min(MAX_QUOTE_SIZE, VOUCHER_LIMIT + pos_v)
        if buy_size > 0:
            orders[VOUCHER].append(Order(VOUCHER, bid_px, buy_size))
        if sell_size > 0:
            orders[VOUCHER].append(Order(VOUCHER, ask_px, -sell_size))

        if HEDGE:
            target_s = max(-SPOT_LIMIT, min(SPOT_LIMIT, -int(round(HEDGE_RATIO * pos_v))))
            delta = target_s - pos_s
            if delta > 0:
                orders[SPOT] = [Order(SPOT, s_ask, min(delta, -d_s.sell_orders[s_ask]))]
            elif delta < 0:
                orders[SPOT] = [Order(SPOT, s_bid, -min(-delta, d_s.buy_orders[s_bid]))]

        return {k: v for k, v in orders.items() if v}, 0, ""
