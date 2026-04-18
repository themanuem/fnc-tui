"""Category management modal — list + edit sub-dialog."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Static


class CategoryEditDialog(ModalScreen[dict | None]):
    """Edit or create a single category."""

    def __init__(self, name: str = "", budget: float = 0.0, track: bool = False,
                 is_new: bool = True, **kwargs):
        super().__init__(**kwargs)
        self._name = name
        self._budget = budget
        self._track = track
        self._is_new = is_new

    def compose(self) -> ComposeResult:
        title = "New Category" if self._is_new else "Edit Category"
        with Vertical(id="cat-edit-container"):
            yield Label(title, id="cat-edit-title")
            yield Static("", id="cat-edit-error")
            yield Label("Name:")
            yield Input(value=self._name, id="cat-name-input")
            yield Label("Budget (€/month):")
            yield Input(value=str(self._budget) if self._budget else "", id="cat-budget-input",
                        placeholder="0")
            yield Checkbox("Track even without budget", value=self._track, id="cat-track-check")
            with Horizontal(id="cat-edit-buttons"):
                yield Button("Save", variant="primary", id="cat-save")
                if not self._is_new:
                    yield Button("Delete", variant="error", id="cat-delete")
                yield Button("Cancel", variant="default", id="cat-cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cat-cancel":
            self.dismiss(None)
        elif event.button.id == "cat-delete":
            self.dismiss({"action": "delete", "name": self._name})
        elif event.button.id == "cat-save":
            name = self.query_one("#cat-name-input", Input).value.strip()
            budget_str = self.query_one("#cat-budget-input", Input).value.strip()
            track = self.query_one("#cat-track-check", Checkbox).value

            if not name:
                self.query_one("#cat-edit-error", Static).update("[red]Name is required[/]")
                return
            try:
                budget = float(budget_str) if budget_str else 0.0
            except ValueError:
                self.query_one("#cat-edit-error", Static).update("[red]Budget must be a number[/]")
                return

            result = {
                "action": "save",
                "name": name,
                "budget": budget,
                "track": track,
                "original_name": self._name,
                "is_new": self._is_new,
            }
            self.dismiss(result)


class CategoryListDialog(ModalScreen[bool]):
    """List all categories with edit/create actions."""

    def __init__(self, categories: dict[str, dict], **kwargs):
        super().__init__(**kwargs)
        self._categories = categories

    def compose(self) -> ComposeResult:
        with Vertical(id="cat-list-container"):
            yield Label("Categories", id="cat-list-title")
            yield DataTable(id="cat-list-table")
            with Horizontal(id="cat-list-buttons"):
                yield Button("New Category", variant="primary", id="cat-new")
                yield Button("Close", variant="default", id="cat-close")

    def on_mount(self):
        self._refresh_table()

    def _refresh_table(self):
        table = self.query_one("#cat-list-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Category", "Budget", "Track")
        table.cursor_type = "row"
        for name in sorted(self._categories):
            meta = self._categories[name]
            budget = f"€{meta['budget']:.0f}/mo" if meta["budget"] else "-"
            track = "yes" if meta.get("track") else ""
            table.add_row(name, budget, track, key=name)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cat-close":
            self.dismiss(True)
        elif event.button.id == "cat-new":
            self.app.push_screen(
                CategoryEditDialog(is_new=True),
                callback=self._on_edit_result,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        name = str(event.row_key.value)
        meta = self._categories.get(name, {})
        self.app.push_screen(
            CategoryEditDialog(
                name=name,
                budget=meta.get("budget", 0.0),
                track=meta.get("track", False),
                is_new=False,
            ),
            callback=self._on_edit_result,
        )

    def _on_edit_result(self, result: dict | None):
        if result is None:
            return

        from finance_tui.config import CATEGORIES_DIR, TRANSACTIONS_DIR
        from finance_tui.writer import (
            delete_category_file,
            rename_category_everywhere,
            write_category_file,
        )

        watcher = getattr(self.app, "_watcher", None)

        if result["action"] == "delete":
            delete_category_file(result["name"])
            self._categories.pop(result["name"], None)
            self.app.notify(f"Deleted category: {result['name']}", timeout=2)

        elif result["action"] == "save":
            old_name = result.get("original_name", "")
            new_name = result["name"]
            budget = result["budget"]
            track = result["track"]

            # Rename if name changed on existing category
            if not result["is_new"] and old_name and old_name != new_name:
                modified = rename_category_everywhere(
                    old_name, new_name,
                    categories_dir=CATEGORIES_DIR,
                    transactions_dir=TRANSACTIONS_DIR,
                )
                if watcher:
                    for p in modified:
                        watcher.ignore_next_change(p)
                self._categories.pop(old_name, None)
                self.app.notify(
                    f"Renamed {old_name} → {new_name} ({len(modified)} files updated)",
                    timeout=3,
                )

            path = write_category_file(new_name, budget, track)
            if watcher:
                watcher.ignore_next_change(path)
            self._categories[new_name] = {"budget": budget, "track": track}

            action = "Created" if result["is_new"] else "Updated"
            if result["is_new"] or (old_name == new_name):
                self.app.notify(f"{action} category: {new_name}", timeout=2)

        self.app.store.load()
        self.app._refresh_all()
        self._categories = dict(self.app.store.categories)
        self._refresh_table()
