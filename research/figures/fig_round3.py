"""Round 3 figures: the Velvetfruit voucher chain."""
import numpy as np
import matplotlib.pyplot as plt

from _common import cli
from research.options import bs_vega, implied_vol, moneyness, tte_years
from research.stats_tools import adf_pvalue, fit_ou
from research.style import ACCENT, ACCENT_2, ACCENT_3, ACCENT_4, INK, MUTED, PALETTE, finish, suptitle

SPOT = "VELVETFRUIT_EXTRACT"
STRIKES = [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500]
ALL_STRIKES = STRIKES + [6000, 6500]
VOLUMES = []  # units traded per strike over the three sample days; filled by main()


def fig_chain(w, out):
    S = w[SPOT]
    fig, axes = plt.subplots(1, 3, figsize=(12.4, 3.6), gridspec_kw={"wspace": 0.3})

    ax = axes[0]
    sub = slice(None, None, 25)
    for K, c in zip([4500, 5000, 5200, 5400], PALETTE):
        ax.scatter(S[sub], w[f"VEV_{K}"][sub], s=2, alpha=0.25, color=c)
        ax.plot([], [], color=c, lw=3, label=f"K = {K}")
    ax.set_yscale("log")
    ax.set_xlabel("VELVETFRUIT_EXTRACT mid")
    ax.set_ylabel("voucher mid (log)")
    ax.set_title("voucher price vs. underlying", pad=6)
    ax.legend(loc="lower right")

    deltas, tvs = [], []
    for K in STRIKES:
        deltas.append(np.polyfit(S, w[f"VEV_{K}"], 1)[0])
        tvs.append((w[f"VEV_{K}"] - np.maximum(S - K, 0)).mean())

    ax = axes[1]
    ax.plot(STRIKES, deltas, "o-", color=ACCENT, ms=5)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("strike")
    ax.set_ylabel(r"$\partial C/\partial S$  (regression)")
    ax.set_title("the empirical delta ladder", pad=6)
    for K, d in zip(STRIKES, deltas):
        if K in (4000, 5300, 5500):
            ax.annotate(f"{d:.2f}", (K, d), textcoords="offset points", xytext=(6, 6),
                        fontsize=8.5, color=INK)

    ax = axes[2]
    ax.bar([str(k) for k in ALL_STRIKES], [max(v, 0.6) for v in VOLUMES], color=ACCENT_3, alpha=0.9)
    ax.set_yscale("log")
    ax.set_ylim(0.5, 3_000)
    ax.set_ylabel("units traded, 3 days (log)")
    ax.set_title("almost nothing trades in the middle", pad=6)
    ax.tick_params(axis="x", rotation=45, labelsize=7.5)
    for i, (k, v) in enumerate(zip(ALL_STRIKES, VOLUMES)):
        if v <= 1:
            ax.annotate("1", (i, 1.0), textcoords="offset points", xytext=(0, 4),
                        ha="center", fontsize=8, color=INK)

    suptitle(fig, "The voucher chain is clean, well behaved, and mostly illiquid",
             f"Round-3 sample data, {len(w):,} snapshots across three days, ten strikes on one underlying.")
    finish(fig, out / "r3_voucher_chain.png",
           "Regressing each voucher on the underlying recovers a delta ladder running from 1.00 at K=4000 "
           "to 0.05 at K=5500, and the deep in-the-money strikes carry no time value at all. But the right "
           "panel is the one that decides the round: VEV_4500, VEV_5000 and VEV_5100 print one unit each "
           "across three days, so anything done with the middle of the chain is done by crossing a wide "
           "spread.")


