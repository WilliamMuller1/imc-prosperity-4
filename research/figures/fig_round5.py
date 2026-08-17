"""Round 5 figures: fifty products, three days, and a lot of ways to fool yourself."""
import itertools

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from _common import cli
from research.prosperity_io import panel
from research.stats_tools import (
    adf_pvalue, alternation_rate, detect_jumps, pairwise_coint_scan, random_walk_null,
)
from research.style import (
    ACCENT, ACCENT_2, ACCENT_3, ACCENT_4, GRID, INK, MUTED, PALETTE, finish, suptitle,
)

DAYS = [2, 3, 4]
LATTICE = ["ROBOT_DISHES", "ROBOT_IRONING", "OXYGEN_SHAKE_CHOCOLATE",
           "OXYGEN_SHAKE_EVENING_BREATH"]
SHORT = {
    "ROBOT_DISHES": "Robot\nDishes",
    "ROBOT_IRONING": "Robot\nIroning",
    "OXYGEN_SHAKE_CHOCOLATE": "O₂ Shake\nChocolate",
    "OXYGEN_SHAKE_EVENING_BREATH": "O₂ Shake\nEvening",
    "PEBBLES_XL": "Pebbles\nXL",
}


def fig_lattice(w, out):
    s = w[4]["ROBOT_DISHES"]
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.5), gridspec_kw={"wspace": 0.3})

    ax = axes[0]
    seg = s[(s.index >= 300_000) & (s.index <= 400_000)]
    ax.step(seg.index, seg.values, where="post", color=ACCENT, lw=1.1)
    for lvl in range(int(seg.min() // 100) * 100, int(seg.max()) + 200, 100):
        ax.axhline(lvl, color=GRID, lw=0.7, zorder=0)
    ax.set_xlabel("timestamp")
    ax.set_ylabel("mid")
    ax.set_title("ROBOT_DISHES, day 4", pad=6)

    ax = axes[1]
    d = s.diff()
    nz = d[d != 0]
    ax.hist(nz, bins=np.arange(-130, 135, 5), color=ACCENT_3, alpha=0.9)
    ax.set_yscale("log")
    ax.set_xlabel("non-zero change in mid")
    ax.set_ylabel("count (log)")
    ax.set_title(f"{(nz.abs() >= 80).mean():.0%} of all moves are ±100", pad=6)

    ax = axes[2]
    names, rates, ns = [], [], []
    for p in LATTICE + ["PEBBLES_XL"]:
        js = pd.concat([detect_jumps(w[d_][p]) for d_ in DAYS])
        r, n = alternation_rate(js)
        names.append(SHORT[p])
        rates.append(r)
        ns.append(n)
    cols = [ACCENT if p != "PEBBLES_XL" else ACCENT_2 for p in LATTICE + ["PEBBLES_XL"]]
    ax.bar(range(len(names)), rates, color=cols, alpha=0.9)
    ax.axhline(0.5, color=INK, ls="--", lw=1.1)
    ax.text(0.02, 0.52, "no structure", transform=ax.transAxes, fontsize=8.5, color=INK)
    ax.set_xticks(range(len(names)), names, fontsize=7.5, rotation=38, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("P(next jump reverses)")
    ax.set_title("alternation rate  (n on bars)", pad=6)
    for i, (r, n) in enumerate(zip(rates, ns)):
        ax.text(i, r + 0.03, f"{n}", ha="center", fontsize=8, color=INK)

    suptitle(fig, "A rounding lattice, and a product that only looks like one",
             "Some Round-5 mids are quantised to multiples of 100; a ±100 print is then a rounding event, "
             "not news.")
    finish(fig, out / "r5_lattice.png",
           "Because the observed price is the latent price rounded onto a 100-wide grid, a jump means the "
           "latent value has just crossed a boundary - so the next crossing is far more likely to go back. "
           "PEBBLES_XL produces just as many ±100 moves but alternates at exactly 50%: it is simply a "
           "volatile product. Screening on jump count alone would have put it in the basket.")


def fig_jump_edge(w, out):
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 3.6),
                             gridspec_kw={"width_ratios": [1.3, 1.0], "wspace": 0.26})
    s = w[4]["ROBOT_DISHES"]
    js = detect_jumps(s)
    grid = np.arange(0, 1_100, 100)
    idx, vals = s.index.to_numpy(), s.to_numpy(float)
    up, dn = [], []
    for t0, v in js.items():
        j = np.searchsorted(idx, t0)
        pos = np.clip(np.searchsorted(idx, t0 + grid), 0, len(vals) - 1)
        (up if v > 0 else dn).append(vals[pos] - vals[j])
    up, dn = np.array(up), np.array(dn)

    ax = axes[0]
    for P, c, lab in ((up, ACCENT_2, f"after a +100 jump (n={len(up)})"),
                      (dn, ACCENT_3, f"after a −100 jump (n={len(dn)})")):
        mu, se = P.mean(0), P.std(0) / np.sqrt(len(P))
        ax.fill_between(grid, mu - 1.96 * se, mu + 1.96 * se, color=c, alpha=0.18, lw=0)
        ax.plot(grid, mu, color=c, lw=1.8, label=lab)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("timestamps after the jump")
    ax.set_ylabel("mean mid change, ticks")
    ax.set_title("the reversal is worth ~40 ticks in 300 timestamps", pad=6)
    ax.legend(loc="lower left")

    ax = axes[1]
    pnl = np.concatenate([-up[:, 3], dn[:, 3]])
    ax.hist(pnl, bins=np.arange(-145, 150, 10), color=ACCENT, alpha=0.9)
    ax.set_yscale("log")
    ax.axvline(0, color=INK, lw=0.9)
    ax.axvline(pnl.mean(), color=ACCENT_2, ls="--", lw=1.4)
    ax.text(pnl.mean() + 6, ax.get_ylim()[1] * 0.35, f"mean {pnl.mean():+.0f}\nvs ~4 ticks of cost",
            color=ACCENT_2, fontsize=8.5)
    ax.set_xlabel("PnL per unit of a 300-timestamp reversal trade, ticks")
    ax.set_ylabel("events (log)")
    ax.set_title(f"{(pnl > 4).mean():.0%} of events clear the spread", pad=6)

    suptitle(fig, "The one Round-5 edge that was structural rather than statistical",
             "ROBOT_DISHES, day 4: 740 lattice crossings, 87% of them followed by a crossing back.")
    finish(fig, out / "r5_lattice_payoff.png",
           "Trading against the jump earns about 40 ticks per event on a position limit of 10, against a "
           "half-spread cost of roughly 4. The asymmetry - not the hit rate - is what makes it worth "
           "doing: the losses are bounded by the same lattice that produces the wins.")


def fig_pebbles(w, wb, wa, out):
    peb = sorted([c for c in w[4].columns if c.startswith("PEBBLES_")])
    win = w[4].iloc[:6_000]
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 3.5), gridspec_kw={"wspace": 0.3})

    ax = axes[0]
    for p_, c in zip(peb, PALETTE):
        ax.plot(np.arange(len(win)), win[p_] - win[p_].iloc[0], lw=0.8, color=c,
                label=p_.replace("PEBBLES_", ""))
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("snapshot (day 4)")
    ax.set_ylabel("mid − first mid, ticks")
    ax.set_title("each pebble wanders freely", pad=6)
    ax.legend(ncols=5, loc="upper center", fontsize=8, columnspacing=0.9, handlelength=1.1)

    ax = axes[1]
    ax.plot(np.arange(len(win)), win[peb].sum(axis=1) - 50_000, lw=0.6, color=ACCENT_2)
    ax.axhline(0, color=INK, lw=0.9)
    ax.set_ylim(-60, 60)
    ax.set_xlabel("snapshot (day 4)")
    ax.set_ylabel("basket − 50,000, ticks")
    ax.set_title("their sum does not", pad=6)

    ax = axes[2]
    allsum = pd.concat([w[d][peb].sum(axis=1) for d in DAYS])
    bsum = pd.concat([wb[d][peb].sum(axis=1) for d in DAYS])
    asum = pd.concat([wa[d][peb].sum(axis=1) for d in DAYS])
    bins = np.arange(-60, 60.5, 2)
    ax.hist(bsum - 50_000, bins=bins, color=ACCENT_2, alpha=0.65, label="Σ best bid (sell here)")
    ax.hist(allsum - 50_000, bins=bins, color=INK, alpha=0.9, label="Σ mid (fair)")
    ax.hist(asum - 50_000, bins=bins, color=ACCENT_3, alpha=0.65, label="Σ best ask (buy here)")
    ax.axvline(0, color=INK, lw=1.0, ls="--")
    ax.set_yscale("log")
    ax.set_xlabel("basket − 50,000, ticks")
    ax.set_ylabel("snapshots (log)")
    ax.set_title("but you cannot trade it", pad=6)
    ax.legend(fontsize=7.2, loc="upper left")

    suptitle(fig, "A hard accounting identity that is not an arbitrage",
             "PEBBLES_XS + S + M + L + XL = 50,000 at every timestamp - behind 65 ticks of spread.")
    finish(fig, out / "r5_pebbles_basket.png",
           f"The pebbles move by 1,500-5,300 ticks a day; their sum never leaves a 20-tick band "
           f"(sigma {allsum.std():.2f}). That is a constraint, not a correlation. But the right-hand panel is "
           "the one that decides what to do with it: crossing five spreads costs 65 ticks, the sum of the "
           "best bids never once reaches 50,000, and the sum of the asks falls below it in 1.5% of "
           "snapshots for at most 4 ticks. The identity is not an arbitrage - it is the most precise fair "
           "value in the round, and its use is quoting.")


