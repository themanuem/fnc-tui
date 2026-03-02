"""Interactive filter bar with navigable chips."""

from __future__ import annotations

from rich.text import Text
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static


class FilterBar(Static):
    """Displays filter chips and allows navigation / editing when focused."""

    can_focus = True

    class RemoveFilter(Message):
        """Posted when a filter chip is deleted."""

        def __init__(self, key: str, filter_type: str) -> None:
            super().__init__()
            self.key = key
            self.filter_type = filter_type  # "drilldown" or "search"

    class ToggleExclude(Message):
        """Posted when x is pressed on a drilldown chip."""

        def __init__(self, key: str) -> None:
            super().__init__()
            self.key = key

    class Dismiss(Message):
        """Posted when esc is pressed — return focus to previous widget."""

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._entries: list[dict] = []  # {key, query, exclude, type}
        self._cursor: int = 0
        self.previous_focus: Widget | None = None

    # ── public API ────────────────────────────────────────

    def set_filters(self, entries: list[dict]) -> None:
        """Update the list of filter entries and re-render."""
        self._entries = list(entries)
        if self._cursor >= len(self._entries):
            self._cursor = max(0, len(self._entries) - 1)
        self._refresh_chips()

    # ── rendering ─────────────────────────────────────────

    def _refresh_chips(self, focused: bool | None = None) -> None:
        if not self._entries:
            self.update("")
            return

        if focused is None:
            focused = self.has_focus
        line = Text()
        for i, entry in enumerate(self._entries):
            if i > 0:
                line.append("  ", style="#333333")

            selected = focused and i == self._cursor
            line.append("[" if selected else " ", style="#555555")

            line.append(entry["key"], style="#E8871E bold")
            line.append("·", style="#555555")
            if entry.get("exclude"):
                line.append("!", style="#E85555 bold")
            line.append(entry["query"], style="#BBBBBB")

            line.append("]" if selected else " ", style="#555555")

        self.update(line)

    # ── focus ─────────────────────────────────────────────

    def on_focus(self) -> None:
        self._cursor = 0
        self._refresh_chips(focused=True)

    def on_blur(self) -> None:
        self._refresh_chips(focused=False)

    # ── keys ──────────────────────────────────────────────

    def key_left(self) -> None:
        if self._entries:
            self._cursor = (self._cursor - 1) % len(self._entries)
            self._refresh_chips()

    def key_right(self) -> None:
        if self._entries:
            self._cursor = (self._cursor + 1) % len(self._entries)
            self._refresh_chips()

    def key_delete(self) -> None:
        self._remove_current()

    def key_backspace(self) -> None:
        self._remove_current()

    def key_x(self) -> None:
        if not self._entries:
            return
        entry = self._entries[self._cursor]
        if entry["type"] == "drilldown":
            self.post_message(self.ToggleExclude(entry["key"]))

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            event.prevent_default()
            self.post_message(self.Dismiss())

    def _remove_current(self) -> None:
        if not self._entries:
            return
        entry = self._entries[self._cursor]
        self.post_message(self.RemoveFilter(entry["key"], entry["type"]))
