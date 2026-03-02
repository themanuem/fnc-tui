"""Transaction DataTable widget with inline editing."""

import calendar
import math
from datetime import date, timedelta

from rich.text import Text
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable

from finance_tui.config import CURRENCY

_BG_EVEN = None
_BG_ODD = "#222222"
_PAGE_SIZE = 50

# ── column layout ────────────────────────────────────────
_COL_STATUS = 0
_COL_ID = 1
_COL_DATE = 2
_COL_DESC = 3
_COL_AMOUNT = 4
_COL_CAT = 5
_COL_ACCT = 6
_COL_RUNSUM = 7
_COL_TAGS = 8
_COL_LINKS = 9
_NUM_COLS = 10

# Column index → edit type (None = disabled)
_COL_TYPE = {
    _COL_STATUS: None,
    _COL_ID: None,
    _COL_DATE: "date",
    _COL_DESC: "text",
    _COL_AMOUNT: "text",
    _COL_CAT: "enum",
    _COL_ACCT: "enum",
    _COL_RUNSUM: None,
    _COL_TAGS: "text",
    _COL_LINKS: "text",
}

_EDITABLE_COLS = [_COL_DATE, _COL_DESC, _COL_AMOUNT, _COL_CAT, _COL_ACCT, _COL_TAGS, _COL_LINKS]

# col → DataFrame field name (for saving edits)
_COL_FIELD = {
    _COL_DATE: "date",
    _COL_DESC: "description",
    _COL_AMOUNT: "amount",
    _COL_CAT: "category",
    _COL_ACCT: "account",
    _COL_TAGS: "tags",
    _COL_LINKS: "links",
}

# ── status icons ─────────────────────────────────────────
_STATUS_ICONS = {
    "validated": ("◆", "#5CB85C"),
    "unvalidated": ("◇", "#777777"),
    "outlier": ("◆", "#E8871E"),
    "duplicate": ("⊘", "#E8871E"),
}


