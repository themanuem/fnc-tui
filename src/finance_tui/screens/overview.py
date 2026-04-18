"""Overview screen - compact btop-style layout."""

import pandas as pd
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical

from finance_tui import analytics
from finance_tui.config import CURRENCY
from finance_tui.widgets.account_table import AccountPanel
from finance_tui.widgets.alerts_panel import AlertsPanel
from finance_tui.widgets.annotations_panel import AnnotationsPanel
from finance_tui.widgets.budget_bar import BudgetPanel
from finance_tui.widgets.donut_chart import ExpenseCategoryPanel, IncomeCategoryPanel
from finance_tui.widgets.evolution_chart import EvolutionChart
from finance_tui.widgets.heatmap import SpendingHeatmap
from finance_tui.widgets.kpi_card import KpiCard


_SENTIMENT_COLORS = {
    "positive": "#5CB85C",
    "negative": "#D9534F",
    "neutral": "#E0E0E0",
}


def _kpi_with_rate(main: str, sentiment: str, rate: float | None) -> Text:
    """Build KPI text with an optional muted rate suffix."""
    color = _SENTIMENT_COLORS.get(sentiment, "#E0E0E0")
    text = Text(main, style=f"{color} bold")
    if rate is not None:
        text.append(f" ({rate:+.1f}%)", style="#777777")
    return text


class OverviewPane(Container):
    """Overview tab: compact KPIs, charts, accounts, budgets."""

    def __init__(self, store=None, **kwargs):
        super().__init__(**kwargs)
        self.store = store

    def compose(self) -> ComposeResult:
        df = self.store.df if self.store else pd.DataFrame()
        period = analytics.fiscal_period()

        balance = analytics.global_balance(df)
        yoy_rate = analytics.balance_yoy_rate(df)
        count = analytics.transaction_count(df)
        growth = analytics.net_growth_mom(df)
        growth_rate = analytics.net_growth_mom_rate(df)
        last_date = analytics.last_transaction_date(df)

        bal_sentiment = "positive" if balance >= 0 else "negative"
        balance_text = _kpi_with_rate(f"{balance:,.2f} {CURRENCY}", bal_sentiment, yoy_rate)

        growth_sentiment = "positive" if growth >= 0 else "negative"
        growth_text = _kpi_with_rate(f"{growth:+,.2f} {CURRENCY}", growth_sentiment, growth_rate)

        with Horizontal(classes="kpi-row"):
            yield KpiCard(
                title="Balance",
                value=balance_text,
                sentiment=bal_sentiment,
                id="kpi-balance",
            )
            yield KpiCard(
                title="MoM Growth",
                value=growth_text,
                sentiment=growth_sentiment,
                id="kpi-growth",
            )
            yield KpiCard(
                title="Transactions",
                value=f"{count:,}",
                sentiment="neutral",
                id="kpi-count",
            )
            yield KpiCard(
                title="Last Txn",
                value=last_date.strftime("%Y-%m-%d") if last_date else "—",
                sentiment="neutral",
                id="kpi-last",
            )
            yield KpiCard(
                title="Period",
                value=period,
                sentiment="neutral",
                id="kpi-period",
            )

        with Horizontal(classes="charts-row"):
            with Vertical(classes="half"):
                acct = AccountPanel(df, id="panel-1")
                acct.border_title = "1·Accounts"
                yield acct
                hmap = SpendingHeatmap(df, id="panel-2")
                hmap.border_title = "2·Activity Heatmap"
                yield hmap
            evo = EvolutionChart(df, classes="half", id="panel-3")
            yield evo

        with Horizontal(classes="bottom-row"):
            exp = ExpenseCategoryPanel(df, classes="third", id="panel-4")
            exp.border_title = "4·Expenses by Category"
            yield exp
            inc = IncomeCategoryPanel(df, classes="third", id="panel-5")
            inc.border_title = "5·Income by Category"
            yield inc
            cats = self.store.categories if self.store else {}
            bud = BudgetPanel(df, cats, classes="third", id="panel-6")
            bud.border_title = "6·Months Over Budget"
            yield bud

        with Horizontal(classes="alerts-row"):
            alerts = AlertsPanel(self.store, id="panel-7")
            alerts.border_title = "7·Alerts"
            yield alerts
            ann = AnnotationsPanel(df, id="panel-8")
            ann.border_title = "8·Tags & Links"
            yield ann

    def refresh_data(self, df: pd.DataFrame, period_label: str = ""):
        """Refresh all overview panels and KPIs with filtered data."""
        # KPIs
        balance = analytics.global_balance(df)
        yoy_rate = analytics.balance_yoy_rate(df)
        growth = analytics.net_growth_mom(df)
        growth_rate = analytics.net_growth_mom_rate(df)
        count = analytics.transaction_count(df)
        last_date = analytics.last_transaction_date(df)

        bal_sentiment = "positive" if balance >= 0 else "negative"
        growth_sentiment = "positive" if growth >= 0 else "negative"

        try:
            self.query_one("#kpi-balance", KpiCard).update_value(
                _kpi_with_rate(f"{balance:,.2f} {CURRENCY}", bal_sentiment, yoy_rate),
                bal_sentiment,
            )
            self.query_one("#kpi-growth", KpiCard).update_value(
                _kpi_with_rate(f"{growth:+,.2f} {CURRENCY}", growth_sentiment, growth_rate),
                growth_sentiment,
            )
            self.query_one("#kpi-count", KpiCard).update_value(
                f"{count:,}", "neutral",
            )
            self.query_one("#kpi-last", KpiCard).update_value(
                last_date.strftime("%Y-%m-%d") if last_date else "—",
                "neutral",
            )
            if period_label:
                self.query_one("#kpi-period", KpiCard).update_value(
                    period_label, "neutral",
                )
        except Exception:
            pass

        # Panels
        try:
            self.query_one("#panel-1", AccountPanel).refresh_data(df)
            self.query_one("#panel-2", SpendingHeatmap).refresh_data(df)
            self.query_one("#panel-3", EvolutionChart).refresh_data(df)
            self.query_one("#panel-4", ExpenseCategoryPanel).refresh_data(df)
            self.query_one("#panel-5", IncomeCategoryPanel).refresh_data(df)
            budget = self.query_one("#panel-6", BudgetPanel)
            if self.store:
                budget._categories = self.store.categories
            budget.refresh_data(df)
            alerts = self.query_one("#panel-7", AlertsPanel)
            if self.store:
                alerts._store = self.store
            alerts.refresh_data(df)
            self.query_one("#panel-8", AnnotationsPanel).refresh_data(df)
        except Exception:
            pass
