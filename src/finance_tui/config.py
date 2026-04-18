"""Paths, constants, and configuration."""

import json
import os
from pathlib import Path

CACHE_DIR = Path.home() / ".finance-tui"
_CONFIG_FILE = CACHE_DIR / "config.json"

CURRENCY = "€"
CURRENCY_CODE = "EUR"

FINANCE_DIR: Path | None = None
TRANSACTIONS_DIR: Path | None = None
CATEGORIES_DIR: Path | None = None
ACCOUNTS_DIR: Path | None = None


def _derive_dirs() -> None:
    global TRANSACTIONS_DIR, CATEGORIES_DIR, ACCOUNTS_DIR
    TRANSACTIONS_DIR = FINANCE_DIR / "Transactions"
    CATEGORIES_DIR = FINANCE_DIR / "Categories"
    ACCOUNTS_DIR = FINANCE_DIR / "Accounts"


def set_finance_dir(path: Path | str) -> None:
    """Set the finance directory and derive subdirectories."""
    global FINANCE_DIR
    FINANCE_DIR = Path(path).expanduser().resolve()
    _derive_dirs()


def save_finance_dir(path: Path | str) -> None:
    """Set the finance directory and persist it to disk."""
    set_finance_dir(path)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps({"finance_dir": str(FINANCE_DIR)}))


def load_config() -> None:
    """Load saved config from disk, falling back to FNC_FINANCE_DIR env var."""
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text())
            if "finance_dir" in data:
                set_finance_dir(data["finance_dir"])
                return
        except (json.JSONDecodeError, KeyError):
            pass
    env = os.environ.get("FNC_FINANCE_DIR")
    if env:
        set_finance_dir(env)


def is_configured() -> bool:
    """True if FINANCE_DIR is set and exists with the expected subdirectories."""
    return (
        FINANCE_DIR is not None
        and FINANCE_DIR.exists()
        and (FINANCE_DIR / "Transactions").exists()
        and (FINANCE_DIR / "Categories").exists()
        and (FINANCE_DIR / "Accounts").exists()
    )


load_config()
