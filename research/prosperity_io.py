"""Loading and normalising the Prosperity data capsules.

Every round ships two semicolon-delimited CSVs per day:

* ``prices_round_<R>_day_<D>.csv`` - an order-book snapshot every 100 timestamps,
  with up to three price levels per side, a ``mid_price`` column and a
  cumulative ``profit_and_loss`` column.
* ``trades_round_<R>_day_<D>.csv``  - the public trade tape. From Round 4 onward
  the ``buyer``/``seller`` columns carry counterparty identifiers.

Two details bite people every year and are handled here:

1. When a side of the book is empty the exchange still emits a row, and
   ``mid_price`` is meaningless (it appears as ``0`` or ``NaN``). Roughly 4% of
   Round-1 snapshots have at least one empty side. Leaving those rows in
   destroys every summary statistic you compute.
2. Timestamps run ``0 .. 999_900`` in steps of 100, i.e. 10,000 snapshots per
   simulated day - not 100,000. Getting this wrong silently corrupts any
   time-to-expiry calculation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

TICKS_PER_DAY = 1_000_000
SNAPSHOT_STEP = 100

ROUND_DAYS = {1: [-2, -1, 0], 2: [-1, 0, 1], 3: [0, 1, 2], 4: [1, 2, 3], 5: [2, 3, 4]}


@dataclass(frozen=True)
class DataRoot:
    """Points at the extracted Prosperity data capsules.

    Expected layout (the capsules are IMC's, so they are not redistributed
    here - download them from the competition dashboard)::

        <root>/ROUND_1/prices_round_1_day_-2.csv
        <root>/ROUND_1/trades_round_1_day_-2.csv
        ...
    """

    root: Path

    def prices(self, rnd: int, days: list[int] | None = None) -> pd.DataFrame:
        days = ROUND_DAYS[rnd] if days is None else days
        frames = []
        for d in days:
            p = self.root / f"ROUND_{rnd}" / f"prices_round_{rnd}_day_{d}.csv"
            frames.append(pd.read_csv(p, sep=";"))
        return clean_book(pd.concat(frames, ignore_index=True))

    def trades(self, rnd: int, days: list[int] | None = None) -> pd.DataFrame:
        days = ROUND_DAYS[rnd] if days is None else days
        frames = []
        for d in days:
            p = self.root / f"ROUND_{rnd}" / f"trades_round_{rnd}_day_{d}.csv"
            frames.append(pd.read_csv(p, sep=";").assign(day=d))
        return pd.concat(frames, ignore_index=True)


def clean_book(df: pd.DataFrame) -> pd.DataFrame:
    """Drop one-sided snapshots and add derived microstructure columns."""
    df = df[df["bid_price_1"].notna() & df["ask_price_1"].notna()].copy()
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    df["mid"] = (df["ask_price_1"] + df["bid_price_1"]) / 2.0
    df["wall_mid"] = wall_mid(df)
    df["imbalance"] = (df["bid_volume_1"] - df["ask_volume_1"]) / (
        df["bid_volume_1"] + df["ask_volume_1"]
    )
    return df


def wall_mid(df: pd.DataFrame) -> pd.Series:
    """Mid-price computed from the *deepest* level on each side.

    The Prosperity books are populated by a small number of bot market makers.
    One of them quotes a wide, very deep pair of levels (the "wall"); the noisy
    tighter levels come from smaller, more erratic participants. Averaging the
    two walls gives a far more stable fair-value estimate than the touch mid -
    on Round-1 osmium it cuts the tick-to-tick variance of the estimator by
    roughly a factor of three.
    """
    bid_p = df[[f"bid_price_{i}" for i in (1, 2, 3)]].to_numpy(dtype=float)
    bid_v = df[[f"bid_volume_{i}" for i in (1, 2, 3)]].to_numpy(dtype=float)
    ask_p = df[[f"ask_price_{i}" for i in (1, 2, 3)]].to_numpy(dtype=float)
    ask_v = df[[f"ask_volume_{i}" for i in (1, 2, 3)]].to_numpy(dtype=float)
    bid_v = np.nan_to_num(bid_v, nan=-1.0)
    ask_v = np.nan_to_num(ask_v, nan=-1.0)
    bw = np.take_along_axis(bid_p, bid_v.argmax(axis=1)[:, None], axis=1).ravel()
    aw = np.take_along_axis(ask_p, ask_v.argmax(axis=1)[:, None], axis=1).ravel()
    return pd.Series((bw + aw) / 2.0, index=df.index)


def panel(df: pd.DataFrame, value: str = "mid", day: int | None = None) -> pd.DataFrame:
    """Wide (timestamp x product) matrix of a column, forward-filled."""
    sub = df if day is None else df[df["day"] == day]
    out = sub.pivot_table(index="timestamp", columns="product", values=value)
    return out.ffill().dropna(how="any")
