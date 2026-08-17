"""Market making on a fair value you know exactly.

With five days to expiry and a strike 1,250 ticks below spot, ``VEV_4000`` has
no optionality left. Its price tracks ``S - K`` with a residual standard
deviation of 0.83 ticks and an empirical delta of 0.9997
(``figures/r3_intrinsic_basis.png``). The fair value of the voucher is therefore
not estimated - it is *derived*:

    F_t = S_t - K,      sd(C_t - F_t) < 1 tick

The instinct is to call this an arbitrage and cross the spread whenever the
basis moves. It is not. The voucher book is quoted symmetrically around
intrinsic and is about 21 ticks wide, so the basis never leaves the spread: in
three days of sample data there is not one snapshot where the best ask sits two
ticks below intrinsic.

What the relationship is worth is *inventory-free market making*. In a
21-tick-wide book, quoting a few ticks either side of a fair value known to
within one tick is close to free money, and the underlying can be traded against
any fill to remove the delta. The general lesson: knowing fair value precisely
is usually worth far more as a quoting edge than as a taking edge.
"""
from typing import Dict, List, Tuple

try:
    from datamodel import Order, OrderDepth, TradingState
except ImportError:  # local replay
    from research.datamodel import Order, OrderDepth, TradingState

SPOT = "VELVETFRUIT_EXTRACT"
VOUCHER = "VEV_4000"
STRIKE = 4_000

SPOT_LIMIT = 200
VOUCHER_LIMIT = 300

QUOTE_EDGE = 4          # ticks either side of the derived fair value
INVENTORY_SKEW = 0.02   # ticks of quote shift per unit of voucher inventory
MAX_QUOTE_SIZE = 40     # never show the whole limit at once
HEDGE_RATIO = 1.0       # the voucher's delta is ~1.00
HEDGE = True


def touch(d: OrderDepth) -> Tuple[int, int]:
    return max(d.buy_orders), min(d.sell_orders)


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        d_s = state.order_depths.get(SPOT)
        d_v = state.order_depths.get(VOUCHER)
        if not (d_s and d_v and d_s.buy_orders and d_s.sell_orders
                and d_v.buy_orders and d_v.sell_orders):
            return {}, 0, ""

        s_bid, s_ask = touch(d_s)
        fair = (s_bid + s_ask) / 2.0 - STRIKE

        pos_v = state.position.get(VOUCHER, 0)
        pos_s = state.position.get(SPOT, 0)
        skew = INVENTORY_SKEW * pos_v

        orders: Dict[str, List[Order]] = {VOUCHER: []}
        bid_px = int(fair - QUOTE_EDGE - skew)
        ask_px = int(fair + QUOTE_EDGE - skew) + 1

        buy_size = min(MAX_QUOTE_SIZE, VOUCHER_LIMIT - pos_v)
        sell_size = min(MAX_QUOTE_SIZE, VOUCHER_LIMIT + pos_v)
        if buy_size > 0:
            orders[VOUCHER].append(Order(VOUCHER, bid_px, buy_size))
        if sell_size > 0:
            orders[VOUCHER].append(Order(VOUCHER, ask_px, -sell_size))

        # Delta-hedge accumulated inventory against the underlying, aggressively.
        if HEDGE:
            target_s = max(-SPOT_LIMIT, min(SPOT_LIMIT, -int(round(HEDGE_RATIO * pos_v))))
            delta = target_s - pos_s
            if delta > 0:
                orders[SPOT] = [Order(SPOT, s_ask, min(delta, -d_s.sell_orders[s_ask]))]
            elif delta < 0:
                orders[SPOT] = [Order(SPOT, s_bid, -min(-delta, d_s.buy_orders[s_bid]))]

        return {k: v for k, v in orders.items() if v}, 0, ""
