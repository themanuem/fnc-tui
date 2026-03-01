"""Transaction heatmap - months vs value buckets."""

import numpy as np
import pandas as pd
from rich.text import Text
from textual.widgets import Static

_BLOCK = "▪"
_EMPTY = "·"

# Orange intensity shades for frequency
_SHADES = ["#2A2A2A", "#4A3520", "#7A5530", "#A06820", "#E8871E"]

# Value bucket edges (expenses as absolute values)
_BUCKET_EDGES = [0, 10, 25, 50, 100, 250, 500, 1000, float("inf")]
_BUCKET_LABELS = [
    "0-10", "10-25", "25-50", "50-100",
    "100-250", "250-500", "500-1k", "1k+",
]

_MONTH_LABELS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


class SpendingHeatmap(Static):
    """Heatmap: rows = calendar months (Jan-Dec), cols = value buckets.

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

        # Use absolute amounts for bucketing
        abs_amounts = df["amount"].abs()
        months = df["date"].dt.month  # 1-12

        # Build 12x8 frequency grid
        grid = np.zeros((12, len(_BUCKET_LABELS)), dtype=int)
        for month_val, amount_val in zip(months, abs_amounts):
            for b in range(len(_BUCKET_EDGES) - 1):
                if _BUCKET_EDGES[b] <= amount_val < _BUCKET_EDGES[b + 1]:
                    grid[month_val - 1][b] += 1
                    break

        max_freq = grid.max() or 1

        lines = []

        # Header row with bucket labels
        header = Text("      ")
        for label in _BUCKET_LABELS:
            header.append(f"{label:>7s} ", style="#777777")
        lines.append(header)

        # Data rows
        for m in range(12):
            line = Text()
            line.append(f" {_MONTH_LABELS[m]:>3s}  ", style="#555555")
            for b in range(len(_BUCKET_LABELS)):
                freq = grid[m][b]
                if freq == 0:
                    line.append(f"  {_EMPTY}     ", style="#2A2A2A")
                else:
                    ratio = freq / max_freq
                    shade_idx = min(int(ratio * (len(_SHADES) - 1)) + 1, len(_SHADES) - 1)
                    color = _SHADES[shade_idx]
                    line.append(f" {_BLOCK}{_BLOCK}{_BLOCK}    ", style=color)
            lines.append(line)

        # Legend
        legend = Text("\n      ")
        legend.append("fewer ", style="#555555")
        for color in _SHADES:
            legend.append(f"{_BLOCK} ", style=color)
        legend.append("more", style="#555555")
        lines.append(legend)

        result = Text("\n").join(lines)
        self.update(result)

    def refresh_data(self, df: pd.DataFrame):
        self._df = df
        self._render_heatmap()
