"""Compact KPI card with btop-style border title."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static


class KpiCard(Vertical):
    """Single-line KPI inside a bordered panel with title in the border."""

    def __init__(
        self,
        title: str,
        value: str,
        sentiment: str = "neutral",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.border_title = title
        self._value = value
        self._sentiment = sentiment

    def compose(self) -> ComposeResult:
        yield Static(self._value, classes=f"kpi-value kpi-{self._sentiment}")

    def update_value(self, value: str, sentiment: str = "neutral"):
        w = self.query_one(".kpi-value", Static)
        w.update(value)
        w.set_classes(f"kpi-value kpi-{sentiment}")