def fig_intrinsic(px, w, out):
    S = w[SPOT]
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 3.6),
                             gridspec_kw={"width_ratios": [1.6, 1.0], "wspace": 0.24})

    # --- the book around intrinsic, on a readable window ---------------------
    v = px[(px["product"] == "VEV_4000") & (px["day"] == 0)].set_index("timestamp")
    s0 = px[(px["product"] == SPOT) & (px["day"] == 0)].set_index("timestamp")["mid"]
    idx = v.index.intersection(s0.index)[:2_000]
    intrinsic = s0.loc[idx] - 4000
    ax = axes[0]
    ax.fill_between(np.arange(len(idx)), v.loc[idx, "bid_price_1"] - intrinsic,
                    v.loc[idx, "ask_price_1"] - intrinsic, color=MUTED, alpha=0.28, lw=0,
                    label="quoted book, ~21 ticks wide")
    ax.plot(np.arange(len(idx)), v.loc[idx, "mid"] - intrinsic, color=ACCENT, lw=0.8,
            label="mid − intrinsic")
    ax.axhline(0, color=ACCENT_2, lw=1.2, ls="--")
    ax.set_xlabel("snapshot (2,000 of day 0)")
    ax.set_ylabel("ticks relative to $S-K$")
    ax.set_title("VEV_4000: the whole book sits around intrinsic", pad=6)
    ax.legend(loc="upper right", ncols=2)

    ax = axes[1]
    r4000 = w["VEV_4000"] - (S - 4000)
    r4500 = w["VEV_4500"] - (S - 4500)
    bins = np.arange(-4, 4.6, 0.5)
    ax.hist(r4000, bins=bins, alpha=0.75, color=ACCENT, label=f"K=4000, $\\sigma$={r4000.std():.2f}")
    ax.hist(r4500, bins=bins, alpha=0.6, color=ACCENT_4, label=f"K=4500, $\\sigma$={r4500.std():.2f}")
    ax.set_xlabel("mid − intrinsic, ticks")
    ax.set_ylabel("snapshots")
    ax.set_title("the basis never leaves the spread", pad=6)
    ax.legend()

    suptitle(fig, "Deep in-the-money vouchers are a synthetic forward, not an option",
             "The 4000 and 4500 strikes track intrinsic value to within one tick, all day, every day.")
    finish(fig, out / "r3_intrinsic_basis.png",
           "The mid is pinned to intrinsic with a standard deviation below one tick - but the book "
           "around it is 21 ticks wide, and in three days there is not one snapshot where the best ask "
           "sits two ticks below intrinsic. There is no arbitrage to take. What there is, is the "
           "ability to quote inside that book around a fair value you know exactly, and to hedge every "
           "fill one-for-one because the delta is 1.00.")


def fig_smile(w, out):
    rows = []
    sub = w.reset_index().iloc[::40]
    for _, r in sub.iterrows():
        S, T = r[SPOT], tte_years(int(r["day"]), r["timestamp"])
        for K in [5000, 5100, 5200, 5300, 5400, 5500]:
            v = implied_vol(r[f"VEV_{K}"], S, K, T)
            if np.isfinite(v):
                rows.append((K, moneyness(S, K, T), v, float(bs_vega(S, K, T, v))))
    K_, m_, iv_, vega_ = map(np.array, zip(*rows))

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.5),
                             gridspec_kw={"width_ratios": [1.4, 1.0], "wspace": 0.24})
    ax = axes[0]
    ax.scatter(m_, iv_, s=3, alpha=0.15, color=ACCENT)
    a, b, c = np.polyfit(m_, iv_, 2)
    xs = np.linspace(m_.min(), m_.max(), 100)
    ax.plot(xs, np.polyval([a, b, c], xs), color=ACCENT_2, lw=1.8,
            label=f"parabolic fit, $R^2$={np.corrcoef(np.polyval([a,b,c],m_),iv_)[0,1]**2:.2f}")
    for K in [5000, 5300, 5500]:
        sel = K_ == K
        ax.scatter(m_[sel].mean(), iv_[sel].mean(), s=45, color=INK, zorder=5)
        ax.annotate(f"{K}", (m_[sel].mean(), iv_[sel].mean()), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=8.5)
    ax.set_xlabel(r"standardised log-moneyness $\ln(K/S)/\sqrt{T}$")
    ax.set_ylabel("implied volatility")
    ax.set_title(f"the surface is flat at {np.median(iv_):.1%}", pad=6)
    ax.legend(loc="upper center")

    ax = axes[1]
    per_strike = [(K, iv_[K_ == K].std()) for K in [5000, 5100, 5200, 5300, 5400, 5500]]
    ks = [p[0] for p in per_strike]
    sd = [p[1] for p in per_strike]
    move = [s * vega_[K_ == k].mean() for k, s in per_strike]
    ax.bar([str(k) for k in ks], move, color=ACCENT_3, alpha=0.9)
    ax.axhline(1.0, color=ACCENT_2, ls="--", lw=1.3)
    ax.text(0.98, 0.9, "1 tick", transform=ax.transAxes, ha="right", color=ACCENT_2, fontsize=9)
    ax.set_ylabel("price move, ticks")
    ax.set_xlabel("strike")
    ax.set_title(r"vega $\times$ 1$\sigma$ of IV", pad=6)
    ax.tick_params(axis="x", rotation=0, labelsize=8)

    suptitle(fig, "Why we did not trade the volatility smile",
             "Fitting Black-Scholes to the chain is easy. Monetising the result is not.")
    finish(fig, out / "r3_iv_surface.png",
           "Implied volatility is flat at 24.2%: every strike sits between 23.0% and 25.0%, and the daily "
           "median moves less than a quarter of a point. A one-sigma move in IV is worth roughly a tick, "
           "less than the round-trip spread on every strike. The smile is real but it is not tradable; "
           "the delta structure is.")


