"""Modal dialog screens for transaction editing."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select


class CategoryChangeDialog(ModalScreen[str | None]):
    """Modal dialog to change a transaction's category."""

    def __init__(self, categories: list[str], current: str, **kwargs):
        super().__init__(**kwargs)
        self._categories = categories
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-container"):
            yield Label(f"Current category: [b]{self._current}[/b]")
            yield Select(
                [(c, c) for c in sorted(self._categories)],
                value=self._current,
                id="cat-select",
            )
            with Vertical(id="dialog-buttons"):
                yield Button("Confirm", variant="primary", id="confirm")
                yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirm":
            select = self.query_one("#cat-select", Select)
            self.dismiss(str(select.value) if select.value != Select.BLANK else None)
        else:
            self.dismiss(None)
