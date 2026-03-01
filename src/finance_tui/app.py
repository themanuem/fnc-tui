"""Main Textual application."""

from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Static, TabbedContent, TabPane

from finance_tui.commands import FinanceCommandProvider
from finance_tui.config import FINANCE_DIR
from finance_tui.widgets.command_palette import FinanceCommandPalette
from finance_tui.screens.dialogs import CategoryChangeDialog
from finance_tui.screens.overview import OverviewPane
from finance_tui.screens.transactions import TransactionsPane
from finance_tui.store import FinanceStore
from finance_tui.watcher import DataChanged, FileWatcher
from finance_tui.widgets.period_selector import PeriodSelector
from finance_tui.widgets.alerts_panel import AlertsPanel
from finance_tui.widgets.scroll_arrows import PanelDrillDown
from finance_tui.widgets.search_bar import build_filter_mask
from finance_tui.widgets.transaction_table import TransactionTable
from finance_tui.writer import (
    change_category,
    prepend_transaction,
    serialize_transaction,
    toggle_validated,
    update_transaction_in_file,
)


# Half-block pixel logo "fnc" — 4 pixel rows rendered in 2 terminal rows
_LOGO_PX = [
    "011011100011",
    "100010010100",
    "111010010100",
    "100010010011",
]
_HALF = {(0, 0): " ", (1, 0): "▀", (0, 1): "▄", (1, 1): "█"}
_CLR = "#E8871E"
LOGO = "\n".join(
    "".join(
        f"[{_CLR}]{_HALF[(int(top), int(bot))]}[/]"
        if (top, bot) != ("0", "0")
        else " "
        for top, bot in zip(_LOGO_PX[r], _LOGO_PX[r + 1])
    )
    for r in range(0, 4, 2)
)


