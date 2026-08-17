"""Round 4 figures: what the de-anonymised trade tape really told us.

The second figure is the one worth reading. It is the clearest example we have
of a signal that survives a t-statistic of 26 and still turns out to be an
artefact of the fair-value estimator.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from _common import cli
from research.style import ACCENT, ACCENT_2, ACCENT_3, INK, MUTED, finish, suptitle

SPOT = "VELVETFRUIT_EXTRACT"


def tag(px, tr):
    idx = px.set_index(["day", "timestamp", "product"])
    tr = tr.copy()
    key = tr.set_index(["day", "timestamp", "symbol"]).index
    for c in ("mid", "wall_mid", "spread"):
        tr[c] = key.map(idx[c])
    return tr.dropna(subset=["mid"])


def fig_edge_map(tr, out):
    marks = sorted(set(tr["buyer"].dropna()) | set(tr["seller"].dropna()))
    buy = tr.assign(e=tr["mid"] - tr["price"]).groupby("buyer")["e"].mean()
    sell = tr.assign(e=tr["price"] - tr["mid"]).groupby("seller")["e"].mean()
    # the same edge measured against the robust fair value
    wbuy = tr.assign(e=tr["wall_mid"] - tr["price"]).groupby("buyer")["e"].mean()
    wsell = tr.assign(e=tr["price"] - tr["wall_mid"]).groupby("seller")["e"].mean()

    fig, axes = plt.subplots(1, 2, figsize=(11.6, 3.9),
                             gridspec_kw={"width_ratios": [1.15, 1.0], "wspace": 0.3})
    ax = axes[0]
    y = np.arange(len(marks))
    ax.barh(y - 0.2, [buy.get(m, np.nan) for m in marks], height=0.38, color=ACCENT,
            label="as buyer  (mid − price)")
    ax.barh(y + 0.2, [sell.get(m, np.nan) for m in marks], height=0.38, color=ACCENT_2,
            label="as seller (price − mid)")
    ax.scatter([wbuy.get(m, np.nan) for m in marks], y - 0.2, s=26, facecolors="none",
               edgecolors=INK, lw=1.1, zorder=5, label="same, vs. wall mid")
    ax.scatter([wsell.get(m, np.nan) for m in marks], y + 0.2, s=26, facecolors="none",
               edgecolors=INK, lw=1.1, zorder=5)
    ax.annotate("Mark 67: the only sign flip", 
                xy=(wbuy.get("Mark 67"), len(marks) - 1 - 0.2), xytext=(-8.5, 4.2),
                fontsize=8, color=INK, va="center",
                arrowprops=dict(arrowstyle="->", lw=0.9, color=INK, shrinkA=4, shrinkB=3))
    ax.set_yticks(y, marks)
    ax.axvline(0, color=INK, lw=0.9)
    ax.invert_yaxis()
    ax.set_xlabel("average execution edge, ticks")
    ax.set_title("who pays and who collects", pad=6)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

    ax = axes[1]
    ct = pd.crosstab(tr["buyer"], tr["seller"]).reindex(index=marks, columns=marks, fill_value=0)
    im = ax.imshow(ct.to_numpy(), cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(marks)), [m.replace("Mark ", "") for m in marks])
    ax.set_yticks(range(len(marks)), [m.replace("Mark ", "") for m in marks])
    ax.set_xlabel("seller (Mark)")
    ax.set_ylabel("buyer (Mark)")
    ax.grid(False)
    for i in range(len(marks)):
        for j in range(len(marks)):
            v = ct.iat[i, j]
            if v:
                ax.text(j, i, str(v), ha="center", va="center", fontsize=8,
                        color="white" if v > ct.to_numpy().max() * 0.5 else INK)
    ax.set_title("who trades with whom", pad=6)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02).set_label("prints", fontsize=8)

    suptitle(fig, "Round 4 named every counterparty",
             "Execution edge and the bilateral flow matrix, three sample days, all products pooled.")
    finish(fig, out / "r4_counterparty_edge.png",
           "Mark 14 collects ~6.5 ticks on both sides of every print: it is the profitable market maker. "
           "Mark 38 pays ~8.5 ticks on both sides and trades hydrogel almost exclusively against Mark 14. "
           "Measuring the same edge against the wall mid (open markers) changes nothing for the makers or "
           "the takers - and flips the sign for Mark 67, who turns out to collect 1.1 ticks rather than pay "
           "0.8. That one disagreement is the whole of section 2.")


def paths_around(px, ev, column, grid):
    out = []
    for d, s in ((d, px[(px["day"] == d) & (px["product"] == SPOT)]
                  .set_index("timestamp")[column]) for d in sorted(px["day"].unique())):
        idx, vals = s.index.to_numpy(), s.to_numpy(float)
        for t0 in ev[ev["day"] == d]["timestamp"]:
            j = np.searchsorted(idx, t0)
            if j >= len(idx) or idx[j] != t0:
                continue
            pos = np.clip(np.searchsorted(idx, t0 + grid), 0, len(vals) - 1)
            out.append(vals[pos] - vals[j])
    return np.asarray(out)


def fig_event(px, tr, out):
    ev = tr[(tr["symbol"] == SPOT) & (tr["buyer"] == "Mark 67")]
    grid = np.arange(-500, 1_100, 100)
    P_touch = paths_around(px, ev, "mid", grid)
    P_wall = paths_around(px, ev, "wall_mid", grid)

    fig, axes = plt.subplots(1, 2, figsize=(11.6, 3.7),
                             gridspec_kw={"width_ratios": [1.3, 1.0], "wspace": 0.26})
    ax = axes[0]
    for P, c, lab in ((P_touch, ACCENT_2, "touch mid"), (P_wall, ACCENT_3, "wall mid")):
        mu, se = P.mean(0), P.std(0) / np.sqrt(len(P))
        ax.fill_between(grid, mu - 1.96 * se, mu + 1.96 * se, color=c, alpha=0.18, lw=0)
        ax.plot(grid, mu, color=c, lw=1.8, label=lab)
    ax.axvline(0, color=INK, ls="--", lw=1.0)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("timestamps relative to the print")
    ax.set_ylabel("price change, ticks")
    ax.set_title(f"average path around a Mark-67 buy  (n = {len(P_touch)})", pad=6)
    ax.legend(loc="lower right")
    ax.annotate("+1.97 ticks, t = 26\n(and entirely spurious)", xy=(100, P_touch.mean(0)[15]),
                xytext=(260, 1.15), fontsize=8.5, color=ACCENT_2,
                arrowprops=dict(arrowstyle="->", color=ACCENT_2, lw=0.9))

    ax = axes[1]
    base = px[px["product"] == SPOT]
    ax.hist(base["mid"] - base["wall_mid"], bins=np.arange(-6, 6.25, 0.25), density=True,
            color=MUTED, alpha=0.55, label="all snapshots")
    ax.hist(ev["mid"] - ev["wall_mid"], bins=np.arange(-6, 6.25, 0.25), density=True,
            color=ACCENT_2, alpha=0.7, label="at Mark-67 prints")
    ax.set_xlabel("touch mid − wall mid, ticks")
    ax.set_ylabel("density")
    ax.set_title("the book is dislocated exactly when he trades", pad=6)
    ax.legend()

    suptitle(fig, "A t-statistic of 26 that means nothing",
             "The same event study, run against two different definitions of fair value.")
    finish(fig, out / "r4_mark67_event_study.png",
           "Measured against the touch mid, a Mark-67 buy 'predicts' a two-tick rally with a t-statistic "
           "of 26. Measured against the wall mid - which ignores thin quotes posted inside the spread - "
           "the same events predict 0.07 ticks. The right-hand panel explains why: Mark 67 only trades "
           "when another participant has posted a quote roughly two ticks through fair value. The alpha "
           "was never in the identity; it was in detecting the dislocated quote, which needs no tape at all.")


if __name__ == "__main__":
    root, out = cli()
    px, tr = root.prices(4), root.trades(4)
    tr = tag(px, tr)
    fig_edge_map(tr, out)
    fig_event(px, tr, out)
