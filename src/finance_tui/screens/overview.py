"""Overview screen - compact btop-style layout."""

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical

from finance_tui import analytics
from finance_tui.config import CURRENCY
from finance_tui.widgets.account_table import AccountPanel
from finance_tui.widgets.alerts_panel import AlertsPanel
from finance_tui.widgets.budget_bar import BudgetPanel
from finance_tui.widgets.donut_chart import ExpenseCategoryPanel, IncomeCategoryPanel
from finance_tui.widgets.evolution_chart import EvolutionChart
from finance_tui.widgets.heatmap import SpendingHeatmap
from finance_tui.widgets.kpi_card import KpiCard


class OverviewPane(Container):
    """Overview tab: compact KPIs, charts, accounts, budgets."""

    def __init__(self, store, **kwargs):
        super().__init__(**kwargs)
        self.store = store

    def compose(self) -> ComposeResult:
        df = self.store.df
        period = analytics.fiscal_period()

        balance = analytics.global_balance(df)
        count = analytics.transaction_count(df)
        growth = analytics.net_growth_mom(df)
        last_date = analytics.last_transaction_date(df)

        with Horizontal(classes="kpi-row"):
            yield KpiCard(
                title="Balance",
                value=f"{balance:,.2f} {CURRENCY}",
                sentiment="positive" if balance >= 0 else "negative",
                id="kpi-balance",
            )
            yield KpiCard(
                title="MoM Growth",
                value=f"{growth:+,.2f} {CURRENCY}",
                sentiment="positive" if growth >= 0 else "negative",
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
            bud = BudgetPanel(df, self.store.categories, classes="third", id="panel-6")
            bud.border_title = "6·Months Over Budget"
            yield bud

        alerts = AlertsPanel(self.store, classes="alerts-row", id="panel-7")
        alerts.border_title = "7·Alerts"
        yield alerts

    def refresh_data(self, df: pd.DataFrame, period_label: str = ""):
        """Refresh all overview panels and KPIs with filtered data."""
        # KPIs
        balance = analytics.global_balance(df)
        growth = analytics.net_growth_mom(df)
        count = analytics.transaction_count(df)
        last_date = analytics.last_transaction_date(df)

        try:
            self.query_one("#kpi-balance", KpiCard).update_value(
                f"{balance:,.2f} {CURRENCY}",
                "positive" if balance >= 0 else "negative",
            )
            self.query_one("#kpi-growth", KpiCard).update_value(
                f"{growth:+,.2f} {CURRENCY}",
                "positive" if growth >= 0 else "negative",
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
            self.query_one("#panel-6", BudgetPanel).refresh_data(df)
            self.query_one("#panel-7", AlertsPanel).refresh_data(df)
        except Exception:
            pass
