"""Market making around a fair value that is a known function of time.

Round-1 pepper root is not a random walk. Regressing mid on timestamp returns

    F(t) = 12_000 + 1_000 * day + t / 1_000

with a residual standard deviation of 1.2 ticks against a 13-tick quoted
spread (``figures/r1_pepper_deterministic_drift.png``). Once you have F(t) the
strategy is the same anchored market maker as ``anchored_market_maker.py`` with
a moving anchor - plus one twist: because F is monotonically increasing, being
long is cheaper than being flat, so the inventory target is positive rather
than zero.

The lesson generalises past this product. Before modelling a price as
stochastic, check whether the organisers made it deterministic.
"""
from typing import Dict, List, Tuple

try:
    from datamodel import Order, OrderDepth, TradingState
except ImportError:
    from research.datamodel import Order, OrderDepth, TradingState

PRODUCT = "INTARIAN_PEPPER_ROOT"
POSITION_LIMIT = 80

DRIFT_PER_TICK = 1e-3     # +1 price unit per 1,000 timestamps
BASE_FAIR = 12_000.0      # day-0 intercept of the sample data
TARGET_INVENTORY = 80     # long bias: the fair value only ever goes up
ENTRY_PREMIUM = 12        # ticks above fair we will pay to reach the target long
BID_EDGE = 2              # how far below fair we bid
ASK_EDGE = 15             # how far above fair we offer - deliberately far away
INVENTORY_SKEW = 0.0      # inventory is an asset here, not a risk


def fair_value(timestamp: int) -> float:
    """Read the module globals at call time so a sweep can rebind them."""
    return BASE_FAIR + DRIFT_PER_TICK * timestamp


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

        # While we are short of the inventory target the drift dominates the
        # spread: 80 units of a +1,000/day drift is worth 80,000, and crossing
        # a 13-tick spread to get there costs about 500. Pay it.
        take_limit = fair + (ENTRY_PREMIUM if working < TARGET_INVENTORY else 0)
        for ask in sorted(depth.sell_orders):
            if ask >= take_limit or working >= TARGET_INVENTORY:
                break
            qty = min(-depth.sell_orders[ask], POSITION_LIMIT - working)
            if qty > 0:
                orders.append(Order(PRODUCT, int(ask), qty))
                working += qty
                bought += qty

        # Selling is expensive even at a premium to fair: the inventory we give
        # up has to be bought back, and every unit we are not holding stops
        # earning the drift. Only sell into a genuinely rich bid.
        for bid in sorted(depth.buy_orders, reverse=True):
            if bid <= fair + ASK_EDGE:
                break
            qty = min(depth.buy_orders[bid], POSITION_LIMIT + working)
            if qty > 0:
                orders.append(Order(PRODUCT, int(bid), -qty))
                working -= qty
                sold += qty

        skew = INVENTORY_SKEW * (pos - TARGET_INVENTORY)
        bid_px = int(fair - BID_EDGE - skew)
        ask_px = int(fair + ASK_EDGE - skew) + 1

        buy_capacity = max(0, POSITION_LIMIT - pos - bought)
        sell_capacity = max(0, POSITION_LIMIT + pos - sold)
        if buy_capacity:
            orders.append(Order(PRODUCT, bid_px, buy_capacity))
        if sell_capacity:
            orders.append(Order(PRODUCT, ask_px, -sell_capacity))

        result[PRODUCT] = orders
        return result, 0, ""
