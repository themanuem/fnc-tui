"""Category breakdown panels - btop disk-style compact bars."""

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Static

from finance_tui import analytics
from finance_tui.config import CURRENCY
from finance_tui.widgets.scroll_arrows import ScrollablePanel

_BAR_WIDTH = 14
_FILL = "▪"
_EMPTY = "·"

# Red shades: higher spend = more vibrant
_RED_SHADES = ["#4A2020", "#6B2A2A", "#8B3535", "#B04040", "#D9534F"]
# Green shades: higher income = more vibrant
_GREEN_SHADES = ["#1A3A1A", "#2D5A2D", "#3D7A3D", "#4A9A4A", "#5CB85C"]


def _shade(ratio: float, palette: list[str]) -> str:
    """Pick a color from palette based on ratio (0..1)."""
    idx = min(int(ratio * len(palette)), len(palette) - 1)
    return palette[idx]


class ExpenseCategoryPanel(ScrollablePanel):
    """Compact expense breakdown with color-coded bars (red shades)."""

    def __init__(self, df, month: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._df = df
        self._month = month
        self.border_title = "Expenses by Category"

    def compose(self) -> ComposeResult:
        self._filters = []
        expenses = analytics.expenses_by_category(self._df, self._month)
        if not expenses:
            self._filters.append("")
            yield Static(" No expenses", classes="bar-row")
            return

        sorted_cats = sorted(expenses.items(), key=lambda x: x[1])
        max_abs = max(abs(v) for _, v in sorted_cats) or 1

        for cat, val in sorted_cats:
            abs_val = abs(val)
            ratio = abs_val / max_abs
            filled = max(1, int(ratio * _BAR_WIDTH))
            empty = _BAR_WIDTH - filled
            bar_color = _shade(ratio, _RED_SHADES)

            line = Text()
            line.append(f" {cat:15s}", style="#BBBBBB")
            line.append(_FILL * filled, style=bar_color)
            line.append(_EMPTY * empty, style="#2A2A2A")
            line.append(f" {abs_val:>9,.2f} {CURRENCY}", style="#777777")

            self._filters.append(f"cat:{cat} <0")
            yield Static(line, classes="bar-row")

    def refresh_data(self, df, month: str | None = None):
        self._df = df
        self._month = month
        self.remove_children()
        for w in self.compose():
            self.mount(w)


class IncomeCategoryPanel(ScrollablePanel):
    """Compact income breakdown with color-coded bars (green shades)."""

    def __init__(self, df, month: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._df = df
        self._month = month
        self.border_title = "Income by Category"

    def compose(self) -> ComposeResult:
        self._filters = []
        income = analytics.income_by_category(self._df, self._month)
        if not income:
            self._filters.append("")
            yield Static(" No income", classes="bar-row")
            return

        sorted_cats = sorted(income.items(), key=lambda x: x[1], reverse=True)
        max_val = max(v for _, v in sorted_cats) or 1

        for cat, val in sorted_cats:
            ratio = val / max_val
            filled = max(1, int(ratio * _BAR_WIDTH))
            empty = _BAR_WIDTH - filled
            bar_color = _shade(ratio, _GREEN_SHADES)

            line = Text()
            line.append(f" {cat:15s}", style="#BBBBBB")
            line.append(_FILL * filled, style=bar_color)
            line.append(_EMPTY * empty, style="#2A2A2A")
            line.append(f" {val:>9,.2f} {CURRENCY}", style="#777777")

            self._filters.append(f"cat:{cat} >0")
            yield Static(line, classes="bar-row")

    def refresh_data(self, df, month: str | None = None):
        self._df = df
        self._month = month
        self.remove_children()
        for w in self.compose():
            self.mount(w)
