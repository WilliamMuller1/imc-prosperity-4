"""A deliberately small order-book replay harness.

This is **not** the simulator we used during the competition. It is a compact,
readable stand-in, good enough to sanity-check the reference strategies in
``strategies/`` and to produce the PnL figures in this repository. Its fill
model is stated explicitly, because a backtester whose fill model you cannot
recite is a random-number generator:

1. **Aggressive orders** - a buy priced at or above a resting ask - fill by
   walking the visible book and paying the resting price, exactly as the
   Prosperity engine does.
2. **Passive orders** rest until the next snapshot and are matched against the
   *public trade tape*. If a print occurs at price ``p`` and we hold a resting
   bid at ``b >= p``, we are filled at ``b`` up to the printed size. This is the
   standard assumption for Prosperity: participants' orders take priority over
   bot orders at the same price, so we intercept flow that would otherwise have
   crossed elsewhere in the book.
3. Position limits are enforced by truncating orders. The real engine *rejects*
   the whole basket for a product on any breach, so this harness is more
   forgiving than the competition; strategies should still respect the limit
   themselves.

Known biases, in the direction of *understating* performance: the tape only
contains trades that happened without us in the book, so any flow we would have
attracted by quoting more aggressively is invisible, and the "wide fill"
behaviour that appears when one side of the book is empty is not modelled at
all. Treat absolute PnL from this harness as a lower bound and a relative
comparison tool, never as an estimate of a competition score.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from research.datamodel import Order, OrderDepth, Trade, TradingState

_LEVELS = (1, 2, 3)
_COLS = ([f"bid_price_{i}" for i in _LEVELS] + [f"bid_volume_{i}" for i in _LEVELS]
         + [f"ask_price_{i}" for i in _LEVELS] + [f"ask_volume_{i}" for i in _LEVELS] + ["mid"])


@dataclass
class ReplayResult:
    pnl: pd.Series
    position: pd.DataFrame
    fills: pd.DataFrame = field(default_factory=pd.DataFrame)

    def summary(self) -> dict:
        d = self.pnl.diff().dropna()
        passive = int((self.fills["kind"] == "passive").sum()) if len(self.fills) else 0
        return {
            "final_pnl": round(float(self.pnl.iloc[-1]), 1),
            "fills": len(self.fills),
            "passive_share": round(passive / max(len(self.fills), 1), 2),
            "volume": int(self.fills["qty"].abs().sum()) if len(self.fills) else 0,
            "max_drawdown": round(float((self.pnl.cummax() - self.pnl).max()), 1),
            "pnl_per_snapshot_t": round(float(d.mean() / (d.std() / np.sqrt(len(d)))), 2)
            if d.std() else float("nan"),
        }


def _depths(row: dict, prods) -> dict[str, OrderDepth]:
    out = {}
    for p in prods:
        r = row[p]
        od = OrderDepth()
        for i in _LEVELS:
            bp, bv = r[f"bid_price_{i}"], r[f"bid_volume_{i}"]
            ap, av = r[f"ask_price_{i}"], r[f"ask_volume_{i}"]
            if bp == bp:
                od.buy_orders[int(bp)] = int(bv)
            if ap == ap:
                od.sell_orders[int(ap)] = -int(av)
        if od.buy_orders and od.sell_orders:
            out[p] = od
    return out


def replay(prices: pd.DataFrame, trader, limits: dict[str, int],
           trades: pd.DataFrame | None = None, day: int | None = None) -> ReplayResult:
    """Replay one day of snapshots against a Prosperity-style ``Trader``."""
    if day is not None:
        prices = prices[prices["day"] == day]
        if trades is not None:
            trades = trades[trades["day"] == day]

    prods = sorted(limits)
    prices = prices[prices["product"].isin(prods)]
    wide = prices.pivot_table(index="timestamp", columns="product", values=_COLS)
    wide = wide.swaplevel(axis=1).sort_index(axis=1)
    records = wide.to_dict("index")
    ts_index = wide.index.to_numpy()

    tape: dict[tuple[int, str], list[tuple[float, int]]] = defaultdict(list)
    if trades is not None:
        for t, sym, px_, q in trades[["timestamp", "symbol", "price", "quantity"]].itertuples(index=False):
            tape[(int(t), sym)].append((float(px_), int(q)))

    pos = {p: 0 for p in prods}
    cash = 0.0
    resting: list[Order] = []
    trader_data = ""
    pnl, positions, fills = [], [], []

    for ts in ts_index:
        raw = records[ts]
        row = {p: {c: raw.get((p, c), np.nan) for c in _COLS} for p in prods}
        books = _depths(row, prods)
        if not books:
            continue

        # ---- 1. match yesterday's resting quotes against today's tape -------
        for o in resting:
            prints = tape.get((int(ts), o.symbol))
            if not prints:
                continue
            for price, size in prints:
                if o.quantity > 0 and o.price >= price:
                    q = min(o.quantity, size, limits[o.symbol] - pos[o.symbol])
                    if q > 0:
                        cash -= q * o.price
                        pos[o.symbol] += q
                        fills.append((ts, o.symbol, o.price, q, "passive"))
                elif o.quantity < 0 and o.price <= price:
                    q = min(-o.quantity, size, limits[o.symbol] + pos[o.symbol])
                    if q > 0:
                        cash += q * o.price
                        pos[o.symbol] -= q
                        fills.append((ts, o.symbol, o.price, -q, "passive"))
        resting = []

        market_trades = {p: [Trade(p, int(px_), q, timestamp=int(ts))
                             for px_, q in tape.get((int(ts), p), [])] for p in prods}
        state = TradingState(timestamp=int(ts), traderData=trader_data, order_depths=books,
                             position=dict(pos), market_trades=market_trades)
        orders, _conv, trader_data = trader.run(state)

        # ---- 2. aggressive fills against the visible book -------------------
        for sym, olist in (orders or {}).items():
            book = books.get(sym)
            if book is None:
                continue
            for o in olist:
                if o.quantity > 0:
                    left = min(o.quantity, limits[sym] - pos[sym])
                    for ap in sorted(book.sell_orders):
                        if ap > o.price or left <= 0:
                            break
                        q = min(left, -book.sell_orders[ap])
                        if q <= 0:
                            continue
                        cash -= q * ap
                        pos[sym] += q
                        book.sell_orders[ap] += q
                        left -= q
                        fills.append((ts, sym, ap, q, "aggressive"))
                    if left > 0:
                        resting.append(Order(sym, o.price, left))
                elif o.quantity < 0:
                    left = min(-o.quantity, limits[sym] + pos[sym])
                    for bp in sorted(book.buy_orders, reverse=True):
                        if bp < o.price or left <= 0:
                            break
                        q = min(left, book.buy_orders[bp])
                        if q <= 0:
                            continue
                        cash += q * bp
                        pos[sym] -= q
                        book.buy_orders[bp] -= q
                        left -= q
                        fills.append((ts, sym, bp, -q, "aggressive"))
                    if left > 0:
                        resting.append(Order(sym, o.price, -left))

        mtm = sum(pos[p] * row[p]["mid"] for p in prods if row[p]["mid"] == row[p]["mid"])
        pnl.append(cash + mtm)
        positions.append(dict(pos))

    idx = ts_index[: len(pnl)]
    return ReplayResult(
        pnl=pd.Series(pnl, index=idx, name="pnl"),
        position=pd.DataFrame(positions, index=idx),
        fills=pd.DataFrame(fills, columns=["timestamp", "symbol", "price", "qty", "kind"]),
    )
