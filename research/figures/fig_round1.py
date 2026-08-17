"""Round 1 figures: a deterministic fair value and a stable anchor."""
import numpy as np
import matplotlib.pyplot as plt

from _common import cli
from research.style import ACCENT, ACCENT_2, ACCENT_3, MUTED, INK as INKLESS, finish, suptitle
from research.stats_tools import fit_ou

OSMIUM, PEPPER = "ASH_COATED_OSMIUM", "INTARIAN_PEPPER_ROOT"


def fair_value_pepper(day, t):
    """F(t) = 12000 + 1000*day + t/1000 - recovered exactly from the sample data."""
    return 12000.0 + 1000.0 * day + t / 1000.0


def fig_pepper(px, out):
    g = px[px["product"] == PEPPER]
    fig, axes = plt.subplots(1, 3, figsize=(12.4, 3.5),
                             gridspec_kw={"width_ratios": [1.9, 1.0, 1.0], "wspace": 0.28})

    ax = axes[0]
    w = g[(g["day"] == 0) & (g["timestamp"].between(400_000, 430_000))]
    ax.fill_between(w["timestamp"], w["bid_price_1"], w["ask_price_1"],
                    color=MUTED, alpha=0.22, lw=0, label="quoted spread")
    ax.plot(w["timestamp"], w["mid"], color=ACCENT, lw=1.0, label="mid")
    ax.plot(w["timestamp"], fair_value_pepper(0, w["timestamp"]), color=ACCENT_2, ls="--",
            lw=1.6, label=r"$F(t)=12000+1000d+t/1000$")
    ax.set_title("30,000 ticks of day 0", pad=6)
    ax.set_xlabel("timestamp")
    ax.set_ylabel("price")
    ax.legend(loc="upper left")

    resid = g["mid"].to_numpy() - fair_value_pepper(g["day"].to_numpy(), g["timestamp"].to_numpy())
    ax = axes[1]
    ax.hist(resid, bins=np.arange(-8, 8.5, 0.5), color=ACCENT_3, alpha=0.9)
    ax.set_title(f"residual  ($\\sigma$ = {resid.std():.2f})", pad=6)
    ax.set_xlabel("mid − F(t), ticks")
    ax.set_ylabel("snapshots")

    ax = axes[2]
    lag = [np.corrcoef(resid[:-k], resid[k:])[0, 1] for k in range(1, 26)]
    ax.bar(range(1, 26), lag, color=MUTED, width=0.75)
    ax.axhline(0, color=INKLESS, lw=0.8)
    ax.set_ylim(-0.15, 0.15)
    ax.set_title("residual autocorrelation", pad=6)
    ax.set_xlabel("lag (snapshots)")

    suptitle(fig, "Pepper root is a straight line plus noise",
             f"Three sample days, {len(g):,} two-sided snapshots. One line per day explains everything.")
    finish(fig, out / "r1_pepper_deterministic_drift.png",
           "The fair value is not a random walk. Fitting price on timestamp returns a slope of exactly "
           "1.000 per 1,000 ticks and an intercept of exactly 10,000 / 11,000 / 12,000 on the three days; "
           "what is left is white noise of 1.2 ticks against a 13-tick quoted spread.")


def fig_osmium(px, out):
    g = px[(px["product"] == OSMIUM) & (px["day"] == 0)]
    fig, axes = plt.subplots(1, 3, figsize=(12.4, 3.5),
                             gridspec_kw={"width_ratios": [1.9, 1.0, 1.0], "wspace": 0.28})

    ax = axes[0]
    w = g[g["timestamp"].between(200_000, 260_000)]
    ax.fill_between(w["timestamp"], w["bid_price_1"], w["ask_price_1"],
                    color=MUTED, alpha=0.22, lw=0, label="quoted spread")
    ax.plot(w["timestamp"], w["wall_mid"], color=ACCENT, lw=1.1, label="wall mid")
    ax.axhline(10_000, color=ACCENT_2, ls="--", lw=1.5, label="anchor = 10,000")
    ax.set_title("60,000 ticks of day 0", pad=6)
    ax.set_xlabel("timestamp")
    ax.set_ylabel("price")
    ax.legend(loc="lower left", ncols=3)

    dev = (px[px["product"] == OSMIUM]["wall_mid"] - 10_000).dropna()
    ax = axes[1]
    ax.hist(dev, bins=np.arange(-20, 20.5, 1), color=ACCENT_3, alpha=0.9)
    ax.set_title(f"wall mid − 10,000  ($\\sigma$ = {dev.std():.1f})", pad=6)
    ax.set_xlabel("ticks")
    ax.set_ylabel("snapshots")

    ax = axes[2]
    x = g["wall_mid"].to_numpy()
    ou = fit_ou(x)
    ax.scatter(x[:-1] - 10_000, np.diff(x), s=2.5, alpha=0.12, color=ACCENT)
    b, a = np.polyfit(x[:-1] - 10_000, np.diff(x), 1)
    xs = np.linspace(-16, 16, 50)
    ax.plot(xs, b * xs + a, color=ACCENT_2, lw=1.7)
    ax.axhline(0, color=INKLESS, lw=0.8)
    ax.set_title(f"$\\phi$ = {ou.phi:.3f}, half-life ≈ {ou.half_life:.0f} snapshots", pad=6)
    ax.set_xlabel("deviation from anchor")
    ax.set_ylabel("next-snapshot change")

    suptitle(fig, "Osmium is an Ornstein–Uhlenbeck process pinned at 10,000",
             "A ~16-tick quoted spread around a mean that never moves: the textbook market-making asset.")
    finish(fig, out / "r1_osmium_anchor.png",
           "The right-hand regression is the whole alpha. A deviation of d ticks from the anchor decays "
           "with a half-life of about 28 snapshots, so quoting inside a 16-tick spread earns the spread "
           "and the reversion at the same time.")


def fig_tolerance(px, tr, out):
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    fv = {OSMIUM: lambda d, t: 10_000.0 + 0.0 * t, PEPPER: fair_value_pepper}
    for col, prod in zip((ACCENT, ACCENT_2), (OSMIUM, PEPPER)):
        g = tr[tr["symbol"] == prod]
        dev = g["price"].to_numpy() - fv[prod](g["day"].to_numpy(), g["timestamp"].to_numpy())
        ax.hist(dev, bins=np.arange(-30, 30.5, 1.5), alpha=0.55, color=col,
                label=f"{prod}   max |dev| = {np.abs(dev).max():.1f}")
    ax.axvline(0, color=INKLESS, lw=0.9)
    ax.set_xlabel("executed price − fair value (ticks)")
    ax.set_ylabel("printed trades")
    ax.legend(loc="upper left")
    suptitle(fig, "How far from fair value will the counterparties actually trade?",
             "Every print in the three sample days, measured against the reconstructed fair value.")
    finish(fig, out / "r1_bot_aggression_tolerance.png",
           "Realised bot aggression against the quotes that happened to exist - not a fill boundary. "
           "The osmium tail stops at +26 because that is the widest ask ever posted in the sample "
           "data, so the right edge is set by the book rather than by the counterparties.")


if __name__ == "__main__":
    root, out = cli()
    px, tr = root.prices(1), root.trades(1)
    fig_pepper(px, out)
    fig_osmium(px, out)
    fig_tolerance(px, tr, out)
