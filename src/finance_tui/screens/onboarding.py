"""First-run onboarding screen to configure the finance data directory."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static


class OnboardingScreen(Screen[Path]):
    """Asks the user to point at their finance data directory."""

    def compose(self) -> ComposeResult:
        with Vertical(id="onboarding-container"):
            yield Label("Welcome to Finance TUI", id="onboarding-title")
            yield Static(
                "Point to a directory containing your finance data.\n"
                "It should have [bold]Transactions/[/], [bold]Categories/[/], "
                "and [bold]Accounts/[/] subdirectories.\n\n"
                "If starting fresh, enter a new path and the folders will be created for you."
            )
            yield Label("Finance directory:")
            with Horizontal(id="onboarding-path-row"):
                yield Input(
                    placeholder="~/Documents/finance",
                    id="onboarding-path",
                )
                yield Button("Browse", variant="default", id="onboarding-browse")
            yield Static("", id="onboarding-error")
            yield Button("Continue", variant="primary", id="onboarding-continue")

    def on_mount(self):
        self.query_one("#onboarding-path", Input).focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "onboarding-browse":
            self._open_dir_browser()
        elif event.button.id == "onboarding-continue":
            self._validate_and_continue()

    def on_input_submitted(self, event: Input.Submitted):
        self._validate_and_continue()

    def _open_dir_browser(self):
        from finance_tui.screens.file_browser import DirBrowserDialog

        current = self.query_one("#onboarding-path", Input).value.strip()
        start = Path(current).expanduser() if current and Path(current).expanduser().is_dir() else Path.home()

        def on_select(result: str | None):
            if result:
                self.query_one("#onboarding-path", Input).value = result

        self.app.push_screen(DirBrowserDialog(start_path=start), on_select)

    def _validate_and_continue(self):
        raw = self.query_one("#onboarding-path", Input).value.strip()
        if not raw:
            self._show_error("Please enter a path.")
            return

        path = Path(raw).expanduser().resolve()

        if path.exists() and not path.is_dir():
            self._show_error("Path exists but is not a directory.")
            return

        if not path.exists():
            try:
                for sub in ("Transactions", "Categories", "Accounts"):
                    (path / sub).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self._show_error(f"Could not create directory: {e}")
                return
        else:
            missing = [s for s in ("Transactions", "Categories", "Accounts") if not (path / s).exists()]
            if missing:
                try:
                    for sub in missing:
                        (path / sub).mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    self._show_error(f"Could not create subdirectories: {e}")
                    return

        from finance_tui.config import save_finance_dir
        save_finance_dir(path)
        self.dismiss(path)

    def _show_error(self, msg: str):
        self.query_one("#onboarding-error", Static).update(f"[red]{msg}[/]")
