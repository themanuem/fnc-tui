"""Base class for overview panels using DataTable for native scrolling."""

from rich.text import Text
from textual.widgets import DataTable

from finance_tui.widgets.scroll_arrows import PanelDrillDown


class PanelTable(DataTable):
    """DataTable-based panel with single-column rows and drill-down on Enter."""

    can_focus = True

    def __init__(self, **kwargs):
        super().__init__(
            show_header=False,
            header_height=0,
            cursor_type="row",
            cell_padding=0,
            **kwargs,
        )
        self._filters: list[str] = []
        self._show_hover_cursor = False
        self.show_cursor = False

    def on_focus(self) -> None:
        self.show_cursor = True

    def on_blur(self) -> None:
        self.show_cursor = False

    def _load_rows(self, rows: list[tuple[Text, str]]) -> None:
        """Clear and reload rows. Each entry is (rich_text, filter_query)."""
        self.clear(columns=True)
        self._filters.clear()
        self.add_column("", key="content")
        for text, filt in rows:
            self.add_row(text)
            self._filters.append(filt)

    def key_enter(self) -> None:
        """Post drill-down message for the selected row."""
        self._drill_down(exclude=False)

    def key_x(self) -> None:
        """Post exclusion drill-down message for the selected row."""
        self._drill_down(exclude=True)

    def _drill_down(self, exclude: bool) -> None:
        idx = self.cursor_row
        if 0 <= idx < len(self._filters):
            query = self._filters[idx]
            if query:
                self.post_message(
                    PanelDrillDown(query, panel_id=self.id or "", exclude=exclude)
                )
