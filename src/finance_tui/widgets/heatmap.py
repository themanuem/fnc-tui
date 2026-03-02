"""Transaction heatmap - months vs value buckets."""

import numpy as np
import pandas as pd
from rich.text import Text
from textual.widgets import Static

# Orange intensity shades for frequency
_SHADES = ["#2A2A2A", "#3D2E1A", "#4A3520", "#6A4A28", "#7A5530", "#A06820", "#C47A1E", "#E8871E"]

# Value bucket edges (expenses as absolute values)
_BUCKET_EDGES = [0, 5, 10, 20, 35, 50, 75, 100, 150, 250, 500, 750, 1000, 2000, float("inf")]
_BUCKET_LABELS = [
    "   5 ", "  10 ", "  20 ", "  35 ", "  50 ", "  75 ", " 100 ",
    " 150 ", " 250 ", " 500 ", " 750 ", "  1k ", "  2k ", "  2k+",
]

_MONTH_LABELS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


class SpendingHeatmap(Static):
    """Heatmap: rows = calendar months, cols = value buckets.

    Each cell shows how many transactions fall into that month+value range.
    """

    can_focus = True

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(**kwargs)
        self._df = df
        self.border_title = "Activity Heatmap"

    def on_mount(self):
        self._render_heatmap()

    def _render_heatmap(self):
        df = self._df
        if df.empty:
            self.update("No data")
            return

        n_buckets = len(_BUCKET_LABELS)
        abs_amounts = df["amount"].abs()
        months = df["date"].dt.month  # 1-12

        # Build 12 x n_buckets frequency grid
        grid = np.zeros((12, n_buckets), dtype=int)
        for month_val, amount_val in zip(months, abs_amounts):
            for b in range(len(_BUCKET_EDGES) - 1):
                if _BUCKET_EDGES[b] <= amount_val < _BUCKET_EDGES[b + 1]:
                    grid[month_val - 1][b] += 1
                    break

        max_freq = grid.max() or 1
        n_shades = len(_SHADES)

        lines = []

        # Header row — 5 chars per column to align with ▪▪▪▪▪
        header = Text("     ")
        for label in _BUCKET_LABELS:
            header.append(label, style="#555555")
        lines.append(header)

        # Data rows — 5 blocks per cell, no spacing
        for m in range(12):
            line = Text()
            line.append(f" {_MONTH_LABELS[m]} ", style="#555555")
            for b in range(n_buckets):
                freq = grid[m][b]
                if freq == 0:
                    line.append("  ·  ", style="#2A2A2A")
                else:
                    ratio = freq / max_freq
                    shade_idx = min(int(ratio * (n_shades - 1)) + 1, n_shades - 1)
                    color = _SHADES[shade_idx]
                    line.append("▪▪▪▪▪", style=color)
            lines.append(line)

        # Legend
        legend = Text("\n     ")
        legend.append("less ", style="#555555")
        for color in _SHADES:
            legend.append("▪▪", style=color)
        legend.append("more", style="#555555")
        lines.append(legend)

        result = Text("\n").join(lines)
        self.update(result)

    def refresh_data(self, df: pd.DataFrame):
        self._df = df
        self._render_heatmap()
