"""Shared matplotlib styling so every figure in the repository looks the same.

The palette is deliberately restrained: one accent colour per figure, grey for
context, and no chart junk. Figures are rendered on an opaque light background
so that they remain readable in both GitHub themes.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

INK = "#1b1f24"
MUTED = "#8a929b"
GRID = "#dfe3e8"
ACCENT = "#1f4e79"       # deep blue   - primary series
ACCENT_2 = "#c1452b"     # brick red   - contrast series / danger
ACCENT_3 = "#2e7d6f"     # teal        - secondary series / "good"
ACCENT_4 = "#b8860b"     # dark gold   - tertiary
BG = "#ffffff"

PALETTE = [ACCENT, ACCENT_2, ACCENT_3, ACCENT_4, "#6a4c93", "#4f5d75"]


def use_style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "savefig.facecolor": BG,
            "savefig.dpi": 170,
            "figure.dpi": 110,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans"],
            "font.size": 10,
            "axes.titlesize": 11.5,
            "axes.titleweight": "semibold",
            "axes.titlelocation": "left",
            "axes.labelsize": 10,
            "axes.labelcolor": INK,
            "axes.edgecolor": MUTED,
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "xtick.color": INK,
            "ytick.color": INK,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "lines.linewidth": 1.3,
            "lines.solid_capstyle": "round",
            "axes.prop_cycle": mpl.cycler(color=PALETTE),
        }
    )
    for spine in ("top", "right"):
        mpl.rcParams[f"axes.spines.{spine}"] = False


def suptitle(fig, title: str, subtitle: str | None = None) -> None:
    """Left-aligned figure title (+ optional grey subtitle) above the panels."""
    h = fig.get_size_inches()[1]
    top = 1.0 + 0.42 / h
    fig.suptitle(title, x=0.005, ha="left", fontsize=12.5, fontweight="semibold", y=top)
    if subtitle:
        fig.text(0.005, 1.0 + 0.10 / h, subtitle, ha="left", va="bottom", fontsize=9.5, color=MUTED)


def caption(fig, text: str) -> None:
    """Small grey caption under a figure - used as the figure's 'so what'."""
    fig.text(0.01, -0.015, text, ha="left", va="top", fontsize=8.5, color=MUTED, wrap=True)


def finish(fig, path, caption_text: str | None = None) -> None:
    if caption_text:
        caption(fig, caption_text)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"wrote {path}")
