#!/usr/bin/env python3
"""Shared figure helpers so every experiment looks the same."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 130,
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

INK = "#1b2430"
RED = "#c0392b"
BLUE = "#2471a3"
GREEN = "#1e8449"
ORANGE = "#ca6f1e"
GREY = "#7f8c8d"
PURPLE = "#7d3c98"
SAFE = "#d5f5e3"      # safe band fill
DEAD = "#fdebd0"      # nothing-finalises fill


def save(fig, name):
    path = os.path.join(FIG, name)
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path}")
    return path


def _plain(v, _=None):
    """Plain decimal labels (no 10^n / 1e5), with thousands separators."""
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if abs(v) >= 1:
        return f"{v:g}"
    return f"{v:g}"


def plain_log(ax, which, ticks):
    """Log axis with plain-number ticks (use instead of 10^n labels)."""
    axis = getattr(ax, f"{which}axis")
    axis.set_major_locator(FixedLocator(ticks))
    axis.set_major_formatter(FuncFormatter(_plain))
    axis.set_minor_locator(NullLocator())


def minor_log(ax, which="y"):
    """Add unlabelled 2..9 minor ticks + light minor gridlines to a log axis."""
    from matplotlib.ticker import LogLocator
    axis = getattr(ax, f"{which}axis")
    axis.set_minor_locator(LogLocator(base=10.0, subs=tuple(range(2, 10))))
    ax.grid(True, which="minor", axis=which, alpha=0.12, lw=0.5)


def ymd(t):
    import datetime
    return datetime.datetime.fromtimestamp(t, datetime.UTC).strftime("%Y-%m")
