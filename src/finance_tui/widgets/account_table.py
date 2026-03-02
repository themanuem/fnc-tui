"""Account panel - btop disk-style compact bars."""

from rich.text import Text

from finance_tui import analytics
from finance_tui.config import CURRENCY
from finance_tui.widgets.panel_table import PanelTable

_BAR_WIDTH = 16
_FILL = "▪"
_EMPTY = "·"


class AccountPanel(PanelTable):
    """Compact account breakdown with inline progress bars."""

    def __init__(self, df, **kwargs):
        super().__init__(**kwargs)
        self._df = df
        self.border_title = "Accounts"

    def on_mount(self) -> None:
        self._initial_row_count = 0
        self._build_rows()

    def _build_rows(self) -> None:
        balances = analytics.balance_by_account(self._df)
        counts = analytics.count_by_account(self._df)
        total = sum(abs(v) for v in balances.values()) or 1

        rows: list[tuple[Text, str]] = []
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

            rows.append((line, f"acc:{account}"))

        if not self._initial_row_count:
            self._initial_row_count = len(rows)

        # Pad to initial row count so height stays stable
        while len(rows) < self._initial_row_count:
            rows.append((Text(""), ""))

        self._load_rows(rows)

    def refresh_data(self, df):
        self._df = df
        self._build_rows()
