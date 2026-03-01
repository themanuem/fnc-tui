"""Tests for analytics functions."""

from finance_tui import analytics


class TestAnalytics:
    """Test analytics against real data."""

    def test_global_balance(self, store):
        balance = analytics.global_balance(store.df)
        assert abs(balance - 19146.35) < 0.01

    def test_transaction_count(self, store):
        assert analytics.transaction_count(store.df) == 1752

    def test_last_transaction_date(self, store):
        last = analytics.last_transaction_date(store.df)
        assert last is not None
        assert last.year >= 2026

    def test_fiscal_period(self):
        period = analytics.fiscal_period()
        assert len(period) == 7  # YYYY-MM format
        assert "-" in period

    def test_income_by_category(self, store):
        income = analytics.income_by_category(store.df)
        assert "Sales" in income
        assert income["Sales"] > 0

    def test_expenses_by_category(self, store):
        expenses = analytics.expenses_by_category(store.df)
        assert "Food" in expenses
        assert expenses["Food"] < 0

    def test_balance_by_account(self, store):
        balances = analytics.balance_by_account(store.df)
        assert len(balances) >= 2
        # Total should equal global balance
        total = sum(balances.values())
        assert abs(total - 19146.35) < 0.01

    def test_monthly_totals(self, store):
        mt = analytics.monthly_totals(store.df)
        assert not mt.empty
        assert "month" in mt.columns
        assert "total" in mt.columns

    def test_category_spend_vs_budget(self, store):
        results = analytics.category_spend_vs_budget(
            store.df, store.categories, month="2026-02"
        )
        assert len(results) > 0
        food = next((r for r in results if r["category"] == "Food"), None)
        assert food is not None
        assert food["budget"] == -200
