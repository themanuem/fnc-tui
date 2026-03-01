"""Command palette providers."""

from textual.command import DiscoveryHit, Hit, Hits, Provider


class FinanceCommandProvider(Provider):
    """Custom command palette provider with discovery and prefix drill-down."""

    async def discover(self) -> Hits:
        """Default suggestions shown before the user types anything."""
        app = self.app
        # Prefix drill-down items (intercepted by FinanceCommandPalette._select_command)
        _noop = lambda: None
        yield DiscoveryHit("Search", _noop, help="Free text search across transactions")
        yield DiscoveryHit("Category", _noop, help="Filter transactions by category")
        yield DiscoveryHit("Account", _noop, help="Filter transactions by account")
        yield DiscoveryHit("Period", _noop, help="Change the active time period")
        # Direct actions
        yield DiscoveryHit(
            "Clear Filters",
            lambda: app.action_clear_filters(),
            help="Remove all active filters",
        )

    async def search(self, query: str) -> Hits:
        app = self.app
        q = query.strip().lower()

        # ── Prefix drill-down: cat: ────────────────────────
        if q.startswith("cat:"):
            fragment = q[4:]
            try:
                categories = list(app.store.categories.keys())
            except Exception:
                categories = []
            for cat in categories:
                if fragment in cat.lower():
                    yield Hit(
                        1.0 - (len(fragment) / max(len(cat), 1)),
                        f"cat:{cat}",
                        lambda c=cat: app.apply_search_filter(f"cat:{c}"),
                        help=f"Show only {cat} transactions",
                    )
            return

        # ── Prefix drill-down: acc: ────────────────────────
        if q.startswith("acc:"):
            fragment = q[4:]
            try:
                accounts = list(app.store.accounts.keys())
            except Exception:
                accounts = []
            for acc in accounts:
                if fragment in acc.lower():
                    yield Hit(
                        1.0 - (len(fragment) / max(len(acc), 1)),
                        f"acc:{acc}",
                        lambda a=acc: app.apply_search_filter(f"acc:{a}"),
                        help=f"Show only {acc} transactions",
                    )
            return

        # ── Prefix drill-down: period: ─────────────────────
        if q.startswith("period:"):
            periods = [
                ("All Time", "set_period_all"),
                ("This Year", "set_period_year"),
                ("This Month", "set_period_month"),
            ]
            fragment = q[7:]
            for label, action in periods:
                if fragment in label.lower():
                    yield Hit(
                        1.0,
                        f"period:{label}",
                        lambda a=action: app.action_custom(a),
                        help=f"Set period to {label}",
                    )
            return

        # ── General search ─────────────────────────────────
        commands = [
            ("Go to Overview", "switch_tab('overview')", "View KPIs and charts"),
            ("Go to Transactions", "switch_tab('transactions')", "View all transactions"),
            ("Period: All Time", "set_period_all", "Show all time data"),
            ("Period: This Year", "set_period_year", "Show current year"),
            ("Period: This Month", "set_period_month", "Show current month"),
            ("Clear Filters", "clear_filter", "Remove all filters"),
            ("Reload Data", "reload_data", "Reload from disk"),
            ("Quit", "quit", "Exit the application"),
        ]

        for name, action, help_text in commands:
            if q in name.lower():
                yield Hit(
                    1.0 - (len(q) / len(name)),
                    name,
                    lambda a=action: app.action_custom(a),
                    help=help_text,
                )

        # Raw query as a transaction filter
        if q:
            yield Hit(
                0.5,
                f"Search transactions: {query.strip()}",
                lambda fq=query.strip(): app.apply_search_filter(fq),
                help="cat:X  acc:X  person:X  >N  <N  or free text",
            )
