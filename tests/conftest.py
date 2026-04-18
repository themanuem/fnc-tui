"""Shared test fixtures."""

import pytest

from finance_tui.config import ACCOUNTS_DIR, CATEGORIES_DIR, FINANCE_DIR, TRANSACTIONS_DIR
from finance_tui.store import FinanceStore

_needs_vault = pytest.mark.skipif(
    FINANCE_DIR is None or not FINANCE_DIR.exists(),
    reason="FNC_FINANCE_DIR not set or directory missing",
)


@pytest.fixture(scope="session")
def store():
    """Load the real finance store once for all tests."""
    if FINANCE_DIR is None or not FINANCE_DIR.exists():
        pytest.skip("FNC_FINANCE_DIR not set or directory missing")
    return FinanceStore()


@pytest.fixture(scope="session")
def transactions_dir():
    if TRANSACTIONS_DIR is None:
        pytest.skip("FNC_FINANCE_DIR not set")
    return TRANSACTIONS_DIR


@pytest.fixture(scope="session")
def categories_dir():
    if CATEGORIES_DIR is None:
        pytest.skip("FNC_FINANCE_DIR not set")
    return CATEGORIES_DIR


@pytest.fixture(scope="session")
def accounts_dir():
    if ACCOUNTS_DIR is None:
        pytest.skip("FNC_FINANCE_DIR not set")
    return ACCOUNTS_DIR
