from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, TradingState

import jsonpickle

POSITION_LIMIT = 10
LATTICE = 100.0
JUMP_MIN = 0.8 * LATTICE
JUMP_MAX = 1.2 * LATTICE
LATTICE_TOL = 5.0
PINNED_MIN = 0.5
MIN_SNAPSHOTS = 200
ALTERNATION_MIN = 0.6
MIN_JUMPS = 20
PASSIVE_EDGE = 1


def off_lattice(mid: float) -> float:
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

            st["n"] += 1
            if off_lattice(mid) <= LATTICE_TOL:
                st["p"] += 1

            if st["m"] is not None:
                move = mid - st["m"]
                if JUMP_MIN <= abs(move) <= JUMP_MAX:
                    direction = "up" if move > 0 else "down"
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
                if sell_room > 0:
                    orders.append(Order(product, best_bid, -sell_room))
            elif direction == "down":
                if buy_room > 0:
                    orders.append(Order(product, best_ask, buy_room))
            else:
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