class TransactionTable(DataTable):
    """DataTable showing financial transactions with inline editing.

    Modes:
      None   – row cursor, normal navigation
      "cell" – cell cursor, left/right between editable columns,
               up/down cycles enum/date values
      "text" – inline text editing with cursor
    """

    # ── messages ──────────────────────────────────────────────

    class TransactionEdited(Message):
        def __init__(self, txn_id: int, changes: dict) -> None:
            super().__init__()
            self.txn_id = txn_id
            self.changes = changes

    class TransactionCreated(Message):
        def __init__(self, values: dict) -> None:
            super().__init__()
            self.values = values

    class NewTransactionRequested(Message):
        pass

    # ── bindings ──────────────────────────────────────────────

    BINDINGS = [
        Binding("i", "sort_id", "Sort·Id", show=False),
        Binding("d", "sort_date", "Sort·Date", show=False),
        Binding("n", "next_page", "Next page", show=False),
        Binding("p", "prev_page", "Prev page", show=False),
        Binding("N", "last_page", "Last page", show=False),
        Binding("P", "first_page", "First page", show=False),
        Binding("alt+up", "cursor_page_top", "Top of page", show=False),
        Binding("alt+down", "cursor_page_bottom", "Bottom of page", show=False),
        Binding("l", "log_new", "Log new", show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = False
        self._sort_col = "date"
        self._sort_asc = False
        self._df = None
        self._skip_rows: set[int] = set()
        self._page = 0
        # Edit state
        self._edit_mode: str | None = None  # None | "cell" | "text"
        self._edit_values: dict[int, object] = {}
        self._original_values: dict[int, object] = {}
        self._editing_txn_id: int | None = None
        self._editing_row: int | None = None
        # Text edit buffer
        self._text_buffer: str = ""
        self._text_cursor: int = 0
        self._text_selected: bool = False
        self._text_col: int | None = None
        # Enum lists
        self._categories: list[str] = []
        self._accounts: list[str] = []
        # New transaction
        self._new_txn: dict | None = None
        # Column keys (set in on_mount)
        self._col_keys: list = []
        # Alert icon overrides: txn_id → alert type string
        self._alert_icons: dict[int, str] = {}
        # Multi-select: persists across pages, keyed on txn_id
        self._multi_selected: set[int] = set()

    def set_enums(self, categories: list[str], accounts: list[str]):
        """Update the category and account lists for enum cycling."""
        self._categories = sorted(categories)
        self._accounts = sorted(accounts)

    def set_alert_icons(self, alert_map: dict[int, str]):
        """Set per-transaction alert type overrides for the status column."""
        self._alert_icons = alert_map

    def on_mount(self):
        self._col_keys = list(self.add_columns(
            " ", "Id", "Date", "Description", "Amount", "Category",
            "Account", "Running Sum", "Tags", "Links",
        ))
        self._update_sort_title()

    def load_data(self, df):
        """Load transaction data from a DataFrame."""
        self._df = df.copy()
        self._page = 0
        self._multi_selected.clear()
        self._exit_edit_mode(cancel=True)
        self._render_rows()

    # ── helpers ──────────────────────────────────────────────

    def _cell(self, text: str, color: str = "#BBBBBB", bg: str | None = None) -> Text:
        t = Text(text)
        style = color
        if bg:
            style += f" on {bg}"
        t.stylize(style)
        return t

    def _status_cell(self, txn_id: int, validated: bool, bg: str | None = None) -> Text:
        """Build the status icon cell for a transaction."""
        if txn_id in self._multi_selected:
            return self._cell("∗", "#E8871E", bg)
        if validated:
            icon, color = _STATUS_ICONS["validated"]
        elif txn_id in self._alert_icons:
            alert_type = self._alert_icons[txn_id]
            icon, color = _STATUS_ICONS.get(alert_type, _STATUS_ICONS["unvalidated"])
        else:
            icon, color = _STATUS_ICONS["unvalidated"]
        return self._cell(icon, color, bg)

    def _tags_cell(self, tags: list, bg: str | None = None) -> Text:
        """Build styled Text for tags (displayed with # prefix, cyan)."""
        if not tags:
            return self._cell("", bg=bg)
        t = Text()
        style = "#4FC1E9"
        if bg:
            style += f" on {bg}"
        for i, tag in enumerate(tags):
            if i > 0:
                t.append(", ", style=f"#BBBBBB on {bg}" if bg else "#BBBBBB")
            t.append(tag, style=style)
        return t

    def _links_cell(self, links: list, bg: str | None = None) -> Text:
        """Build styled Text for links (displayed with [[]] wrapper, purple)."""
        if not links:
            return self._cell("", bg=bg)
        t = Text()
        style = "#AC92EC"
        if bg:
            style += f" on {bg}"
        for i, link in enumerate(links):
            if i > 0:
                t.append(", ", style=f"#BBBBBB on {bg}" if bg else "#BBBBBB")
            t.append(link, style=style)
        return t

    @property
    def _total_pages(self) -> int:
        if self._df is None or self._df.empty:
            return 1
        return max(1, math.ceil(len(self._df) / _PAGE_SIZE))

    def _update_sort_title(self):
        arrow = "↑" if self._sort_asc else "↓"
        name = "Id" if self._sort_col == "id" else "Date"
        page_info = f"{self._page + 1}/{self._total_pages}"
        self.border_title = f"{name} {arrow}  {page_info}"
        sel_count = len(self._multi_selected)
        sel_hint = f"  [#E8871E bold]{sel_count} sel[/]" if sel_count else ""
        self.border_subtitle = (
            "[#E8871E]space[/]·Sel  "
            "[#E8871E]i[/]·Id  [#E8871E]d[/]·Date  "
            "[#E8871E]v[/]·Validate  [#E8871E]c[/]·Cat  "
            "[#E8871E]m[/]·Tags  [#E8871E]w[/]·Links  "
            "[#E8871E]l[/]·Log  "
            "[#E8871E]p[/]·Prev  [#E8871E]n[/]·Next"
            + sel_hint
        )

    def _get_editing_row_key(self):
        """Get the RowKey for the row currently being edited."""
        if self._editing_row is None:
            return None
        try:
            rk, _ = self.coordinate_to_cell_key(Coordinate(self._editing_row, 0))
            return rk
        except Exception:
            return None

    def focus_transaction(self, txn_id: int):
        """Move cursor to the row with the given transaction id."""
        for row_idx in range(self.row_count):
            if row_idx in self._skip_rows:
                continue
            try:
                rk, _ = self.coordinate_to_cell_key(Coordinate(row_idx, 0))
                if str(rk.value) == str(txn_id):
                    self.move_cursor(row=row_idx)
                    return
            except Exception:
                continue

    # ── key dispatch ─────────────────────────────────────────

    def on_key(self, event) -> None:
        if self._edit_mode == "text":
            self._handle_text_key(event)
            event.stop()
            event.prevent_default()
            return

        if self._edit_mode == "cell":
            self._handle_cell_key(event)
            event.stop()
            event.prevent_default()
            return

        # Row mode: multi-select keys
        if event.key == "space":
            self._toggle_multi_select()
            event.stop()
            event.prevent_default()
            return

        if event.key == "ctrl+a":
            self._select_all_page()
            event.stop()
            event.prevent_default()
            return

        if event.key == "ctrl+shift+a":
            self._select_all_global()
            event.stop()
            event.prevent_default()
            return

        if event.key in ("shift+up", "shift+down"):
            self._extend_selection(event.key)
            event.stop()
            event.prevent_default()
            return

        # Row mode: direct column shortcuts
        if event.key == "m":
            self._enter_cell_mode_at(_COL_TAGS)
            event.stop()
            event.prevent_default()
            return

        if event.key == "w":
            self._enter_cell_mode_at(_COL_LINKS)
            event.stop()
            event.prevent_default()
            return

        # Row mode: Enter enters cell mode
        if event.key == "enter":
            self._enter_cell_mode()
            event.stop()
            event.prevent_default()

    # ── row cursor: skip non-data rows ───────────────────────

    def action_cursor_down(self):
        target = self.cursor_coordinate.row + 1
        while target < self.row_count and target in self._skip_rows:
            target += 1
        if target < self.row_count:
            self.move_cursor(row=target)

    def action_cursor_up(self):
        target = self.cursor_coordinate.row - 1
        while target >= 0 and target in self._skip_rows:
            target -= 1
        if target >= 0:
            self.move_cursor(row=target)

    def _move_cursor_to_first_data_row(self):
        if self.row_count == 0:
            return
        target = 0
        while target < self.row_count and target in self._skip_rows:
            target += 1
        if target < self.row_count:
            self.move_cursor(row=target)

    def action_cursor_page_top(self):
        self._move_cursor_to_first_data_row()

    def action_cursor_page_bottom(self):
        if self.row_count == 0:
            return
        target = self.row_count - 1
        while target >= 0 and target in self._skip_rows:
            target -= 1
        if target >= 0:
            self.move_cursor(row=target)

    # ── pagination ───────────────────────────────────────────

    def action_next_page(self):
        if self._page < self._total_pages - 1:
            self._page += 1
            self._update_sort_title()
            self._render_rows()

    def action_prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._update_sort_title()
            self._render_rows()

    def action_first_page(self):
        if self._page != 0:
            self._page = 0
            self._update_sort_title()
            self._render_rows()

    def action_last_page(self):
        last = self._total_pages - 1
        if self._page != last:
            self._page = last
            self._update_sort_title()
            self._render_rows()

    # ── multi-select ──────────────────────────────────────────

    def _toggle_multi_select(self):
        """Toggle the current row's txn_id in the multi-select set."""
        if self.row_count == 0:
            return
        current_row = self.cursor_coordinate.row
        if current_row in self._skip_rows:
            return
        try:
            rk, _ = self.coordinate_to_cell_key(Coordinate(current_row, 0))
        except Exception:
            return
        key_val = str(rk.value)
        if key_val.startswith("__"):
            return
        txn_id = int(key_val)
        if txn_id in self._multi_selected:
            self._multi_selected.discard(txn_id)
        else:
            self._multi_selected.add(txn_id)
        # Update status cell in-place
        if self._df is not None:
            txn = self._df[self._df["id"] == txn_id]
            if not txn.empty:
                validated = bool(txn.iloc[0].get("validated", False))
                self.update_cell(rk, self._col_keys[_COL_STATUS], self._status_cell(txn_id, validated))
        self._update_sort_title()

    def _get_page_txn_ids(self) -> list[int]:
        """Return all txn_ids visible on the current page."""
        ids = []
        for row_idx in range(self.row_count):
            if row_idx in self._skip_rows:
                continue
            try:
                rk, _ = self.coordinate_to_cell_key(Coordinate(row_idx, 0))
            except Exception:
                continue
            key_val = str(rk.value)
            if key_val.startswith("__"):
                continue
            ids.append(int(key_val))
        return ids

    def _select_all_page(self):
        """Toggle-select all transactions on the current page (ctrl+a)."""
        page_ids = set(self._get_page_txn_ids())
        if page_ids <= self._multi_selected:
            # All already selected → deselect page
            self._multi_selected -= page_ids
        else:
            self._multi_selected |= page_ids
        self._render_rows()
        self._update_sort_title()

    def _select_all_global(self):
        """Toggle-select all transactions across all pages (ctrl+shift+a)."""
        if self._df is None or self._df.empty:
            return
        all_ids = set(self._df["id"].astype(int).tolist())
        if all_ids <= self._multi_selected:
            self._multi_selected.clear()
        else:
            self._multi_selected = all_ids
        self._render_rows()
        self._update_sort_title()

    def _extend_selection(self, key: str):
        """Select the current row and move cursor in direction (shift+up/down)."""
        # Select current row first
        self._toggle_multi_select_add()
        # Move cursor
        if key == "shift+down":
            self.action_cursor_down()
        else:
            self.action_cursor_up()
        # Select the new row too
        self._toggle_multi_select_add()

    def _toggle_multi_select_add(self):
        """Add the current row's txn_id to multi-select (no toggle-off)."""
        if self.row_count == 0:
            return
        current_row = self.cursor_coordinate.row
        if current_row in self._skip_rows:
            return
        try:
            rk, _ = self.coordinate_to_cell_key(Coordinate(current_row, 0))
        except Exception:
            return
        key_val = str(rk.value)
        if key_val.startswith("__"):
            return
        txn_id = int(key_val)
        self._multi_selected.add(txn_id)
        if self._df is not None:
            txn = self._df[self._df["id"] == txn_id]
            if not txn.empty:
                validated = bool(txn.iloc[0].get("validated", False))
                self.update_cell(rk, self._col_keys[_COL_STATUS], self._status_cell(txn_id, validated))
        self._update_sort_title()

    # ── cell mode ────────────────────────────────────────────

    def _enter_cell_mode(self):
        """Switch from row mode to cell mode on the current row."""
        if self.row_count == 0:
            return
        current_row = self.cursor_coordinate.row
        if current_row in self._skip_rows:
            return
        try:
            rk, _ = self.coordinate_to_cell_key(Coordinate(current_row, 0))
        except Exception:
            return
        key_val = str(rk.value)
        if key_val.startswith("__"):
            return

        txn_id = int(key_val)
        if self._df is None:
            return
        txn = self._df[self._df["id"] == txn_id]
        if txn.empty:
            return
        txn = txn.iloc[0]

        self._editing_txn_id = txn_id
        self._editing_row = current_row
        tags = txn.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        links = txn.get("links", [])
        if not isinstance(links, list):
            links = []
        self._original_values = {
            _COL_DATE: txn["date"].strftime("%Y-%m-%d"),
            _COL_DESC: str(txn["description"]),
            _COL_AMOUNT: float(txn["amount"]),
            _COL_CAT: str(txn["category"]),
            _COL_ACCT: str(txn["account"]),
            _COL_TAGS: ", ".join(tags),
            _COL_LINKS: ", ".join(links),
        }
        self._edit_values = {}
        self._edit_mode = "cell"
        self.cursor_type = "cell"
        self.move_cursor(row=current_row, column=_COL_DESC)
        self.add_class("editing")

    def _enter_cell_mode_at(self, col: int):
        """Enter cell mode and immediately open text edit on the given column."""
        self._enter_cell_mode()
        if self._edit_mode != "cell":
            return
        self.move_cursor(row=self._editing_row, column=col)
        self._enter_text_mode(col)

    def _handle_cell_key(self, event):
        col = self.cursor_coordinate.column
        col_type = _COL_TYPE.get(col)
        key = event.key

        if key == "escape":
            self._exit_edit_mode(cancel=True)
        elif key == "enter":
            if col_type == "text":
                self._enter_text_mode(col)
            else:
                self._save_and_exit()
        elif key == "left":
            self._move_to_editable_col(-1)
        elif key == "right":
            self._move_to_editable_col(1)
        elif key in ("up", "down"):
            delta = 1 if key == "down" else -1
            if col_type == "enum":
                self._cycle_enum(col, delta)
            elif col_type == "date":
                self._cycle_date(days=delta)
        elif key in ("shift+up", "shift+down"):
            if col_type == "date":
                delta = 1 if key == "shift+down" else -1
                self._cycle_date(months=delta)

    def _move_to_editable_col(self, direction: int):
        col = self.cursor_coordinate.column
        row = self.cursor_coordinate.row
        if col in _EDITABLE_COLS:
            idx = _EDITABLE_COLS.index(col)
        else:
            idx = 0 if direction > 0 else len(_EDITABLE_COLS) - 1
        new_idx = idx + direction
        if 0 <= new_idx < len(_EDITABLE_COLS):
            self.move_cursor(row=row, column=_EDITABLE_COLS[new_idx])

    def _cycle_enum(self, col: int, delta: int):
        values = self._categories if col == _COL_CAT else self._accounts
        if not values:
            return
        current = self._edit_values.get(col, self._original_values.get(col, ""))
        try:
            idx = values.index(str(current))
        except ValueError:
            idx = 0
        new_idx = (idx + delta) % len(values)
        new_val = values[new_idx]
        self._edit_values[col] = new_val
        self._update_edit_cell(col, new_val)

    def _cycle_date(self, days: int = 0, months: int = 0):
        current_str = str(self._edit_values.get(
            _COL_DATE, self._original_values.get(_COL_DATE, ""),
        ))
        y, m, d = (int(x) for x in current_str.split("-"))
        current_date = date(y, m, d)

        if days:
            current_date += timedelta(days=days)
        if months:
            new_m = current_date.month + months
            new_y = current_date.year
            while new_m > 12:
                new_m -= 12
                new_y += 1
            while new_m < 1:
                new_m += 12
                new_y -= 1
            max_day = calendar.monthrange(new_y, new_m)[1]
            current_date = date(new_y, new_m, min(current_date.day, max_day))

        date_str = current_date.strftime("%Y-%m-%d")
        self._edit_values[_COL_DATE] = date_str
        self._update_edit_cell(_COL_DATE, date_str)

    def _update_edit_cell(self, col: int, value):
        """Update the visual cell content during editing."""
        row_key = self._get_editing_row_key()
        if row_key is None:
            return
        if col == _COL_AMOUNT:
            try:
                amt = float(value)
                color = "#5CB85C" if amt >= 0 else "#D9534F"
                text = Text(f"{amt:+,.2f} {CURRENCY}")
                text.stylize(color)
            except (ValueError, TypeError):
                text = self._cell(str(value))
        elif col == _COL_TAGS:
            items = [x.strip() for x in str(value).split(",") if x.strip()]
            text = self._tags_cell(items)
        elif col == _COL_LINKS:
            items = [x.strip() for x in str(value).split(",") if x.strip()]
            text = self._links_cell(items)
        else:
            text = self._cell(str(value))
        self.update_cell(row_key, self._col_keys[col], text)

    # ── text editing mode ────────────────────────────────────

    def _enter_text_mode(self, col: int):
        self._text_col = col
        current = self._edit_values.get(col, self._original_values.get(col, ""))
        self._text_buffer = str(current)
        self._text_cursor = len(self._text_buffer)
        self._text_selected = True
        self._edit_mode = "text"
        self._render_text_cell()

    def _handle_text_key(self, event):
        key = event.key

        if key == "escape":
            self._edit_mode = "cell"
            col = self._text_col
            value = self._edit_values.get(col, self._original_values.get(col, ""))
            self._update_edit_cell(col, value)
            self._text_col = None
            return

        if key == "enter":
            self._confirm_text()
            self._save_and_exit()
            return

        if key == "left":
            if self._text_selected:
                self._text_selected = False
                self._text_cursor = 0
            elif self._text_cursor > 0:
                self._text_cursor -= 1
            self._render_text_cell()
            return

        if key == "right":
            if self._text_selected:
                self._text_selected = False
            elif self._text_cursor < len(self._text_buffer):
                self._text_cursor += 1
            self._render_text_cell()
            return

        if key == "home":
            self._text_selected = False
            self._text_cursor = 0
            self._render_text_cell()
            return

        if key == "end":
            self._text_selected = False
            self._text_cursor = len(self._text_buffer)
            self._render_text_cell()
            return

        if key == "backspace":
            if self._text_selected:
                self._text_buffer = ""
                self._text_cursor = 0
                self._text_selected = False
            elif self._text_cursor > 0:
                self._text_buffer = (
                    self._text_buffer[: self._text_cursor - 1]
                    + self._text_buffer[self._text_cursor :]
                )
                self._text_cursor -= 1
            self._render_text_cell()
            return

        if key == "delete":
            if self._text_selected:
                self._text_buffer = ""
                self._text_cursor = 0
                self._text_selected = False
            elif self._text_cursor < len(self._text_buffer):
                self._text_buffer = (
                    self._text_buffer[: self._text_cursor]
                    + self._text_buffer[self._text_cursor + 1 :]
                )
            self._render_text_cell()
            return

        # Printable character
        if event.character and event.is_printable:
            if self._text_selected:
                self._text_buffer = event.character
                self._text_cursor = 1
                self._text_selected = False
            else:
                self._text_buffer = (
                    self._text_buffer[: self._text_cursor]
                    + event.character
                    + self._text_buffer[self._text_cursor :]
                )
                self._text_cursor += 1
            self._render_text_cell()

    def _render_text_cell(self):
        """Render the text cell with cursor indicator."""
        col = self._text_col
        if col is None:
            return
        row_key = self._get_editing_row_key()
        if row_key is None:
            return

        buf = self._text_buffer
        if self._text_selected:
            t = Text(buf or " ")
            t.stylize("reverse bold")
        else:
            t = Text()
            before = buf[: self._text_cursor]
            at = buf[self._text_cursor] if self._text_cursor < len(buf) else " "
            after = buf[self._text_cursor + 1 :] if self._text_cursor < len(buf) else ""
            t.append(before)
            t.append(at, style="reverse")
            t.append(after)

        self.update_cell(row_key, self._col_keys[col], t)

    def _confirm_text(self):
        """Store text buffer value into edit_values."""
        col = self._text_col
        if col is None:
            return
        if col == _COL_AMOUNT:
            try:
                self._edit_values[col] = float(self._text_buffer)
            except ValueError:
                return  # invalid number, keep original
        else:
            self._edit_values[col] = self._text_buffer
        self._text_col = None

    # ── save / exit ──────────────────────────────────────────

    def _save_and_exit(self):
        """Save pending edits and return to row mode."""
        if self._text_col is not None:
            self._confirm_text()

        if self._new_txn is not None:
            values = dict(self._new_txn)
            for col, val in self._edit_values.items():
                field = _COL_FIELD.get(col)
                if field:
                    if field in ("tags", "links"):
                        val = [t.strip() for t in str(val).split(",") if t.strip()]
                    values[field] = val
            self._new_txn = None
            self._exit_edit_mode(cancel=False)
            self.post_message(self.TransactionCreated(values))
        elif self._edit_values and self._editing_txn_id is not None:
            changes = {}
            for col, val in self._edit_values.items():
                field = _COL_FIELD.get(col)
                if field:
                    if field in ("tags", "links"):
                        val = [t.strip() for t in str(val).split(",") if t.strip()]
                    changes[field] = val
            txn_id = self._editing_txn_id
            self._exit_edit_mode(cancel=False)
            self.post_message(self.TransactionEdited(txn_id, changes))
        else:
            self._exit_edit_mode(cancel=True)

    def _exit_edit_mode(self, cancel: bool = False):
        """Leave edit mode. If cancel, restore original cell values."""
        if cancel and self._edit_mode and self._editing_row is not None:
            row_key = self._get_editing_row_key()
            if row_key is not None:
                for col, val in self._original_values.items():
                    if col == _COL_AMOUNT:
                        amt = float(val)
                        t = Text(f"{amt:+,.2f} {CURRENCY}")
                        t.stylize("#5CB85C" if amt >= 0 else "#D9534F")
                    elif col == _COL_TAGS:
                        items = [x.strip() for x in str(val).split(",") if x.strip()]
                        t = self._tags_cell(items)
                    elif col == _COL_LINKS:
                        items = [x.strip() for x in str(val).split(",") if x.strip()]
                        t = self._links_cell(items)
                    else:
                        t = self._cell(str(val))
                    try:
                        self.update_cell(row_key, self._col_keys[col], t)
                    except Exception:
                        pass

        if cancel and self._new_txn is not None:
            try:
                self.remove_row("__new__")
            except Exception:
                pass
            self._new_txn = None

        self._edit_mode = None
        self._edit_values = {}
        self._original_values = {}
        self._editing_txn_id = None
        self._editing_row = None
        self._text_col = None
        self._text_buffer = ""
        self._text_cursor = 0
        self._text_selected = False
        self.cursor_type = "row"
        self.remove_class("editing")

    # ── new transaction ──────────────────────────────────────

    def action_log_new(self):
        if self._edit_mode is not None:
            return
        self.post_message(self.NewTransactionRequested())

    def start_new_transaction(self, txn_id: int, df=None):
        """Set up a new transaction row and enter cell mode on it."""
        today = date.today().strftime("%Y-%m-%d")
        category = self._categories[0] if self._categories else ""
        account = self._accounts[0] if self._accounts else ""
        self._new_txn = {
            "id": txn_id,
            "date": today,
            "description": "",
            "amount": 0.0,
            "category": category,
            "account": account,
            "tags": [],
            "links": [],
        }
        if df is not None:
            self._df = df.copy()
        self._page = 0
        self._render_rows()
        # Find the __new__ row and enter cell mode
        for row_idx in range(self.row_count):
            if row_idx in self._skip_rows:
                continue
            try:
                rk, _ = self.coordinate_to_cell_key(Coordinate(row_idx, 0))
                if str(rk.value) == "__new__":
                    self._editing_txn_id = None
                    self._editing_row = row_idx
                    self._original_values = {
                        _COL_DATE: self._new_txn["date"],
                        _COL_DESC: self._new_txn["description"],
                        _COL_AMOUNT: self._new_txn["amount"],
                        _COL_CAT: self._new_txn["category"],
                        _COL_ACCT: self._new_txn["account"],
                        _COL_TAGS: "",
                        _COL_LINKS: "",
                    }
                    self._edit_values = {}
                    self._edit_mode = "cell"
                    self.cursor_type = "cell"
                    self.move_cursor(row=row_idx, column=_COL_DESC)
                    self.add_class("editing")
                    return
            except Exception:
                continue

    # ── rendering ────────────────────────────────────────────

    def _render_rows(self):
        self.clear()
        self._skip_rows.clear()
        self._update_sort_title()

        table_row = 0
        e_count = _NUM_COLS  # number of empty cells per filler row

        # New transaction row at top
        if self._new_txn is not None:
            txn = self._new_txn
            amt = txn["amount"]
            self.add_row(
                self._cell("△", "#888888"),
                self._cell(str(txn["id"]), "#888888"),
                self._cell(txn["date"]),
                self._cell(txn["description"] or "…", "#888888"),
                self._cell(
                    f"{amt:+,.2f} {CURRENCY}",
                    "#5CB85C" if amt >= 0 else "#D9534F",
                ),
                self._cell(txn["category"]),
                self._cell(txn["account"]),
                self._cell("—", "#555555"),
                self._tags_cell(txn.get("tags", [])),
                self._links_cell(txn.get("links", [])),
                key="__new__",
            )
            table_row += 1

        if self._df is None or self._df.empty:
            if self._new_txn is None:
                return
            self._move_cursor_to_first_data_row()
            return

        df = self._df.sort_values(
            self._sort_col, ascending=self._sort_asc,
        ).reset_index(drop=True)

        start = self._page * _PAGE_SIZE
        end = start + _PAGE_SIZE
        df = df.iloc[start:end].reset_index(drop=True)

        # Day groups
        prev_date = None
        grp = 0
        groups = []
        for _, row in df.iterrows():
            d = row["date"].strftime("%Y-%m-%d")
            if d != prev_date:
                if prev_date is not None:
                    grp += 1
                prev_date = d
            groups.append(grp)

        group_sums: dict[int, float] = {}
        group_dates: dict[int, str] = {}
        for i, (_, row) in enumerate(df.iterrows()):
            g = groups[i]
            group_sums[g] = group_sums.get(g, 0.0) + row["amount"]
            group_dates[g] = row["date"].strftime("%Y-%m-%d")

        first_of_group: dict[int, int] = {}
        last_of_group: dict[int, int] = {}
        for idx, g in enumerate(groups):
            if g not in first_of_group:
                first_of_group[g] = idx
            last_of_group[g] = idx
        first_indices = set(first_of_group.values())
        last_indices = set(last_of_group.values())

        for i, (_, row) in enumerate(df.iterrows()):
            g = groups[i]
            bg = _BG_ODD if g % 2 else _BG_EVEN

            if i in first_indices:
                day_sum = group_sums[g]
                date_str = group_dates[g]
                e = self._cell("", "#333333", bg)
                self.add_row(
                    e, e, e,
                    self._cell(
                        f"── {date_str}  Σ {day_sum:,.2f} {CURRENCY} ──",
                        "#555555", bg,
                    ),
                    *[e] * (e_count - 4),
                    key=f"__day__{g}",
                )
                self._skip_rows.add(table_row)
                table_row += 1

            amt = row["amount"]
            txn_id = int(row["id"])
            validated = bool(row.get("validated", False))
            tags = row.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            links = row.get("links", [])
            if not isinstance(links, list):
                links = []
            self.add_row(
                self._status_cell(txn_id, validated, bg),
                self._cell(str(txn_id), bg=bg),
                self._cell(row["date"].strftime("%Y-%m-%d"), bg=bg),
                self._cell(str(row["description"]), bg=bg),
                self._cell(
                    f"{amt:+,.2f} {CURRENCY}",
                    "#5CB85C" if amt >= 0 else "#D9534F",
                    bg,
                ),
                self._cell(str(row["category"]), bg=bg),
                self._cell(str(row["account"]), bg=bg),
                self._cell(f"{row['running_sum']:,.2f} {CURRENCY}", bg=bg),
                self._tags_cell(tags, bg),
                self._links_cell(links, bg),
                key=str(txn_id),
            )
            table_row += 1

            if i in last_indices:
                e = self._cell("", bg=bg)
                self.add_row(*[e] * e_count, key=f"__empty__{g}")
                self._skip_rows.add(table_row)
                table_row += 1

        self._move_cursor_to_first_data_row()

    # ── sort actions ─────────────────────────────────────────

    def action_sort_id(self):
        if self._sort_col == "id":
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = "id"
            self._sort_asc = True
        self._page = 0
        self._update_sort_title()
        self._render_rows()

    def action_sort_date(self):
        if self._sort_col == "date":
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = "date"
            self._sort_asc = False
        self._page = 0
        self._update_sort_title()
        self._render_rows()
