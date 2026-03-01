"""Insights screen - AI chat + anomaly alerts."""

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Input, Static

from finance_tui.ai.insights import get_all_insights
from finance_tui.ai.nlq import query_nlq


class InsightsPane(Container):
    """Insights tab: anomaly alerts + NLQ chat interface."""

    def __init__(self, store=None, **kwargs):
        super().__init__(**kwargs)
        self._store = store

    def compose(self) -> ComposeResult:
        yield Static("[b]Insights & Alerts[/b]", id="insights-alerts")
        yield VerticalScroll(id="chat-log")
        yield Input(
            placeholder="Ask about your finances... (e.g., 'How much did I spend on food in February?')",
            id="chat-input",
        )

    def on_mount(self):
        if self._store:
            self._load_insights()

    @work(thread=True)
    def _load_insights(self):
        insights = get_all_insights(self._store.df, self._store.categories)
        if insights:
            alert_text = "[b]Insights & Alerts[/b]\n\n"
            icons = {
                "budget_over": "🔴",
                "budget_warning": "🟡",
                "outlier": "⚠️",
                "duplicate": "🔄",
            }
            for item in insights[:10]:
                icon = icons.get(item["type"], "ℹ️")
                alert_text += f"  {icon} {item['message']}\n"
            self.app.call_from_thread(
                self.query_one("#insights-alerts", Static).update, alert_text
            )

    def on_input_submitted(self, event: Input.Submitted):
        if not event.value.strip():
            return
        question = event.value.strip()
        event.input.value = ""
        self._ask_question(question)

    @work(thread=True)
    def _ask_question(self, question: str):
        import asyncio

        log = self.query_one("#chat-log", VerticalScroll)

        user_msg = Static(f"[b]You:[/b] {question}", classes="chat-user")
        self.app.call_from_thread(log.mount, user_msg)

        loading = Static("[dim]Thinking...[/dim]", classes="chat-ai")
        self.app.call_from_thread(log.mount, loading)

        loop = asyncio.new_event_loop()
        try:
            answer = loop.run_until_complete(
                query_nlq(question, self._store.df, self._store.categories)
            )
        except Exception as e:
            answer = f"Error: {e}"
        finally:
            loop.close()

        self.app.call_from_thread(loading.update, f"[b]AI:[/b] {answer}")
        self.app.call_from_thread(log.scroll_end, animate=False)
