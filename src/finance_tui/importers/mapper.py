"""Autodetect column mapping using heuristics."""

import re
from dataclasses import dataclass

import pandas as pd


@dataclass
class ColumnMapping:
    date_col: str
    description_col: str
    amount_col: str | None = None
    debit_col: str | None = None
    credit_col: str | None = None

    def validate(self) -> None:
        has_single = self.amount_col is not None
        has_split = self.debit_col is not None and self.credit_col is not None
        if not (has_single or has_split):
            raise ValueError(
                "Mapping must have either 'amount' or both 'debit' and 'credit' columns"
            )

    @property
    def is_split(self) -> bool:
        return self.debit_col is not None and self.credit_col is not None


# Patterns ordered by priority — first match wins.
# Completion/settlement dates are listed before start dates so they win.
_DATE_PATTERNS = [
    r"complet\w*\s*date", r"settle\w*\s*date", r"post\w*\s*date",
    r"value\s*date", r"booking\s*date", r"transaction\s*date",
    r"\bdate\b", r"\bfecha\b", r"\bdatum\b",
]
_DESC_PATTERNS = [
    r"\bdescription\b", r"\bnarration\b", r"\bmemo\b",
    r"\bpayee\b", r"\bname\b", r"\bdetails?\b", r"\breference\b",
    r"\bconcept[eo]?\b",
]
_AMOUNT_PATTERNS = [
    r"\bamount\b", r"\bsum\b", r"\btotal\b", r"\bvalue\b",
    r"\bimporte?\b", r"\bbetrag\b",
]
_DEBIT_PATTERNS = [
    r"\bdebit\b", r"\bwithdrawal\b", r"\bcharge\b", r"\bout\b",
]
_CREDIT_PATTERNS = [
    r"\bcredit\b", r"\bdeposit\b", r"\bin\b(?!dex|put|voice)",
]


def _match_column(columns: list[str], patterns: list[str]) -> str | None:
    lower = {c: c.lower().strip() for c in columns}
    for pattern in patterns:
        for col, low in lower.items():
            if re.search(pattern, low):
                return col
    return None


def detect_columns(df: pd.DataFrame) -> ColumnMapping:
    """Detect column mapping using name-based heuristics."""
    columns = list(df.columns)

    date_col = _match_column(columns, _DATE_PATTERNS)
    desc_col = _match_column(columns, _DESC_PATTERNS)
    amount_col = _match_column(columns, _AMOUNT_PATTERNS)
    debit_col = _match_column(columns, _DEBIT_PATTERNS)
    credit_col = _match_column(columns, _CREDIT_PATTERNS)

    if not date_col:
        for col in columns:
            try:
                pd.to_datetime(df[col].head(5))
                date_col = col
                break
            except Exception:
                continue

    if not date_col:
        raise ValueError(f"Could not detect a date column in: {columns}")
    if not desc_col:
        raise ValueError(f"Could not detect a description column in: {columns}")

    has_split = debit_col and credit_col
    if not amount_col and not has_split:
        raise ValueError(f"Could not detect an amount column in: {columns}")

    return ColumnMapping(
        date_col=date_col,
        description_col=desc_col,
        amount_col=amount_col if not has_split else None,
        debit_col=debit_col if has_split else None,
        credit_col=credit_col if has_split else None,
    )
