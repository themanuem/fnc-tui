"""Multi-step import wizard modal."""

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static


class ImportWizard(ModalScreen[bool]):
    """Three-step import wizard: file → mapping → preview + confirm."""

    def __init__(self, accounts: list[str], **kwargs):
        super().__init__(**kwargs)
        self._accounts = accounts
        self._step = 1
        self._df = None
        self._mapping = None
        self._transactions = None
        self._duplicates = []

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-container"):
            yield Label("Import Transactions", id="wizard-title")
            yield Static("", id="wizard-error")
            # Step 1: File selection
            with Vertical(id="wizard-step-1"):
                yield Label("File path:")
                with Horizontal(id="wizard-file-row"):
                    yield Input(placeholder="/path/to/export.csv", id="wizard-file")
                    yield Button("Browse", variant="default", id="wizard-browse")
                yield Label("Account:")
                yield Select(
                    [(a, a) for a in sorted(self._accounts)],
                    id="wizard-account",
                    prompt="Select account",
                )
                yield Label("LLM Provider:")
                yield Select(
                    [("Auto-detect", "auto"), ("Ollama", "ollama"), ("Anthropic", "anthropic")],
                    value="auto",
                    id="wizard-provider",
                )
            # Step 2: Column mapping
            with Vertical(id="wizard-step-2"):
                yield Label("Column Mapping", id="wizard-map-title")
                yield Label("Date column:")
                yield Select([], id="wizard-date-col", prompt="Select column")
                yield Label("Description column:")
                yield Select([], id="wizard-desc-col", prompt="Select column")
                yield Label("Amount column:")
                yield Select([], id="wizard-amount-col", prompt="Select column")
            # Step 3: Preview
            with Vertical(id="wizard-step-3"):
                yield Label("", id="wizard-preview-title")
                yield DataTable(id="wizard-preview-table")
                yield Static("", id="wizard-preview-stats")
                yield Static("", id="wizard-dupe-warning")
            # Buttons
            with Vertical(id="wizard-buttons"):
                yield Button("Next", variant="primary", id="wizard-next")
                yield Button("Back", variant="default", id="wizard-back")
                yield Button("Cancel", variant="default", id="wizard-cancel")

    def on_mount(self):
        self._show_step(1)

    _STEP_FOCUS = {
        1: "#wizard-file",
        2: "#wizard-date-col",
        3: "#wizard-preview-table",
    }

    def _show_step(self, step: int):
        self._step = step
        for i in range(1, 4):
            self.query_one(f"#wizard-step-{i}").display = i == step
        back = self.query_one("#wizard-back", Button)
        next_btn = self.query_one("#wizard-next", Button)
        back.display = step > 1
        next_btn.label = "Import" if step == 3 else "Next"
        self.query_one("#wizard-error", Static).update("")
        self.set_timer(0.1, lambda: self.query_one(self._STEP_FOCUS[step]).focus())

    def _show_error(self, msg: str):
        self.query_one("#wizard-error", Static).update(f"[red]{msg}[/]")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "wizard-browse":
            self._open_file_browser()
            return
        if event.button.id == "wizard-cancel":
            self.dismiss(False)
        elif event.button.id == "wizard-back":
            self._show_step(self._step - 1)
        elif event.button.id == "wizard-next":
            if self._step == 1:
                self._process_step1()
            elif self._step == 2:
                self._process_step2()
            elif self._step == 3:
                self._process_step3()

    def _open_file_browser(self):
        from finance_tui.screens.file_browser import FileBrowserDialog

        current = self.query_one("#wizard-file", Input).value.strip()
        start = Path(current).parent if current and Path(current).parent.is_dir() else Path.home()

        def on_select(result: str | None):
            if result:
                self.query_one("#wizard-file", Input).value = result

        self.app.push_screen(FileBrowserDialog(start_path=start), on_select)

    def _process_step1(self):
        file_input = self.query_one("#wizard-file", Input)
        account_select = self.query_one("#wizard-account", Select)
        provider_select = self.query_one("#wizard-provider", Select)

        file_path = Path(file_input.value.strip())
        if not file_path.exists():
            self._show_error(f"File not found: {file_path}")
            return
        if account_select.value == Select.BLANK:
            self._show_error("Please select an account")
            return

        self._file_path = file_path
        self._account = str(account_select.value)
        self._provider_choice = str(provider_select.value)
        self._read_and_map_file()

    @work(thread=True)
    def _read_and_map_file(self):
        from finance_tui.importers.readers import read_file
        from finance_tui.importers.mapper import detect_columns
        from finance_tui.importers.llm import Provider, detect_provider

        try:
            self._df = read_file(self._file_path)
        except Exception as e:
            self.app.call_from_thread(self._show_error, f"Read error: {e}")
            return

        columns = list(self._df.columns)
        col_options = [(c, c) for c in columns]

        # Try LLM mapping
        detected = None
        if self._provider_choice == "auto":
            provider = detect_provider()
        elif self._provider_choice == "ollama":
            provider = Provider.OLLAMA
        else:
            provider = Provider.ANTHROPIC

        if provider:
            try:
                detected = detect_columns(self._df, provider=provider)
            except Exception:
                pass

        def update_ui():
            for sel_id in ("#wizard-date-col", "#wizard-desc-col", "#wizard-amount-col"):
                sel = self.query_one(sel_id, Select)
                sel.set_options(col_options)

            if detected:
                self.query_one("#wizard-date-col", Select).value = detected.date_col
                self.query_one("#wizard-desc-col", Select).value = detected.description_col
                if detected.amount_col:
                    self.query_one("#wizard-amount-col", Select).value = detected.amount_col
                title = self.query_one("#wizard-map-title", Label)
                provider_name = provider.value if provider else "auto"
                title.update(f"Column Mapping [dim](detected by {provider_name})[/]")

            self._show_step(2)

        self.app.call_from_thread(update_ui)

    def _process_step2(self):
        from finance_tui.importers.mapper import ColumnMapping

        date_col = self.query_one("#wizard-date-col", Select).value
        desc_col = self.query_one("#wizard-desc-col", Select).value
        amount_col = self.query_one("#wizard-amount-col", Select).value

        if date_col == Select.BLANK or desc_col == Select.BLANK or amount_col == Select.BLANK:
            self._show_error("Please select all three columns")
            return

        self._mapping = ColumnMapping(
            date_col=str(date_col),
            description_col=str(desc_col),
            amount_col=str(amount_col),
        )
        self._build_preview()

    @work(thread=True)
    def _build_preview(self):
        from finance_tui.config import TRANSACTIONS_DIR
        from finance_tui.importers.transformer import detect_duplicates, transform
        from finance_tui.store import FinanceStore
        from finance_tui.writer import serialize_transaction

        try:
            self._transactions = transform(
                self._df, self._mapping, self._account,
                transactions_dir=TRANSACTIONS_DIR,
            )
        except Exception as e:
            self.app.call_from_thread(self._show_error, f"Transform error: {e}")
            return

        try:
            store = FinanceStore()
            self._duplicates = detect_duplicates(self._transactions, store.df)
        except Exception:
            self._duplicates = []

        txns = self._transactions

        def update_ui():
            count = len(txns)
            shown = min(10, count)
            self.query_one("#wizard-preview-title", Label).update(
                f"Preview ({shown} of {count} transactions)"
            )

            table = self.query_one("#wizard-preview-table", DataTable)
            table.clear(columns=True)
            table.add_columns("Date", "Description", "Amount")
            for t in txns[:10]:
                table.add_row(t.date.isoformat(), t.description, f"{t.amount:.2f}")

            total = sum(t.amount for t in txns)
            self.query_one("#wizard-preview-stats", Static).update(
                f"Total: [bold]{total:.2f}[/] | Count: [bold]{count}[/] | Account: [bold]{self._account}[/]"
            )

            if self._duplicates:
                n = len(self._duplicates)
                self.query_one("#wizard-dupe-warning", Static).update(
                    f"[yellow]Warning:[/] {n} potential duplicate{'s' if n != 1 else ''} detected"
                )
            else:
                self.query_one("#wizard-dupe-warning", Static).update("")

            self._show_step(3)

        self.app.call_from_thread(update_ui)

    def _process_step3(self):
        self._write_transactions()

    @work(thread=True)
    def _write_transactions(self):
        from finance_tui.config import TRANSACTIONS_DIR
        from finance_tui.writer import bulk_prepend_transactions, serialize_transaction

        lines = []
        for t in self._transactions:
            serialized = serialize_transaction(
                t.validated, t.amount, t.category, t.description,
                t.date.isoformat(), t.account, t.id,
            )
            lines.append((t.date.year, serialized))

        try:
            written = bulk_prepend_transactions(lines, TRANSACTIONS_DIR)
            count = len(self._transactions)
            files = ", ".join(p.name for p in written.values())

            def done():
                self.app.store.load()
                self.app._refresh_all()
                self.app.notify(f"{count} transactions imported to {files}", timeout=3)
                self.dismiss(True)

            self.app.call_from_thread(done)
        except Exception as e:
            self.app.call_from_thread(self._show_error, f"Write error: {e}")
