"""Alerts panel - budget warnings, outliers, duplicates with validation."""

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Static

from finance_tui.widgets.scroll_arrows import ScrollablePanel

_ICONS = {
    "budget_over": "●",
    "budget_warning": "◐",
    "outlier": "△",
    "duplicate": "◇",
}

_COLORS = {
    "budget_over": "#D9534F",
    "budget_warning": "#E8871E",
    "outlier": "#E8871E",
    "duplicate": "#777777",
}


class AlertsPanel(ScrollablePanel):
    """Alerts panel with multi-select (Space) and validate (v)."""

    class ValidateAlerts(Message):
        """Posted when user validates selected alerts."""

        def __init__(self, txn_ids: list[int]) -> None:
            super().__init__()
            self.txn_ids = txn_ids

    class AlertIconsReady(Message):
        """Posted after alerts load, carrying txn_id → alert_type map."""

        def __init__(self, alert_map: dict[int, str]) -> None:
            super().__init__()
            self.alert_map = alert_map

    def __init__(self, store, **kwargs):
        super().__init__(**kwargs)
        self._store = store
        self._df = None
        self._items: list[dict] = []
        self._multi_selected: set[int] = set()
        self.border_title = "Alerts"

    def compose(self) -> ComposeResult:
        self._filters = []
        yield Static("Loading...", id="alerts-content", classes="bar-row")

    def on_mount(self):
        super().on_mount()
        self._load_alerts()

    # ── rendering ────────────────────────────────────────────

    def _render_alert_text(self, item: dict, selected: bool = False) -> Text:
        """Build the Rich Text for an alert row."""
        icon = _ICONS.get(item["type"], "·")
        color = _COLORS.get(item["type"], "#777777")
        line = Text()
        if selected:
            line.append(" ◆ ", style="#5CB85C")
        else:
            line.append(f" {icon} ", style=color)
        line.append(item["message"], style="#BBBBBB")
        return line

    @work(thread=True, exclusive=True)
    def _load_alerts(self):
        from finance_tui.ai.insights import get_all_insights

        df = self._df if self._df is not None else self._store.df
        insights = get_all_insights(df, self._store.categories)

        def _render():
            try:
                content = self.query_one("#alerts-content", Static)
            except Exception:
                return

            if not insights:
                self._items = []
                self._filters = [""]
                self._multi_selected.clear()
                line = Text()
                line.append(" No alerts ", style="#555555")
                line.append("— finances look good", style="#3A3A3A")
                content.update(line)
                return

            content.remove()
            self._items = []
            self._filters = []
            self._multi_selected.clear()

            for item in insights[:15]:
                self._items.append(item)
                self.mount(Static(self._render_alert_text(item), classes="bar-row"))

                if item["type"] in ("budget_over", "budget_warning"):
                    cat = item.get("category", "")
                    self._filters.append(f"cat:{cat} <0" if cat else "")
                else:
                    desc = item.get("description", item.get("message", ""))
                    self._filters.append(desc[:40] if desc else "")

        # Build alert map: txn_id → alert_type
        alert_map: dict[int, str] = {}
        for item in insights:
            txn_id = item.get("id")
            if txn_id is not None:
                alert_map[txn_id] = item["type"]

        def _post_icons():
            self.post_message(self.AlertIconsReady(alert_map))

        self.app.call_from_thread(_render)
        self.app.call_from_thread(_post_icons)

    # ── multi-select ─────────────────────────────────────────

    def key_space(self):
        """Toggle multi-selection on the current row."""
        if self._selected_index < 0 or self._selected_index >= len(self._items):
            return
        idx = self._selected_index
        if idx in self._multi_selected:
            self._multi_selected.discard(idx)
        else:
            self._multi_selected.add(idx)
        self._update_row_visual(idx)

    def _update_row_visual(self, idx: int):
        """Re-render a single row to reflect its selection state."""
        rows = self._get_row_widgets()
        if idx < 0 or idx >= len(rows) or idx >= len(self._items):
            return
        selected = idx in self._multi_selected
        rows[idx].update(self._render_alert_text(self._items[idx], selected))

    # ── validate ─────────────────────────────────────────────

    def key_v(self):
        """Validate selected alerts (or current row if none selected)."""
        if self._multi_selected:
            indices = set(self._multi_selected)
        elif self._selected_index >= 0:
            indices = {self._selected_index}
        else:
            return

        txn_ids = []
        for idx in indices:
            if idx < len(self._items):
                item = self._items[idx]
                if "id" in item:
                    txn_ids.append(item["id"])

        if txn_ids:
            self.post_message(self.ValidateAlerts(txn_ids))

        self._remove_alerts(indices)

    def _remove_alerts(self, indices: set[int]):
        """Remove alerts at given indices from the panel."""
        rows = self._get_row_widgets()
        for idx in sorted(indices, reverse=True):
            if idx < len(rows):
                rows[idx].remove()
            if idx < len(self._items):
                self._items.pop(idx)
            if idx < len(self._filters):
                self._filters.pop(idx)

        self._multi_selected.clear()

        if self._selected_index >= len(self._items):
            self._selected_index = max(0, len(self._items) - 1)
        if not self._items:
            self._selected_index = -1
            self.mount(Static(
                Text(" No alerts ", style="#555555"),
                classes="bar-row",
            ))
        self._update_selection()

    # ── refresh ──────────────────────────────────────────────

    def refresh_data(self, df_or_store=None):
        if hasattr(df_or_store, "df"):
            self._store = df_or_store
            self._df = None
        else:
            self._df = df_or_store
        self._multi_selected.clear()
        self.remove_children()
        for w in self.compose():
            self.mount(w)
        self._load_alerts()
