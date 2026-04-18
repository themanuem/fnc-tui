"""Autodetect column mapping using an LLM."""

import hashlib
import json
from dataclasses import dataclass

import pandas as pd

from finance_tui.ai.cache import cache_get, cache_set
from finance_tui.importers.llm import Provider, llm_complete

SYSTEM_PROMPT = """You are a data-mapping assistant. You identify columns in financial data.
Respond with JSON only — no explanation, no markdown fences."""

USER_PROMPT = """\
Given these spreadsheet columns and sample data, identify which columns contain:
1. Transaction date
2. Transaction description or name
3. Transaction amount

If the amount is split into separate debit and credit columns, identify both instead of a single amount column.

Columns: {columns}

Sample rows:
{samples}

Respond with JSON only. Use one of these two formats:
{{"date": "column_name", "description": "column_name", "amount": "column_name"}}
or if split into debit/credit:
{{"date": "column_name", "description": "column_name", "debit": "column_name", "credit": "column_name"}}"""


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


def detect_columns(
    df: pd.DataFrame,
    provider: Provider = Provider.OLLAMA,
    model: str | None = None,
) -> ColumnMapping:
    """Use an LLM to detect which columns map to date, description, and amount."""
    columns = list(df.columns)
    cache_key = "map:" + hashlib.md5(
        ",".join(sorted(columns)).encode()
    ).hexdigest()
    cached = cache_get(cache_key)
    if cached:
        mapping = _parse_mapping(cached)
        mapping.validate()
        return mapping

    samples = df.head(5).to_string(index=False)
    prompt = USER_PROMPT.format(columns=columns, samples=samples)

    response = llm_complete(prompt, system=SYSTEM_PROMPT, provider=provider, model=model)
    parsed = _extract_json(response)
    mapping = _parse_mapping(parsed)
    mapping.validate()

    cache_set(cache_key, parsed)
    return mapping


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError(f"No JSON object found in LLM response: {text[:200]}")
    return json.loads(text[start:end])


def _parse_mapping(data: dict) -> ColumnMapping:
    return ColumnMapping(
        date_col=data["date"],
        description_col=data["description"],
        amount_col=data.get("amount"),
        debit_col=data.get("debit"),
        credit_col=data.get("credit"),
    )
