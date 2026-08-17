"""Statistical tools we actually used to separate signal from noise.

Nothing here is exotic. The point of the module is that every claim made in
the write-up has a small, readable function behind it - in particular the
multiple-testing machinery, which is the single most important defence in a
competition where you are handed 50 products and three days of data.
"""
from __future__ import annotations

import itertools
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from statsmodels.tsa.stattools import adfuller  # noqa: E402


# --------------------------------------------------------------------------- #
# Stationarity / mean reversion
# --------------------------------------------------------------------------- #
def adf_pvalue(x, maxlag: int = 20, subsample: int = 1) -> float:
    x = np.asarray(x, dtype=float)[::subsample]
    x = x[np.isfinite(x)]
    if x.size < 50 or np.allclose(x, x[0]):
        return 1.0
    try:
        return float(adfuller(x, maxlag=maxlag, regression="c")[1])
    except Exception:
        return 1.0


@dataclass
class OUFit:
    """Discrete OU / AR(1) fit:  x_{t+1} - mu = phi (x_t - mu) + eps."""

    mu: float
    phi: float
    sigma: float

    @property
    def half_life(self) -> float:
        """Ticks for a deviation to decay by half. inf if phi >= 1."""
        return np.inf if self.phi >= 1 or self.phi <= 0 else float(np.log(2) / -np.log(self.phi))


def fit_ou(x) -> OUFit:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    x0, x1 = x[:-1], x[1:]
    phi, c = np.polyfit(x0, x1, 1)
    mu = c / (1 - phi) if abs(1 - phi) > 1e-12 else float(np.mean(x))
    resid = x1 - (phi * x0 + c)
    return OUFit(mu=float(mu), phi=float(phi), sigma=float(resid.std(ddof=1)))


# --------------------------------------------------------------------------- #
# Multiple testing
# --------------------------------------------------------------------------- #
def pairwise_coint_scan(
    is_panel: pd.DataFrame, oos_panel: pd.DataFrame, alpha: float = 0.05, subsample: int = 10
) -> pd.DataFrame:
    """In-sample cointegration scan with a genuine out-of-sample re-test.

    For every unordered pair (a, b) we regress a on b in-sample, run ADF on the
    residual, and - for the pairs that pass - re-run ADF on the *same* hedge
    ratio applied to held-out data. The gap between the two hit rates is the
    honest measure of how much of a "cointegration" screen is real.
    """
    prods = sorted(set(is_panel.columns) & set(oos_panel.columns))
    rows = []
    for a, b in itertools.combinations(prods, 2):
        x, y = is_panel[a].to_numpy(float), is_panel[b].to_numpy(float)
        beta = float(np.polyfit(y, x, 1)[0])
        p_is = adf_pvalue(x - beta * y, subsample=subsample)
        if p_is >= alpha:
            continue
        r_oos = oos_panel[a].to_numpy(float) - beta * oos_panel[b].to_numpy(float)
        rows.append((a, b, beta, p_is, adf_pvalue(r_oos, subsample=subsample)))
    out = pd.DataFrame(rows, columns=["a", "b", "beta", "p_is", "p_oos"])
    out.attrs["n_pairs"] = len(prods) * (len(prods) - 1) // 2
    return out


def random_walk_null(n_series: int, n_obs: int, seed: int = 0, subsample: int = 1) -> np.ndarray:
    """ADF p-values for every pair of *independent* random walks.

    This is the control experiment. If a screen finds "cointegrated" pairs at a
    rate no better than this, the screen has found nothing.
    """
    rng = np.random.default_rng(seed)
    rw = np.cumsum(rng.standard_normal((n_obs, n_series)), axis=0)
    ps = []
    for i, j in itertools.combinations(range(n_series), 2):
        beta = float(np.polyfit(rw[:, j], rw[:, i], 1)[0])
        ps.append(adf_pvalue(rw[:, i] - beta * rw[:, j], subsample=subsample))
    return np.asarray(ps)


# --------------------------------------------------------------------------- #
# Event studies
# --------------------------------------------------------------------------- #
def event_study(
    price: pd.Series, event_ts, horizons=(100, 200, 500, 1_000, 2_000, 5_000)
) -> pd.DataFrame:
    """Mean forward price change after a set of events, with Newey-free t-stats.

    ``price`` must be indexed by timestamp. Returns one row per horizon with the
    mean move, its standard error and a t-statistic. Overlapping windows inflate
    the t-stats, so treat them as a screening device, not a p-value.
    """
    price = price.dropna()
    idx = price.index.to_numpy()
    vals = price.to_numpy(float)
    rows = []
    for h in horizons:
        moves = []
        for t0 in event_ts:
            j = np.searchsorted(idx, t0)
            if j >= len(idx) or idx[j] != t0:
                continue
            k = np.searchsorted(idx, t0 + h, side="right") - 1
            if k <= j:
                continue
            moves.append(vals[k] - vals[j])
        m = np.asarray(moves)
        if m.size == 0:
            continue
        se = m.std(ddof=1) / np.sqrt(m.size)
        rows.append(dict(horizon=h, n=m.size, mean=m.mean(), se=se, t=m.mean() / se if se else np.nan))
    return pd.DataFrame(rows)


def block_bootstrap_ci(x, stat=np.mean, block: int = 200, n_boot: int = 2_000, seed: int = 0):
    """Stationary-ish block bootstrap CI - the right tool for autocorrelated PnL."""
    x = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(len(x) / block))
    starts = rng.integers(0, max(len(x) - block, 1), size=(n_boot, n_blocks))
    samples = np.empty(n_boot)
    for i in range(n_boot):
        samples[i] = stat(np.concatenate([x[s : s + block] for s in starts[i]])[: len(x)])
    return float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


# --------------------------------------------------------------------------- #
# Jump / lattice detection
# --------------------------------------------------------------------------- #
def detect_jumps(mid: pd.Series, threshold: float = 80.0) -> pd.Series:
    """Signed jumps whose absolute size exceeds ``threshold``."""
    d = mid.dropna().diff()
    return d[d.abs() >= threshold]


def alternation_rate(jumps: pd.Series) -> tuple[float, int]:
    """P(next jump has the opposite sign). 0.5 means there is no structure."""
    s = np.sign(jumps.to_numpy(float))
    if s.size < 2:
        return float("nan"), 0
    return float(np.mean(s[1:] != s[:-1])), int(s.size - 1)
