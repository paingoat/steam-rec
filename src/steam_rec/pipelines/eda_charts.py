"""Static EDA charts (PNG) from eda_summary.json. Single-series charts: one hue, thin marks, recessive axes."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SERIES = "#2a78d6"
SURFACE = "#fcfcfb"
INK, INK2 = "#0b0b0b", "#52514e"


def _style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    ax.tick_params(colors=INK2, labelsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#d0cfca")
    ax.grid(axis="y", color="#ecebe7", linewidth=0.8)
    ax.set_axisbelow(True)


def _k(n: int) -> str:
    return f"{n // 1000}k" if n >= 1000 else str(n)


def _rng(lo: int, hi: int) -> str:
    return _k(lo) if lo == hi else f"{_k(lo)}–{_k(hi)}"


def _bar(path: Path, labels, values, title, xlabel, ylabel, log=False) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.6), facecolor=SURFACE)
    ax.bar(range(len(values)), values, color=SERIES, width=0.8, edgecolor=SURFACE, linewidth=2)
    ax.set_xticks(range(len(labels)), labels, rotation=0 if len(labels) <= 8 else 35, ha="center" if len(labels) <= 8 else "right")
    if log:
        ax.set_yscale("log")
    _style(ax, title, xlabel, ylabel)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def make_charts(summary_path: Path) -> list[Path]:
    rep = json.loads(summary_path.read_text())
    out = summary_path.parent
    files = []

    years = sorted(rep["by_year"])
    p = out / "reviews_by_year.png"
    _bar(p, years, [rep["by_year"][y][0] / 1e6 for y in years], "Reviews per year", "year", "reviews (millions)")
    files.append(p)

    h = {int(k): v for k, v in rep["chart_user_degree_hist"].items()}
    ks = sorted(h)
    p = out / "user_degree_hist.png"
    _bar(p, [_rng(2**k, 2 ** (k + 1) - 1) for k in ks], [h[k] for k in ks],
         "Users by number of reviews (log2 buckets)", "reviews per user", "users (log scale)", log=True)
    files.append(p)

    h = {int(k): v for k, v in rep["chart_hours_hist"].items() if k is not None and k != "None"}
    ks = sorted(h)
    p = out / "hours_hist.png"
    _bar(p, ["<1" if k == 0 else _rng(2**k - 1, 2 ** (k + 1) - 2) for k in ks], [h[k] / 1e6 for k in ks],
         "Reviews by hours played (log2 buckets)", "hours", "reviews (millions)")
    files.append(p)
    return files