class FinanceTUI(App):
    """Personal finance terminal UI."""

    TITLE = "Finance TUI"
    CSS_PATH = Path("styles/app.tcss")
    COMMANDS = {FinanceCommandProvider}
    COMMAND_PALETTE_BINDING = "ctrl+k"

    BINDINGS = [
        ("o", "switch_tab('overview')", "Overview"),
        ("t", "switch_tab('transactions')", "Txns"),
        Binding("1", "focus_panel('panel-1')", "Panel 1", show=False),
        Binding("2", "focus_panel('panel-2')", "Panel 2", show=False),
        Binding("3", "focus_panel('panel-3')", "Panel 3", show=False),
        Binding("4", "focus_panel('panel-4')", "Panel 4", show=False),
        Binding("5", "focus_panel('panel-5')", "Panel 5", show=False),
        Binding("6", "focus_panel('panel-6')", "Panel 6", show=False),
        Binding("7", "focus_panel('panel-7')", "Panel 7", show=False),
        ("left_square_bracket", "period_prev", "◀"),
        ("right_square_bracket", "period_next", "▶"),
        ("p", "period_prefix", "Period"),
        Binding("v", "validate_transaction", "Validate", show=False),
        Binding("c", "change_category_dialog", "Cat", show=False),
        ("r", "reload_data", "Reload"),
        ("escape", "clear_filters", "Clear"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.animation_level = "none"
        self.store = FinanceStore()
        self._watcher: FileWatcher | None = None
        self._period_start = None
        self._period_end = None
        self._period_label = ""
        self._drilldown_filters: dict[str, str] = {}  # panel_num → query
        self._search_query: str = ""
        self._period_pending = False

    def compose(self):
        with Horizontal(id="top-bar"):
            yield Static(LOGO, id="logo")
            yield Static("", id="active-filters")
            yield PeriodSelector(id="period")
        with TabbedContent(id="main-tabs"):
            with TabPane("Overview", id="overview"):
                yield OverviewPane(self.store)
            with TabPane("Transactions", id="transactions"):
                yield TransactionsPane(self.store)
        yield Footer()

    def on_mount(self):
        self._watcher = FileWatcher(FINANCE_DIR, self)
        self._watcher.start()

    def on_unmount(self):
        if self._watcher:
            self._watcher.stop()

    # --- Command palette ---
    def action_command_palette(self) -> None:
        if not FinanceCommandPalette.is_open(self):
            self.push_screen(FinanceCommandPalette(id="--command-palette"))

    def _palette_insert_prefix(self, prefix: str) -> None:
        """Insert a prefix into the open command palette input (drill-down)."""
        from textual.command import CommandInput
        try:
            palette = self.query_one(FinanceCommandPalette)
            input_widget = palette.query_one(CommandInput)
            input_widget.value = prefix
            input_widget.action_end()
        except Exception:
            pass

    # --- Tab switching ---
    def action_switch_tab(self, tab_id: str):
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = tab_id
        if tab_id == "transactions":
            try:
                self.query_one("#txn-table", TransactionTable).focus()
            except Exception:
                pass

    # --- Panel focus ---
    def action_focus_panel(self, panel_id: str):
        """Focus a numbered panel in the overview tab."""
        self.action_switch_tab("overview")
        try:
            panel = self.query_one(f"#{panel_id}")
            panel.focus()
        except Exception:
            pass

    @on(PanelDrillDown)
    def _on_panel_drill_down(self, event: PanelDrillDown):
        """Add/toggle a drill-down filter from a panel row."""
        panel_num = event.panel_id.replace("panel-", "") if event.panel_id else "?"
        existing = self._drilldown_filters.get(panel_num)
        if existing == event.filter_query:
            del self._drilldown_filters[panel_num]
        else:
            self._drilldown_filters[panel_num] = event.filter_query
        self._update_filter_bar()
        self._refresh_all()

    def action_clear_filters(self):
        """Clear all active filters (drilldown + search)."""
        if self._drilldown_filters or self._search_query:
            self._drilldown_filters.clear()
            self._search_query = ""
            self._update_filter_bar()
            self._refresh_all()

    def _update_filter_bar(self):
        """Render active filter chips into the top bar."""
        try:
            widget = self.query_one("#active-filters", Static)
        except Exception:
            return
        if not self._drilldown_filters and not self._search_query:
            widget.update("")
            return
        line = Text()
        for i, (num, query) in enumerate(self._drilldown_filters.items()):
            if i > 0:
                line.append("  ", style="#333333")
            line.append(f"{num}", style="#E8871E bold")
            line.append("·", style="#555555")
            line.append(query, style="#BBBBBB")
        if self._search_query:
            if self._drilldown_filters:
                line.append("  ", style="#333333")
            line.append("s", style="#E8871E bold")
            line.append("·", style="#555555")
            line.append(self._search_query, style="#BBBBBB")
        widget.update(line)

    # --- Search (via command palette) ---
    def apply_search_filter(self, query: str):
        """Apply a transaction search/filter from the command palette."""
        self._search_query = query
        self.action_switch_tab("transactions")
        self._update_filter_bar()
        self._refresh_all()

    # --- Period navigation ---
    def action_period_prev(self):
        self.query_one("#period", PeriodSelector).action_prev()

    def action_period_next(self):
        self.query_one("#period", PeriodSelector).action_next()

    def action_period_prefix(self):
        self._period_pending = True
        self.notify("Period: [a]ll  [y]ear  [m]onth", timeout=2)

    def on_key(self, event) -> None:
        if not self._period_pending:
            return
        self._period_pending = False
        key = event.key
        if key == "a":
            self.query_one("#period", PeriodSelector).action_set_all()
            event.stop()
            event.prevent_default()
        elif key == "y":
            self.query_one("#period", PeriodSelector).action_set_year()
            event.stop()
            event.prevent_default()
        elif key == "m":
            self.query_one("#period", PeriodSelector).action_set_month()
            event.stop()
            event.prevent_default()

    def action_set_period_all(self):
        self.query_one("#period", PeriodSelector).action_set_all()

    def action_set_period_year(self):
        self.query_one("#period", PeriodSelector).action_set_year()

    def action_set_period_month(self):
        self.query_one("#period", PeriodSelector).action_set_month()

    @on(PeriodSelector.PeriodChanged)
    def _on_period_changed(self, event: PeriodSelector.PeriodChanged):
        self._period_start = event.start
        self._period_end = event.end
        self._period_label = event.label
        self._refresh_all()

    def _get_filtered_df(self):
        import pandas as pd
        df = self.store.df
        if self._period_start and self._period_end:
            start = pd.Timestamp(self._period_start)
            end = pd.Timestamp(self._period_end)
            df = df[(df["date"] >= start) & (df["date"] < end)]
        for query in self._drilldown_filters.values():
            mask = build_filter_mask(df, query)
            df = df[mask]
        if self._search_query:
            mask = build_filter_mask(df, self._search_query)
            df = df[mask]
        return df

    def _refresh_all(self):
        """Refresh both overview and transactions with the current period filter."""
        filtered = self._get_filtered_df()
        self._refresh_transactions_view(filtered)
        self._refresh_overview(filtered)

    def _refresh_transactions_view(self, df=None):
        try:
            if df is None:
                df = self._get_filtered_df()
            pane = self.query_one("TransactionsPane", TransactionsPane)
            table = pane.query_one("#txn-table", TransactionTable)
            table.set_enums(
                categories=list(self.store.categories.keys()),
                accounts=list(self.store.accounts.keys()),
            )
            table.load_data(df)
            status = pane.query_one("#txn-status", Static)
            status.update(pane._status_text(len(df)))
        except Exception:
            pass

    def _refresh_overview(self, df=None):
        try:
            if df is None:
                df = self._get_filtered_df()
            overview = self.query_one("OverviewPane", OverviewPane)
            label = getattr(self, "_period_label", "")
            overview.refresh_data(df, period_label=label)
        except Exception:
            pass

    # --- Data reload ---
    @on(DataChanged)
    def _on_data_changed(self, event: DataChanged):
        self.store.load()
        self._refresh_all()
        self.notify("Data reloaded", timeout=2)

    def action_reload_data(self):
        self.store.load()
        self._refresh_all()
        self.notify("Data reloaded", timeout=2)

    # --- Transaction editing ---
    def action_validate_transaction(self):
        try:
            table = self.query_one("#txn-table", TransactionTable)
        except Exception:
            return

        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if not row_key:
            return

        txn_id = int(row_key.value)
        row = self.store.df[self.store.df["id"] == txn_id]
        if row.empty:
            return

        row = row.iloc[0]
        new_line = toggle_validated(row["raw_line"])

        if self._watcher:
            file_path = self.store.transactions_dir / row["source_file"]
            self._watcher.ignore_next_change(str(file_path))

        update_transaction_in_file(
            row["source_file"], row["line_number"], new_line
        )
        self.store.load()
        self._refresh_all()
        self.notify("Transaction validated", timeout=2)

    def action_change_category_dialog(self):
        try:
            table = self.query_one("#txn-table", TransactionTable)
        except Exception:
            return

        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if not row_key:
            return

        txn_id = int(row_key.value)
        row = self.store.df[self.store.df["id"] == txn_id]
        if row.empty:
            return

        row_data = row.iloc[0]
        categories = list(self.store.categories.keys())

        def on_dismiss(new_cat: str | None) -> None:
            if not new_cat or new_cat == row_data["category"]:
                return
            new_line = change_category(row_data["raw_line"], new_cat)

            if self._watcher:
                file_path = self.store.transactions_dir / row_data["source_file"]
                self._watcher.ignore_next_change(str(file_path))

            update_transaction_in_file(
                row_data["source_file"], row_data["line_number"], new_line
            )
            self.store.load()
            self._refresh_all()
            self.notify(f"Category changed to {new_cat}", timeout=2)

        self.push_screen(
            CategoryChangeDialog(categories, row_data["category"]),
            callback=on_dismiss,
        )

    # --- Inline editing ---
    @on(TransactionTable.TransactionEdited)
    def _on_transaction_edited(self, event: TransactionTable.TransactionEdited):
        row = self.store.df[self.store.df["id"] == event.txn_id]
        if row.empty:
            return
        row_data = row.iloc[0]

        new_line = serialize_transaction(
            validated=row_data["validated"],
            amount=event.changes.get("amount", row_data["amount"]),
            category=event.changes.get("category", row_data["category"]),
            description=event.changes.get("description", row_data["description"]),
            date_str=event.changes.get("date", row_data["date"].strftime("%Y-%m-%d")),
            account=event.changes.get("account", row_data["account"]),
            txn_id=event.txn_id,
        )

        if self._watcher:
            file_path = self.store.transactions_dir / row_data["source_file"]
            self._watcher.ignore_next_change(str(file_path))

        update_transaction_in_file(
            row_data["source_file"], row_data["line_number"], new_line
        )
        self.store.load()
        self._refresh_all()
        try:
            table = self.query_one("#txn-table", TransactionTable)
            table.focus_transaction(event.txn_id)
        except Exception:
            pass

    @on(TransactionTable.TransactionCreated)
    def _on_transaction_created(self, event: TransactionTable.TransactionCreated):
        values = event.values
        new_line = serialize_transaction(
            validated=False,
            amount=values["amount"],
            category=values["category"],
            description=values["description"],
            date_str=values["date"],
            account=values["account"],
            txn_id=values["id"],
        )

        year = int(values["date"][:4])
        file_path = prepend_transaction(new_line, year)

        if self._watcher:
            self._watcher.ignore_next_change(str(file_path))

        self.store.load()
        self._refresh_all()
        self.notify(f"Transaction #{values['id']} created", timeout=2)

    @on(TransactionTable.NewTransactionRequested)
    def _on_new_txn_requested(self, event: TransactionTable.NewTransactionRequested):
        self._drilldown_filters.clear()
        self._search_query = ""
        self._update_filter_bar()
        filtered = self._get_filtered_df()
        self._refresh_overview(filtered)

        max_id = int(self.store.df["id"].max()) if not self.store.df.empty else 0
        try:
            pane = self.query_one("TransactionsPane", TransactionsPane)
            table = pane.query_one("#txn-table", TransactionTable)
            table.set_enums(
                categories=list(self.store.categories.keys()),
                accounts=list(self.store.accounts.keys()),
            )
            status = pane.query_one("#txn-status", Static)
            status.update(pane._status_text(len(filtered)))
            table.start_new_transaction(max_id + 1, filtered)
        except Exception:
            pass

    # --- Alert validation ---
    @on(AlertsPanel.ValidateAlerts)
    def _on_validate_alerts(self, event: AlertsPanel.ValidateAlerts):
        for txn_id in event.txn_ids:
            row = self.store.df[self.store.df["id"] == txn_id]
            if row.empty:
                continue
            row_data = row.iloc[0]
            new_line = toggle_validated(row_data["raw_line"])

            if self._watcher:
                file_path = self.store.transactions_dir / row_data["source_file"]
                self._watcher.ignore_next_change(str(file_path))

            update_transaction_in_file(
                row_data["source_file"], row_data["line_number"], new_line
            )

        self.store.load()
        self._refresh_transactions_view()
        count = len(event.txn_ids)
        self.notify(f"Validated {count} transaction{'s' if count > 1 else ''}", timeout=2)

    # --- Command palette custom actions ---
    def action_custom(self, action_str: str):
        if action_str.startswith("switch_tab"):
            tab_id = action_str.split("'")[1]
            self.action_switch_tab(tab_id)
        elif action_str.startswith("apply_search("):
            query = action_str[len("apply_search("):-1]
            self.apply_search_filter(query)
        elif action_str == "clear_filter":
            self.action_clear_filters()
        elif action_str == "reload_data":
            self.action_reload_data()
        elif action_str == "quit":
            self.action_quit()
        elif action_str == "set_period_all":
            self.action_set_period_all()
        elif action_str == "set_period_year":
            self.action_set_period_year()
        elif action_str == "set_period_month":
            self.action_set_period_month()