def fig_drift(w, out):
    prods = sorted(w[4].columns)
    rows = []
    for p in prods:
        sl = []
        for d in DAYS:
            s = w[d][p]
            b = np.polyfit(s.index.to_numpy(float), s.to_numpy(float), 1)[0] * 1_000
            r2 = np.corrcoef(s.index.to_numpy(float), s.to_numpy(float))[0, 1] ** 2
            sl.append((b, r2))
        rows.append(dict(product=p, s2=sl[0][0], s3=sl[1][0], s4=sl[2][0],
                         min_r2=min(x[1] for x in sl)))
    df = pd.DataFrame(rows)
    df["same_sign"] = (np.sign(df.s2) == np.sign(df.s3)) & (np.sign(df.s3) == np.sign(df.s4))
    picked = ["OXYGEN_SHAKE_GARLIC", "GALAXY_SOUNDS_BLACK_HOLES", "MICROCHIP_OVAL",
              "UV_VISOR_AMBER", "PEBBLES_XS"]

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 3.7),
                             gridspec_kw={"width_ratios": [1.2, 1.0], "wspace": 0.28})
    ax = axes[0]
    o = df[~df["product"].isin(picked)]
    ax.scatter(o.s2, o.s3, s=26, color=MUTED, alpha=0.6, label="other products")
    q = df[df["product"].isin(picked)]
    ax.scatter(q.s2, q.s3, s=70, color=ACCENT_2, zorder=4, label="the five we bet on")
    offsets = {"OXYGEN_SHAKE_GARLIC": (8, 8), "GALAXY_SOUNDS_BLACK_HOLES": (8, -14),
               "MICROCHIP_OVAL": (8, 4), "UV_VISOR_AMBER": (8, 4), "PEBBLES_XS": (10, 2)}
    for _, r in q.iterrows():
        ax.annotate(r["product"].replace("_", " ").title(), (r.s2, r.s3),
                    textcoords="offset points", xytext=offsets[r["product"]],
                    fontsize=7.5, color=INK)
    ax.axhline(0, color=INK, lw=0.8)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_xlabel("day-2 slope (ticks / 1,000 timestamps)")
    ax.set_ylabel("day-3 slope")
    ax.set_title("does a trend on one day repeat on the next?", pad=6)
    ax.legend(loc="lower right")

    ax = axes[1]
    n_same = int(df.same_sign.sum())
    ax.bar(["observed", "coin-flip null"], [n_same, len(df) * 0.25],
           color=[ACCENT, MUTED], alpha=0.9, width=0.55)
    ax.set_ylabel("products trending the same way on all 3 days")
    ax.set_title(f"{n_same} of {len(df)} vs. {len(df) * 0.25:.1f} expected by chance", pad=6)
    for i, v in enumerate([n_same, len(df) * 0.25]):
        ax.text(i, v + 0.3, f"{v:.1f}", ha="center", fontsize=9.5, color=INK)
    n_strong = int((df.same_sign & (df.min_r2 > 0.5)).sum())
    ax.text(0.5, 0.42, f"of which {n_strong} keep $R^2>0.5$\non all three days",
            transform=ax.transAxes, ha="center", fontsize=10, color=ACCENT_2,
            bbox=dict(boxstyle="round,pad=0.45", fc="white", ec=ACCENT_2, lw=0.8))

    suptitle(fig, "The directional bet we made was indistinguishable from noise",
             "Per-day linear trend of every Round-5 product, fitted on the three sample days.")
    finish(fig, out / "r5_drift_illusion.png",
           "Thirteen of fifty products trend the same way on all three days; a fair coin predicts 12.5. "
           "Not one of them keeps a per-day R² above 0.5 across all three. Our submission held maximum "
           "directional exposure in five of them citing 'R² > 0.75' - a figure that came from one line "
           "fitted through all three days at once, so it measured the level gaps between days rather than "
           "any trend within one. MICROCHIP_OVAL: pooled 0.912, day-2 0.000. The bet paid off. That does "
           "not make it a good bet.")


