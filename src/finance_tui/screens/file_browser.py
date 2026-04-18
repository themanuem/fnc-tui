"""File and directory browser modals."""

from pathlib import Path
from typing import Iterable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label, Static

ALLOWED_EXTENSIONS = {".csv", ".json", ".xlsx", ".md"}


class FilteredDirectoryTree(DirectoryTree):

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path
            for path in paths
            if path.is_dir() or path.suffix.lower() in ALLOWED_EXTENSIONS
        ]


class DirsOnlyTree(DirectoryTree):

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if path.is_dir()]


class DirBrowserDialog(ModalScreen[str | None]):
    """Modal directory browser that returns the selected directory path or None."""

    def __init__(self, start_path: Path | None = None, **kwargs):
        super().__init__(**kwargs)
        self._start_path = start_path or Path.home()
        self._selected_path: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="file-browser-container"):
            yield Label("Select Directory", id="file-browser-title")
            yield Static("", id="file-browser-path")
            yield DirsOnlyTree(self._start_path, id="file-browser-tree")
            with Horizontal(id="file-browser-buttons"):
                yield Button("Select", variant="primary", id="file-browser-select", disabled=True)
                yield Button("Cancel", variant="default", id="file-browser-cancel")

    def on_mount(self):
        self.query_one("#file-browser-tree").focus()

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected):
        event.stop()
        self._selected_path = str(event.path)
        self.query_one("#file-browser-path", Static).update(f"[dim]{event.path}[/]")
        self.query_one("#file-browser-select", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "file-browser-cancel":
            self.dismiss(None)
        elif event.button.id == "file-browser-select":
            self.dismiss(self._selected_path)


class FileBrowserDialog(ModalScreen[str | None]):
    """Modal file browser that returns the selected file path or None."""

    def __init__(self, start_path: Path | None = None, **kwargs):
        super().__init__(**kwargs)
        self._start_path = start_path or Path.home()

    def compose(self) -> ComposeResult:
        with Vertical(id="file-browser-container"):
            yield Label("Select File", id="file-browser-title")
            yield Static("", id="file-browser-path")
            yield FilteredDirectoryTree(self._start_path, id="file-browser-tree")
            with Horizontal(id="file-browser-buttons"):
                yield Button("Select", variant="primary", id="file-browser-select", disabled=True)
                yield Button("Cancel", variant="default", id="file-browser-cancel")

    def on_mount(self):
        self.query_one("#file-browser-tree").focus()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
        event.stop()
        self._selected_path = str(event.path)
        self.query_one("#file-browser-path", Static).update(
            f"[dim]{event.path}[/]"
        )
        self.query_one("#file-browser-select", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "file-browser-cancel":
            self.dismiss(None)
        elif event.button.id == "file-browser-select":
            self.dismiss(self._selected_path)
