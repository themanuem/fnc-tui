"""Alerts panel - budget warnings, outliers, duplicates."""

from rich.text import Text
from textual import work
from textual.app import ComposeResult
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
    """Compact alerts panel showing budget warnings, outliers, and duplicates."""

    def __init__(self, store, **kwargs):
        super().__init__(**kwargs)
        self._store = store
        self._df = None
        self.border_title = "Alerts"

    def compose(self) -> ComposeResult:
        self._filters = []
        yield Static("Loading...", id="alerts-content", classes="bar-row")

    def on_mount(self):
        super().on_mount()
        self._load_alerts()

    @work(thread=True, exclusive=True)
    def _load_alerts(self):
        from finance_tui.ai.insights import get_all_insights

        df = self._df if self._df is not None else self._store.df
        insights = get_all_insights(df, self._store.categories)

        def _render():
            # Guard: placeholder may have been removed by a concurrent refresh
            try:
                content = self.query_one("#alerts-content", Static)
            except Exception:
                return

            if not insights:
                self._filters = [""]
                line = Text()
                line.append(" No alerts ", style="#555555")
                line.append("— finances look good", style="#3A3A3A")
                content.update(line)
                return

            # Remove placeholder, mount individual alert rows
            content.remove()
            self._filters = []
            for item in insights[:15]:
                icon = _ICONS.get(item["type"], "·")
                color = _COLORS.get(item["type"], "#777777")

                line = Text()
                line.append(f" {icon} ", style=color)
                line.append(item["message"], style="#BBBBBB")

                self.mount(Static(line, classes="bar-row"))

                # Build drill-down filter based on alert type
                if item["type"] in ("budget_over", "budget_warning"):
                    cat = item.get("category", "")
                    self._filters.append(f"cat:{cat} <0" if cat else "")
                else:
                    desc = item.get("description", item.get("message", ""))
                    self._filters.append(desc[:40] if desc else "")

        self.app.call_from_thread(_render)

    def refresh_data(self, df_or_store=None):
        if hasattr(df_or_store, "df"):
            self._store = df_or_store
            self._df = None
        else:
            self._df = df_or_store
        self.remove_children()
        for w in self.compose():
            self.mount(w)
        self._load_alerts()
