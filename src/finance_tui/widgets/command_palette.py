"""Raycast-style command palette overlay."""

from rich.text import Text
from textual.command import (
    Command,
    CommandInput,
    CommandList,
    CommandPalette,
    DiscoveryHit,
)
from textual.widgets._option_list import OptionList

# DiscoveryHit display labels that trigger prefix drill-down instead of closing
_PREFIX_MAP = {
    "Search": "",
    "Category": "cat:",
    "Account": "acc:",
    "Period": "period:",
    "Tag": "tag:",
    "Link": "link:",
}


class FinanceCommandPalette(CommandPalette):
    """Command palette with prefix drill-down, footer hints, and themed framing."""

    def _on_mount(self, _) -> None:
        super()._on_mount(_)
        try:
            container = self.query_one("#--container")
            container.border_title = Text("Palette", style="#E8871E bold")
            container.border_subtitle = self._subtitle_text()
        except Exception:
            pass
        try:
            icon = self.query_one("SearchIcon")
            icon.display = False
        except Exception:
            pass

    def _is_prefix_hit(self, hit) -> str | None:
        """Return the prefix string if this hit is a drill-down entry, else None."""
        text = hit.text if hit.text else str(getattr(hit, "display", ""))
        return _PREFIX_MAP.get(text)

    def _select_command(self, event: OptionList.OptionSelected) -> None:
        """Override: intercept prefix drill-down items to stay open."""
        event.stop()
        assert isinstance(event.option, Command)
        hit = event.option.hit

        prefix = self._is_prefix_hit(hit)
        if prefix is not None:
            # Drill down: insert prefix into input, don't close
            input_widget = self.query_one(CommandInput)
            input_widget.value = prefix
            input_widget.action_end()
            return

        # Normal selection: delegate to parent behavior
        super()._select_command(event)

    def key_tab(self) -> None:
        """Tab inserts the highlighted option's prefix into the input."""
        try:
            command_list = self.query_one(CommandList)
            input_widget = self.query_one(CommandInput)
            idx = command_list.highlighted
            if idx is None:
                return
            option = command_list.get_option_at_index(idx)
            hit = option.hit
            prefix = self._is_prefix_hit(hit)
            if prefix is not None:
                input_widget.value = prefix
                input_widget.action_end()
        except Exception:
            pass

    @staticmethod
    def _subtitle_text() -> Text:
        t = Text()
        t.append("enter ", style="#E8871E")
        t.append("Select  ", style="#777777")
        t.append("tab ", style="#E8871E")
        t.append("Drill down  ", style="#777777")
        t.append("esc ", style="#E8871E")
        t.append("Close", style="#555555")
        return t
