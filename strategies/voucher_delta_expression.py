from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, TradingState

import jsonpickle

LEG = "VEV_5000"
OFFSET = "VEV_5400"
SPOT = "VELVETFRUIT_EXTRACT"

ANCHOR = 5_250.0
BETA = 0.79
ENTRY = 23.0
EXIT = 4.0
COST_SLACK = 4.0
EWMA_SPAN = 500
POS_LIMIT = 150
LEG_LIMIT = 300


def touch(d: OrderDepth) -> Tuple[int, int]:
    return max(d.buy_orders), min(d.sell_orders)


def wall_mid(d: OrderDepth) -> float:
    bid = max(d.buy_orders.items(), key=lambda kv: kv[1])[0]
    ask = max(d.sell_orders.items(), key=lambda kv: -kv[1])[0]
    return (bid + ask) / 2.0


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
        s_mid = wall_mid(depths[SPOT])

        fair = ((a_bid + a_ask) / 2.0 - (b_bid + b_ask) / 2.0) - BETA * (s_mid - ANCHOR)
        alpha = 2.0 / (EWMA_SPAN + 1.0)
        ref = store.get("ref")
        ref = fair if ref is None else alpha * fair + (1 - alpha) * ref
        store["ref"] = ref

        dev = s_mid - ANCHOR
        pos = int(store.get("pos", 0))
        pos_a = state.position.get(LEG, 0)
        pos_b = state.position.get(OFFSET, 0)
        orders: Dict[str, List[Order]] = {}

        cost_to_buy = a_ask - b_bid - BETA * dev
        rev_to_sell = a_bid - b_ask - BETA * dev

        def send(px_a, qty_a, px_b, qty_b):
            orders.setdefault(LEG, []).append(Order(LEG, px_a, qty_a))
            orders.setdefault(OFFSET, []).append(Order(OFFSET, px_b, qty_b))

        if dev <= -ENTRY and cost_to_buy <= ref + COST_SLACK:
            q = min(-depths[LEG].sell_orders[a_ask], depths[OFFSET].buy_orders[b_bid],
                    POS_LIMIT - pos, LEG_LIMIT - pos_a, LEG_LIMIT + pos_b)
            if q > 0:
                send(a_ask, q, b_bid, -q)
                store["pos"] = pos + q
        elif dev >= ENTRY and rev_to_sell >= ref - COST_SLACK:
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