def fig_pair(px, w, out):
    S = w[SPOT]
    a, b = "VEV_5000", "VEV_5400"
    spread = w[a] - w[b]
    beta, c0 = np.polyfit(S - 5250, spread, 1)
    resid = spread - (beta * (S - 5250) + c0)
    r2 = np.corrcoef(beta * (S - 5250) + c0, spread)[0, 1] ** 2

    # dispersion of the residual around its OWN moving mean, and the width we
    # would have to cross to trade it - the two numbers that decide the trade.
    ref = resid.ewm(alpha=2.0 / 501, adjust=False).mean().shift(1)
    signal_sd = float((resid - ref).std())
    bid = px.pivot_table(index=["day", "timestamp"], columns="product", values="bid_price_1")
    ask = px.pivot_table(index=["day", "timestamp"], columns="product", values="ask_price_1")
    width = float(((ask[a] - bid[b]) - (bid[a] - ask[b])).reindex(resid.index).mean())

    fig, axes = plt.subplots(1, 3, figsize=(12.4, 3.5), gridspec_kw={"wspace": 0.32})
    ax = axes[0]
    ax.scatter((S - 5250)[::20], spread[::20], s=3, alpha=0.2, color=ACCENT)
    xs = np.linspace((S - 5250).min(), (S - 5250).max(), 50)
    ax.plot(xs, beta * xs + c0, color=ACCENT_2, lw=1.8)
    ax.set_xlabel("underlying − 5250")
    ax.set_ylabel(f"{a} − {b}")
    ax.set_title(rf"$\beta$ = {beta:.2f},  $R^2$ = {r2:.2f}", pad=6)

    ax = axes[1]
    x = np.arange(len(spread))
    ax.plot(x, spread - spread.mean(), lw=0.4, color=MUTED, label=f"raw, $\\sigma$={spread.std():.1f}")
    ax.plot(x, resid, lw=0.4, color=ACCENT_3, label=f"hedged, $\\sigma$={resid.std():.1f}")
    ax.set_xlabel("snapshot")
    ax.set_ylabel("deviation from mean")
    ax.set_title("residual after hedging", pad=6)
    ax.legend(loc="upper right")

    ax = axes[2]
    ax.bar(["tradable\nsignal", "cost of\ntrading it"], [signal_sd, width],
           color=[ACCENT_3, ACCENT_2], alpha=0.9, width=0.55)
    ax.set_ylabel("ticks")
    ax.set_title(f"the residual costs {width / signal_sd:.1f}× its own size", pad=6)
    for i, v in enumerate([signal_sd, width]):
        ax.annotate(f"{v:.2f}", (i, v), textcoords="offset points", xytext=(0, 4),
                    ha="center", fontsize=9, color=INK)
    ax.text(0.24, 0.30, "σ around its\nEWMA mean", transform=ax.transAxes,
            ha="center", fontsize=7.5, color=MUTED)

    suptitle(fig, "A voucher spread is a delta position, and its residual is not tradable",
             "Removing the underlying leaves a clean signal that is far smaller than the spread you must cross.")
    finish(fig, out / "r3_pair_beta_hedge.png",
           "98% of the 5000-5400 spread's variance is the underlying moving, and beta is exactly the "
           "difference of the two deltas. Regressing it out cuts sigma from 12.5 ticks to 1.7 - but around "
           "its own moving mean the residual disperses by 0.64 ticks against 7.42 ticks of executable "
           "width. The elegant object is the untradable one; the chain's value is leverage on the "
           "underlying, not relative value between strikes.")


if __name__ == "__main__":
    root, out = cli()
    px, tr = root.prices(3), root.trades(3)
    w = px.pivot_table(index=["day", "timestamp"], columns="product", values="mid").dropna()
    VOLUMES.extend(int(tr[tr["symbol"] == f"VEV_{K}"]["quantity"].sum()) for K in ALL_STRIKES)
    fig_chain(w, out)
    fig_intrinsic(px, w, out)
    fig_smile(w, out)
    fig_pair(px, w, out)
