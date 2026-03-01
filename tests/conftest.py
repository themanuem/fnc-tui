"""Shared test fixtures."""

import pytest

from finance_tui.config import ACCOUNTS_DIR, CATEGORIES_DIR, TRANSACTIONS_DIR
from finance_tui.store import FinanceStore


@pytest.fixture(scope="session")
def store():
    """Load the real finance store once for all tests."""
    return FinanceStore()


@pytest.fixture(scope="session")
def transactions_dir():
    return TRANSACTIONS_DIR


@pytest.fixture(scope="session")
def categories_dir():
    return CATEGORIES_DIR


@pytest.fixture(scope="session")
def accounts_dir():
    return ACCOUNTS_DIR
