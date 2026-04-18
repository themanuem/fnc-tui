"""Alerts panel - budget warnings, outliers, duplicates with validation."""

from rich.text import Text
from textual import work
from textual.message import Message

from finance_tui.widgets.panel_table import PanelTable

_ICONS = {
    "outlier": "◆",
    "duplicate": "⊘",
}

_COLORS = {
    "outlier": "#E8871E",
    "duplicate": "#E8871E",
}


class AlertsPanel(PanelTable):
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

    def on_mount(self) -> None:
        if not self._store:
            return
        self._show_loading()
        self._load_alerts()

    def _show_loading(self) -> None:
        line = Text("Loading...", style="#555555")
        self._load_rows([(line, "")])

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
            self._items = []
            self._filters = []
            self._multi_selected.clear()

            if not insights:
                line = Text()
                line.append(" No alerts ", style="#555555")
                line.append("— finances look good", style="#3A3A3A")
                self._load_rows([(line, "")])
                return

            rows: list[tuple[Text, str]] = []
            for item in insights[:15]:
                self._items.append(item)
                text = self._render_alert_text(item)

                desc = item.get("description", item.get("message", ""))
                filt = desc[:40] if desc else ""

                rows.append((text, filt))

            self._load_rows(rows)

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

    def key_space(self) -> None:
        """Toggle multi-selection on the current row."""
        idx = self.cursor_row
        if idx < 0 or idx >= len(self._items):
            return
        if idx in self._multi_selected:
            self._multi_selected.discard(idx)
        else:
            self._multi_selected.add(idx)
        # Re-render the row in place
        selected = idx in self._multi_selected
        text = self._render_alert_text(self._items[idx], selected)
        self.update_cell_at((idx, 0), text)

    # ── validate ─────────────────────────────────────────────

    def key_v(self) -> None:
        """Validate selected alerts (or current row if none selected)."""
        if self._multi_selected:
            indices = set(self._multi_selected)
        elif self.cursor_row >= 0:
            indices = {self.cursor_row}
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

    def _remove_alerts(self, indices: set[int]) -> None:
        """Remove alerts at given indices from the panel."""
        # Get row keys before removing anything
        row_keys = list(self.rows.keys())
        for idx in sorted(indices, reverse=True):
            if idx < len(row_keys):
                self.remove_row(row_keys[idx])
            if idx < len(self._items):
                self._items.pop(idx)
            if idx < len(self._filters):
                self._filters.pop(idx)

        self._multi_selected.clear()

        if not self._items:
            line = Text()
            line.append(" No alerts ", style="#555555")
            line.append("— finances look good", style="#3A3A3A")
            self._load_rows([(line, "")])

    # ── refresh ──────────────────────────────────────────────

    def refresh_data(self, df_or_store=None):
        if hasattr(df_or_store, "df"):
            self._store = df_or_store
            self._df = None
        else:
            self._df = df_or_store
        self._multi_selected.clear()
        self._show_loading()
        self._load_alerts()
