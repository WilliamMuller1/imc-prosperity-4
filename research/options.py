"""Black-Scholes utilities for the Velvetfruit voucher chain (Rounds 3-4).

The vouchers are European calls on ``VELVETFRUIT_EXTRACT`` with a 7-day life,
one competition round per day. Time to expiry is therefore

    TTE(day, t) = TTE_0 - day - t / 1_000_000        [days]

and we quote it in years with a 365-day convention. The convention only shifts
the *level* of implied volatility, not the shape of the surface or any of the
relative-value conclusions drawn from it.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

DAYS_PER_YEAR = 365.0


def bs_call(S, K, T, sigma, r: float = 0.0):
    S, K, T, sigma = map(np.asarray, (S, K, T, sigma))
    intrinsic = np.maximum(S - K, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        px = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return np.where((T <= 0) | (sigma <= 0), intrinsic, px)


def bs_delta(S, K, T, sigma):
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1)


def bs_vega(S, K, T, sigma):
    """dPrice/dSigma, in price units per 1.00 of volatility."""
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    return S * np.sqrt(T) * norm.pdf(d1)


def implied_vol(price, S, K, T, lo: float = 1e-4, hi: float = 5.0):
    """Robust IV solve; returns NaN when the quote is outside the no-arb bounds."""
    if not np.isfinite(price) or T <= 0:
        return np.nan
    if price <= max(S - K, 0.0) + 1e-9 or price >= S:
        return np.nan
    try:
        return brentq(lambda s: float(bs_call(S, K, T, s)) - price, lo, hi, maxiter=200)
    except ValueError:
        return np.nan


def moneyness(S, K, T):
    """Standardised log-moneyness m = ln(K/S) / sqrt(T) - the usual smile x-axis."""
    return np.log(np.asarray(K) / np.asarray(S)) / np.sqrt(np.asarray(T))


def tte_years(day: int, timestamp, tte_at_day0: float = 8.0):
    """Continuous time to expiry, in years, for the Round-3 historical days."""
    return (tte_at_day0 - day - np.asarray(timestamp) / 1_000_000.0) / DAYS_PER_YEAR
