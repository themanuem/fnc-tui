"""Account panel - btop disk-style compact bars."""

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Static

from finance_tui import analytics
from finance_tui.config import CURRENCY
from finance_tui.widgets.scroll_arrows import ScrollablePanel

_BAR_WIDTH = 16
_FILL = "▪"
_EMPTY = "·"


class AccountPanel(ScrollablePanel):
    """Compact account breakdown with inline progress bars."""

    def __init__(self, df, **kwargs):
        super().__init__(**kwargs)
        self._df = df
        self.border_title = "Accounts"

    def compose(self) -> ComposeResult:
        self._filters = []
        balances = analytics.balance_by_account(self._df)
        counts = analytics.count_by_account(self._df)
        total = sum(abs(v) for v in balances.values()) or 1

        for account in sorted(balances.keys()):
            bal = balances[account]
            cnt = counts.get(account, 0)
            pct = abs(bal) / total

            filled = max(1, int(pct * _BAR_WIDTH))
            empty = _BAR_WIDTH - filled

            line = Text()
            line.append(f" {account:14s} ", style="#BBBBBB")
            line.append(_FILL * filled, style="#E8871E")
            line.append(_EMPTY * empty, style="#2A2A2A")
            line.append(f" {bal:>10,.2f} {CURRENCY} ", style="#E0E0E0")
            line.append(f"({cnt})", style="#555555")

            self._filters.append(f"acc:{account}")
            yield Static(line, classes="bar-row")

    def refresh_data(self, df):
        self._df = df
        self.remove_children()
        for w in self.compose():
            self.mount(w)
