"""Category breakdown panels - btop disk-style compact bars."""

from rich.text import Text

from finance_tui import analytics
from finance_tui.config import CURRENCY
from finance_tui.widgets.panel_table import PanelTable

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


class ExpenseCategoryPanel(PanelTable):
    """Compact expense breakdown with color-coded bars (red shades)."""

    def __init__(self, df, month: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._df = df
        self._month = month
        self.border_title = "Expenses by Category"

    def on_mount(self) -> None:
        self._build_rows()

    def _build_rows(self) -> None:
        expenses = analytics.expenses_by_category(self._df, self._month)
        if not expenses:
            line = Text(" No expenses", style="#555555")
            self._load_rows([(line, "")])
            return

        sorted_cats = sorted(expenses.items(), key=lambda x: x[1])
        max_abs = max(abs(v) for _, v in sorted_cats) or 1

        rows: list[tuple[Text, str]] = []
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

            rows.append((line, f"cat:{cat} <0"))

        self._load_rows(rows)

    def refresh_data(self, df, month: str | None = None):
        self._df = df
        self._month = month
        self._build_rows()


class IncomeCategoryPanel(PanelTable):
    """Compact income breakdown with color-coded bars (green shades)."""

    def __init__(self, df, month: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._df = df
        self._month = month
        self.border_title = "Income by Category"

    def on_mount(self) -> None:
        self._build_rows()

    def _build_rows(self) -> None:
        income = analytics.income_by_category(self._df, self._month)
        if not income:
            line = Text(" No income", style="#555555")
            self._load_rows([(line, "")])
            return

        sorted_cats = sorted(income.items(), key=lambda x: x[1], reverse=True)
        max_val = max(v for _, v in sorted_cats) or 1

        rows: list[tuple[Text, str]] = []
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

            rows.append((line, f"cat:{cat} >0"))

        self._load_rows(rows)

    def refresh_data(self, df, month: str | None = None):
        self._df = df
        self._month = month
        self._build_rows()