def fig_multiple_testing(w, out):
    is_panel = pd.concat([w[2], w[3]], ignore_index=True)
    oos_panel = w[4].reset_index(drop=True)
    res = pairwise_coint_scan(is_panel, oos_panel, alpha=0.05, subsample=10)
    n_pairs = res.attrs["n_pairs"]
    null = random_walk_null(50, len(is_panel) // 10, seed=0)

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 3.7),
                             gridspec_kw={"width_ratios": [1.15, 1.0], "wspace": 0.28})
    ax = axes[0]
    ax.scatter(res.p_is, res.p_oos, s=16, color=ACCENT, alpha=0.55)
    ax.axhline(0.05, color=ACCENT_2, ls="--", lw=1.2)
    ax.axvline(0.05, color=ACCENT_2, ls="--", lw=1.2)
    ax.set_xscale("log")
    ax.set_xlabel("ADF p-value, days 2–3 (in sample)")
    ax.set_ylabel("ADF p-value, day 4 (held out)")
    ax.set_title(f"{len(res)} pairs pass in sample, {(res.p_oos < 0.05).sum()} survive", pad=6)
    ax.text(0.03, 0.06, "survivors", transform=ax.transAxes, color=ACCENT_2, fontsize=8.5)

    ax = axes[1]
    bars = [100 * len(res) / n_pairs, 100 * (null < 0.05).mean(), 100 * (res.p_oos < 0.05).mean(), 5]
    labels = ["real data\nin sample", "independent\nrandom walks", "real data\nheld out", "nominal\n5% level"]
    ax.bar(labels, bars, color=[ACCENT, MUTED, ACCENT_3, ACCENT_2], alpha=0.9, width=0.6)
    for i, v in enumerate(bars):
        ax.text(i, v + 0.4, f"{v:.1f}%", ha="center", fontsize=9.5, color=INK)
    ax.set_ylabel("% of pairs 'cointegrated' at 5%")
    ax.set_title("the screen finds no more than chance does", pad=6)
    ax.tick_params(axis="x", labelsize=8)

    suptitle(fig, "Why we did not run a pairs book on the Round-5 universe",
             f"All {n_pairs} product pairs, hedge ratio fitted in sample, ADF re-run on held-out data.")
    finish(fig, out / "r5_multiple_testing.png",
           "Scanning fifty products gives 1,225 pairs. One in five clears an ADF test in sample - but so "
           "does one in seven pairs of *independent random walks* over the same sample length, and only "
           "2.8% of the in-sample winners survive on held-out data. A screen that selects on p-values "
           "alone is a machine for generating confident nonsense.")
    return res


