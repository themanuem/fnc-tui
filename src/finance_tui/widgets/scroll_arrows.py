"""Mixin that replaces scrollbars with ▲/▼ arrow indicators."""

from textual.containers import VerticalScroll
from textual.message import Message


class PanelDrillDown(Message):
    """Posted when Enter is pressed on a panel row."""

    def __init__(self, filter_query: str, panel_id: str = ""):
        super().__init__()
        self.filter_query = filter_query
        self.panel_id = panel_id


class ScrollArrowsMixin:
    """Mixin for scroll containers: hides scrollbar, shows ▲/▼ in border_subtitle."""

    def on_mount(self):
        if hasattr(super(), "on_mount"):
            super().on_mount()
        self.call_later(self._update_arrows)

    def on_resize(self):
        if hasattr(super(), "on_resize"):
            super().on_resize()
        self._update_arrows()

    def watch_scroll_y(self, value: float):
        self._update_arrows()

    def _update_arrows(self):
        can_up = self.scroll_y > 0
        can_down = self.scroll_y < self.max_scroll_y

        if can_up and can_down:
            self.border_subtitle = "▲▼"
        elif can_up:
            self.border_subtitle = "▲"
        elif can_down:
            self.border_subtitle = "▼"
        else:
            self.border_subtitle = ""


class ScrollablePanel(ScrollArrowsMixin, VerticalScroll):
    """VerticalScroll container with arrow overflow indicators and row selection."""

    can_focus = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selected_index: int = -1
        self._filters: list[str] = []

    def _get_row_widgets(self):
        """Return the list of row widgets (Static children with class bar-row)."""
        return list(self.query(".bar-row"))

    def _update_selection(self):
        """Highlight the selected row and clear others."""
        rows = self._get_row_widgets()
        for i, row in enumerate(rows):
            if i == self._selected_index:
                row.add_class("panel-row-selected")
            else:
                row.remove_class("panel-row-selected")
        # Scroll selected row into view
        if 0 <= self._selected_index < len(rows):
            rows[self._selected_index].scroll_visible()

    def key_up(self):
        rows = self._get_row_widgets()
        if not rows:
            return
        if self._selected_index <= 0:
            self._selected_index = 0
        else:
            self._selected_index -= 1
        self._update_selection()

    def key_down(self):
        rows = self._get_row_widgets()
        if not rows:
            return
        if self._selected_index < len(rows) - 1:
            self._selected_index += 1
        self._update_selection()

    def key_enter(self):
        if 0 <= self._selected_index < len(self._filters):
            query = self._filters[self._selected_index]
            if query:
                self.post_message(PanelDrillDown(query, panel_id=self.id or ""))

    def on_focus(self):
        if hasattr(super(), "on_focus"):
            super().on_focus()
        rows = self._get_row_widgets()
        if rows and self._selected_index < 0:
            self._selected_index = 0
            self._update_selection()

    def on_blur(self):
        if hasattr(super(), "on_blur"):
            super().on_blur()
        rows = self._get_row_widgets()
        for row in rows:
            row.remove_class("panel-row-selected")
        self._selected_index = -1
