"""Budget panel - shows months over budget per category."""

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Static

from finance_tui import analytics
from finance_tui.config import CURRENCY
from finance_tui.widgets.scroll_arrows import ScrollablePanel

_BAR_WIDTH = 12
_FILL = "▪"
_EMPTY = "·"


class BudgetPanel(ScrollablePanel):
    """Shows how many unique months each category exceeded its budget."""

    def __init__(self, df, categories, **kwargs):
        kwargs.pop("month", None)
        super().__init__(**kwargs)
        self._df = df
        self._categories = categories
        self.border_title = "Months Over Budget"

    def compose(self) -> ComposeResult:
        self._filters = []
        items = analytics.months_over_budget(self._df, self._categories)

        if not items:
            self._filters.append("")
            yield Static(" No budgeted categories", classes="bar-row")
            return

        # Find max total months for bar scaling
        max_total = max(i["total_months"] for i in items) or 1

        for item in items:
            over = item["months_over"]
            total = item["total_months"]

            if total == 0:
                continue

            # Bar shows proportion of months that were over budget
            filled = max(0, int((over / max_total) * _BAR_WIDTH)) if over > 0 else 0
            empty = _BAR_WIDTH - filled

            if over == 0:
                bar_color = "#555555"
            elif over <= 2:
                bar_color = "#E8871E"
            else:
                bar_color = "#D9534F"

            avg = item["avg_overspend"]

            line = Text()
            line.append(f" {item['category']:15s}", style="#BBBBBB")
            line.append(_FILL * filled, style=bar_color)
            line.append(_EMPTY * empty, style="#2A2A2A")
            line.append(f" {over:>2d}/{total:<2d} mo", style=bar_color if over > 0 else "#555555")
            if avg > 0:
                line.append(f"  ~{avg:>6,.0f} {CURRENCY}", style="#D9534F")
            else:
                line.append(f"       —   ", style="#3A3A3A")

            self._filters.append(f"cat:{item['category']} <0")
            yield Static(line, classes="bar-row")

    def refresh_data(self, df, **kwargs):
        self._df = df
        self.remove_children()
        for w in self.compose():
            self.mount(w)
