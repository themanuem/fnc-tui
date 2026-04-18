"""Data store - loads parsed data into pandas DataFrames."""

from pathlib import Path

import pandas as pd

from finance_tui import config as cfg
from finance_tui.parser import parse_all_accounts, parse_all_categories, parse_all_transactions


class FinanceStore:
    """Central data store backed by pandas DataFrames."""

    def __init__(
        self,
        transactions_dir: Path | None = None,
        categories_dir: Path | None = None,
        accounts_dir: Path | None = None,
    ):
        self.transactions_dir = transactions_dir or cfg.TRANSACTIONS_DIR
        self.categories_dir = categories_dir or cfg.CATEGORIES_DIR
        self.accounts_dir = accounts_dir or cfg.ACCOUNTS_DIR
        self.df = pd.DataFrame()
        self.categories: dict[str, dict] = {}
        self.accounts: dict[str, dict] = {}
        self.load()

    def load(self):
        """Load all data from disk."""
        self._load_categories()
        self._load_accounts()
        self._load_transactions()

    def _load_categories(self):
        cats = parse_all_categories(self.categories_dir)
        self.categories = {c.name: {"budget": c.budget, "track": c.track} for c in cats}

    def _load_accounts(self):
        accs = parse_all_accounts(self.accounts_dir)
        self.accounts = {a.name: {"aliases": a.aliases} for a in accs}

    def _load_transactions(self):
        txns = parse_all_transactions(self.transactions_dir)
        if not txns:
            self.df = pd.DataFrame()
            return

        records = []
        for t in txns:
            records.append({
                "id": t.id,
                "date": t.date,
                "amount": t.amount,
                "category": t.category,
                "description": t.description,
                "account": t.account,
                "validated": t.validated,
                "source_file": t.source_file,
                "line_number": t.line_number,
                "raw_line": t.raw_line,
                "people": t.people,
                "tags": t.tags,
                "links": t.links,
            })

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        # Derived columns
        df["is_expense"] = df["amount"] < 0
        df["is_income"] = df["amount"] > 0
        df["month"] = df["date"].dt.to_period("M").astype(str)

        # Running sum (cumulative balance over time)
        df["running_sum"] = df["amount"].cumsum().round(2)

        # Day-end total (cumulative sum at the end of each day)
        df["day_end_total"] = (
            df.groupby(df["date"].dt.date)["amount"]
            .transform("sum")
            .groupby(df["date"].dt.date)
            .cumsum()
        )
        # Actually, day_end_total should be the running_sum at the last transaction of each day
        # Simpler: just use running_sum, group by date, take the last value and forward-fill
        day_totals = df.groupby(df["date"].dt.date)["running_sum"].transform("last")
        df["day_end_total"] = day_totals

        self.df = df

    def reload_file(self, file_path: Path):
        """Reload a single transaction file (for live watching)."""
        # For now, just reload everything
        self._load_transactions()

    @property
    def transaction_count(self) -> int:
        return len(self.df)

    @property
    def global_balance(self) -> float:
        if self.df.empty:
            return 0.0
        return round(self.df["amount"].sum(), 2)
