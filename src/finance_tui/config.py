"""Paths, constants, and configuration."""

from pathlib import Path

OBSIDIAN_VAULT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/Personal"
FINANCE_DIR = OBSIDIAN_VAULT / "04_finance"
TRANSACTIONS_DIR = FINANCE_DIR / "Transactions"
CATEGORIES_DIR = FINANCE_DIR / "Categories"
ACCOUNTS_DIR = FINANCE_DIR / "Accounts"

CURRENCY = "€"
CURRENCY_CODE = "EUR"

CACHE_DIR = Path.home() / ".finance-tui"
