"""Transform mapped DataFrames into Transaction objects."""

import re
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from dateutil import parser as dateparser

from finance_tui import config as cfg
from finance_tui.importers.mapper import ColumnMapping
from finance_tui.models import Transaction
from finance_tui.parser import TRANSACTION_RE


def transform(
    df: pd.DataFrame,
    mapping: ColumnMapping,
    account: str,
    category: str = "Other",
    transactions_dir: Path | None = None,
) -> list[Transaction]:
    """Convert a mapped DataFrame into Transaction objects."""
    transactions_dir = transactions_dir or cfg.TRANSACTIONS_DIR
    start_id = _next_id(transactions_dir)
    transactions = []
    for i, (_, row) in enumerate(df.iterrows()):
        txn_date = _parse_date(row[mapping.date_col])
        amount = _normalize_amount(row, mapping)
        description = str(row[mapping.description_col]).strip()
        transactions.append(Transaction(
            id=start_id + i,
            date=txn_date,
            amount=amount,
            category=category,
            description=description,
            account=account,
            validated=False,
            source_file=f"{txn_date.year}.md",
            line_number=0,
            raw_line="",
        ))
    return transactions


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    s = str(value).strip()
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        pass
    return dateparser.parse(s, dayfirst=True).date()


def _normalize_amount(row: pd.Series, mapping: ColumnMapping) -> float:
    if mapping.is_split:
        debit = _to_float(row[mapping.debit_col])
        credit = _to_float(row[mapping.credit_col])
        return round(credit - abs(debit), 2)
    return round(_to_float(row[mapping.amount_col]), 2)


def _to_float(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    # European format: 1.234,56 → dots are thousands, comma is decimal
    if "," in s and "." in s and s.rfind(",") > s.rfind("."):
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    s = re.sub(r"[^\d.\-+]", "", s)
    return float(s) if s else 0.0


def _next_id(transactions_dir: Path) -> int:
    max_id = 0
    if not transactions_dir.exists():
        return 1
    for path in transactions_dir.glob("*.md"):
        for line in path.read_text(encoding="utf-8").splitlines():
            m = TRANSACTION_RE.match(line)
            if m:
                max_id = max(max_id, int(m.group(7)))
    return max_id + 1


def detect_duplicates(
    new_txns: list[Transaction],
    existing_df: pd.DataFrame,
    similarity: float = 0.8,
) -> list[dict]:
    """Flag new transactions that look like duplicates of existing ones."""
    if existing_df.empty:
        return []

    dupes = []
    for txn in new_txns:
        mask = (
            (existing_df["date"].dt.date == txn.date)
            & (existing_df["amount"] == txn.amount)
        )
        candidates = existing_df[mask]
        for _, row in candidates.iterrows():
            ratio = SequenceMatcher(None, txn.description, row["description"]).ratio()
            if ratio >= similarity:
                dupes.append({
                    "new": txn,
                    "existing_id": row["id"],
                    "existing_desc": row["description"],
                    "similarity": round(ratio, 2),
                })
                break
    return dupes
