"""Transactions screen - full transaction DataTable."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

from finance_tui.config import CURRENCY
from finance_tui.widgets.transaction_table import TransactionTable


class TransactionsPane(Container):
    """Transactions tab: DataTable + status bar."""

    def __init__(self, store, **kwargs):
        super().__init__(**kwargs)
        self.store = store

    def compose(self) -> ComposeResult:
        yield TransactionTable(id="txn-table")
        count = len(self.store.df) if self.store else 0
        yield Static(self._status_text(count), id="txn-status")

    def on_mount(self):
        if self.store:
            self._load_from_store()

    def _load_from_store(self):
        table = self.query_one("#txn-table", TransactionTable)
        table.set_enums(
            categories=list(self.store.categories.keys()),
            accounts=list(self.store.accounts.keys()),
        )
        table.load_data(self.store.df)

    def _status_text(self, count: int) -> str:
        if not self.store:
            return ""
        total = len(self.store.df)
        if count == total:
            return f"{count:,} transactions | Balance: {self.store.global_balance:,.2f} {CURRENCY}"
        return f"{count:,} / {total:,} transactions (filtered)"