def fig_snackpack(w, wb, wa, out):
    snack = [c for c in w[4].columns if c.startswith("SNACKPACK_")]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.8),
                             gridspec_kw={"width_ratios": [1.0, 1.15, 1.0], "wspace": 0.34})
    ax = axes[0]
    C = w[4][snack].diff().corr()
    im = ax.imshow(C, cmap="RdBu_r", vmin=-1, vmax=1)
    lab = [s.replace("SNACKPACK_", "").title() for s in snack]
    ax.set_xticks(range(len(lab)), lab, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(lab)), lab, fontsize=8)
    ax.grid(False)
    for i in range(len(lab)):
        for j in range(len(lab)):
            ax.text(j, i, f"{C.iat[i, j]:.2f}", ha="center", va="center", fontsize=7.5,
                    color="white" if abs(C.iat[i, j]) > 0.6 else INK)
    ax.set_title("first-difference correlation, day 4", pad=6)

    ax = axes[1]
    for d, c in zip(DAYS, (ACCENT, ACCENT_3, ACCENT_4)):
        s = w[d]["SNACKPACK_CHOCOLATE"] + w[d]["SNACKPACK_VANILLA"]
        ax.plot(np.arange(len(s)) + (d - 2) * len(s), s, lw=0.5, color=c, label=f"day {d}")
    ax.axhline(20_000, color=ACCENT_2, ls="--", lw=1.3)
    ax.set_xlabel("snapshot")
    ax.set_ylabel("chocolate + vanilla")
    ax.set_title("a soft relationship, not a hard one", pad=6)
    ax.legend(ncols=3, loc="lower left")

    ax = axes[2]
    sp = pd.concat([w[d]["SNACKPACK_CHOCOLATE"] - w[d]["SNACKPACK_VANILLA"] for d in DAYS])
    cost = float(np.mean([(wa[d]["SNACKPACK_CHOCOLATE"] - wb[d]["SNACKPACK_CHOCOLATE"]).median()
                          + (wa[d]["SNACKPACK_VANILLA"] - wb[d]["SNACKPACK_VANILLA"]).median()
                          for d in DAYS]))
    ax.bar(["dispersion\nof the spread", "round-trip\ncost"], [sp.std(), cost],
           color=[ACCENT_3, ACCENT_2], alpha=0.9, width=0.55)
    for i, v in enumerate([sp.std(), cost]):
        ax.annotate(f"{v:.0f}", (i, v), textcoords="offset points", xytext=(0, 4),
                    ha="center", fontsize=9, color=INK)
    ax.set_ylabel("ticks")
    ax.set_title(f"tradable: {sp.std() / cost:.0f}× its own cost", pad=6)

    suptitle(fig, "The looser relationship was the tradable one",
             "Snack packs screen worse than the pebbles and are worth far more.")
    finish(fig, out / "r5_snackpack_structure.png",
           "Chocolate and vanilla move at -0.92 correlation but their sum drifts 155 ticks across three "
           "days, so unlike the pebbles this is a tendency, not an identity. It is also the better trade: "
           f"the chocolate-vanilla spread disperses by {sp.std():.0f} ticks against a {cost:.0f}-tick "
           "round-trip cost, an 11:1 ratio running exactly the opposite way to the pebbles' 1:23. "
           "Tightness is not tradability; dispersion over cost is.")


if __name__ == "__main__":
    root, out = cli()
    px = root.prices(5)
    w = {d: panel(px, "mid", day=d) for d in DAYS}
    wb = {d: panel(px, "bid_price_1", day=d) for d in DAYS}
    wa = {d: panel(px, "ask_price_1", day=d) for d in DAYS}
    fig_lattice(w, out)
    fig_jump_edge(w, out)
    fig_pebbles(w, wb, wa, out)
    fig_drift(w, out)
    res = fig_multiple_testing(w, out)
    fig_snackpack(w, wb, wa, out)
