"""Replay figures for the reference strategies in ``strategies/``.

Read the fill-model caveats in ``research/replay.py`` before quoting any number
produced here. In particular the tape is fixed, so a quote that is one tick
wider fills just as often as a tight one - the harness cannot price the
fill-probability trade-off and will always prefer wider quotes.
"""
import importlib.util
from typing import Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from _common import cli
from research.replay import replay
from research.style import ACCENT, ACCENT_2, ACCENT_3, ACCENT_4, INK, MUTED, finish, suptitle
from research.datamodel import Order


def load(path: str) -> Any:
    spec = importlib.util.spec_from_file_location(path.split("/")[-1][:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BuyAndHold:
    """Baseline: sweep the ask book to the position limit and sit there."""

    def __init__(self, product: str, limit: int):
        self.product, self.limit = product, limit

    def run(self, state):
        d = state.order_depths.get(self.product)
        if not d or not d.sell_orders:
            return {}, 0, ""
        room = self.limit - state.position.get(self.product, 0)
        if room <= 0:
            return {}, 0, ""
        return {self.product: [Order(self.product, max(d.sell_orders), room)]}, 0, ""


def fig_round1(root, out):
    px, tr = root.prices(1), root.trades(1)
    osm = load("strategies/anchored_market_maker.py")
    pep = load("strategies/deterministic_drift.py")

    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.6),
                             gridspec_kw={"width_ratios": [1, 1, 0.95], "wspace": 0.3})

    ax = axes[0]
    total = 0.0
    for d, c in zip([-2, -1, 0], (ACCENT, ACCENT_3, ACCENT_4)):
        r = replay(px, osm.Trader(), {"ASH_COATED_OSMIUM": 80}, trades=tr, day=d)
        ax.plot(r.pnl.index / 1e6, r.pnl.values, color=c, lw=1.2, label=f"day {d}")
        total += r.pnl.iloc[-1]
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("fraction of the trading day")
    ax.set_ylabel("PnL, XIRECs")
    ax.set_title(f"osmium: {total:,.0f} over 3 days", pad=6, fontsize=10.5)
    ax.legend(ncols=3, loc="upper left")

    ax = axes[1]
    edges = [0, 2, 4, 6, 8, 10, 15]
    totals = {}
    for e in edges:
        pep.ASK_EDGE = e
        tot, shown = 0.0, None
        for d in (-2, -1, 0):
            pep.BASE_FAIR = 12_000.0 + 1_000.0 * d
            r = replay(px, pep.Trader(), {"INTARIAN_PEPPER_ROOT": 80}, trades=tr, day=d)
            tot += r.pnl.iloc[-1]
            shown = r.pnl if shown is None else shown
        totals[e] = tot
        if e in (0, 4, 15):
            col = {0: ACCENT_2, 4: ACCENT_3, 15: ACCENT}[e]
            ax.plot(shown.index / 1e6, shown.values, color=col, lw=1.4,
                    label=f"offer at fair + {e}")
    ax.set_xlabel("fraction of the trading day (day −2)")
    ax.set_ylabel("PnL, XIRECs")
    ax.set_title("how tight should the offer be?", pad=6, fontsize=10.5)
    ax.legend(loc="upper left")

    ax = axes[2]
    drift_value = 80 * 1_000 * 3
    ax.plot(edges, [totals[e] for e in edges], "o-", color=ACCENT, ms=5)
    ax.axhline(drift_value, color=ACCENT_2, ls="--", lw=1.3)
    ax.text(0.35, drift_value, " buy-and-hold benchmark = 240,000", color=ACCENT_2,
            fontsize=8.5, va="bottom")
    ax.set_xlabel("ticks between fair value and our offer")
    ax.set_ylabel("3-day PnL, XIRECs")
    ax.set_ylim(0, 2.6e5)
    ax.set_title("offer distance vs PnL (tape saturates at +10)", pad=6, fontsize=10.5)

    suptitle(fig, "Round 1, replayed",
             "Reference implementations from strategies/, replayed against the sample tape.")
    finish(fig, out / "r1_strategy_replay.png",
           "Osmium has no drift, so quoting around its anchor is the whole business. Pepper root is the "
           "opposite: one unit of inventory earns 1,000 ticks of drift per day against about 13 for a "
           "round trip of market making, so being long comes first. The right-hand curve flattens at +10 "
           "because that is where the sample tape stops printing - beyond it the harness cannot fill our "
           "offer at all, so the plateau is a property of the fill model, not an optimum.")


def fig_round5(root, out):
    px, tr = root.prices(5, [4]), root.trades(5, [4])
    lat = load("strategies/lattice_reversal.py")
    products = ["ROBOT_DISHES", "ROBOT_IRONING", "OXYGEN_SHAKE_CHOCOLATE", "PEBBLES_XL"]
    limits = {p: 10 for p in products}
    sub = px[px["product"].isin(products)]

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 3.6),
                             gridspec_kw={"width_ratios": [1.35, 1.0], "wspace": 0.26})
    ax = axes[0]
    per_product = {}
    for p, c in zip(products, (ACCENT, ACCENT_3, ACCENT_4, ACCENT_2)):
        r = replay(sub[sub["product"] == p], lat.Trader(), {p: 10}, trades=tr, day=4)
        ax.plot(r.pnl.index / 1e6, r.pnl.values, color=c, lw=1.3, label=p.replace("_", " ").title())
        per_product[p] = r.pnl.iloc[-1]
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("fraction of day 4")
    ax.set_ylabel("PnL, XIRECs")
    ax.set_title("lattice reversal, one product at a time", pad=6, fontsize=10.5)
    ax.legend(loc="upper left", fontsize=8.5)

    ax = axes[1]
    ks = list(per_product)
    vals = [per_product[k] for k in ks]
    cols = [ACCENT if v > 0 else ACCENT_2 for v in vals]
    ax.barh(range(len(ks)), vals, color=cols, alpha=0.9)
    ax.set_yticks(range(len(ks)), [k.replace("_", " ").title() for k in ks], fontsize=8.5)
    ax.margins(y=0.14)
    ax.invert_yaxis()
    ax.axvline(0, color=INK, lw=0.9)
    for i, v in enumerate(vals):
        ax.text(v, i - 0.34, f"{v:,.0f}", va="center", fontsize=9, color=INK,
                ha="left" if v > 0 else "right")
    ax.set_xlabel("day-4 PnL, XIRECs (position limit 10)")
    ax.set_title("the same rule, applied blind", pad=6, fontsize=10.5)

    suptitle(fig, "Round 5, replayed",
             "One generic detector armed on every product - no per-product tuning, no product list.")
    finish(fig, out / "r5_strategy_replay.png",
           "The detector is identical across products; the difference in outcome is entirely the "
           "difference between a lattice and a merely volatile series. PEBBLES_XL produces just as many "
           "±100 moves and loses money, which is exactly what a mechanism-based signal should do when "
           "the mechanism is absent.")


if __name__ == "__main__":
    root, out = cli()
    fig_round1(root, out)
    fig_round5(root, out)
