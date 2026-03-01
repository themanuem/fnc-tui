"""Search bar with prefix-based filter syntax."""

import re

from textual import on
from textual.message import Message
from textual.widgets import Input

import pandas as pd


def tokenize_query(query: str) -> list[str]:
    """Split query into tokens, keeping person:First Last as one token."""
    tokens = []
    remainder = query.strip()
    while remainder:
        # Match prefix tokens that may contain spaces (person:)
        m = re.match(r"(person:\S+(?:\s+\S+)*?)(?=\s+(?:cat:|acc:|person:|[><]\d)|$)", remainder)
        if m:
            tokens.append(m.group(1))
            remainder = remainder[m.end():].lstrip()
            continue
        # Match other prefix tokens or operators
        m = re.match(r"((?:cat|acc):\S+|[><]-?\d+\.?\d*|\S+)", remainder)
        if m:
            tokens.append(m.group(1))
            remainder = remainder[m.end():].lstrip()
            continue
        break
    return tokens


def build_filter_mask(df: pd.DataFrame, query: str) -> pd.Series:
    """Build a boolean mask from a compound filter query string.

    Supported tokens:
        cat:Food       - filter by category
        acc:Revolut_01 - filter by account
        person:Mom     - filter by person mentioned
        >100           - amount greater than
        <-50           - amount less than
        Free text      - search description
    """
    mask = pd.Series(True, index=df.index)
    tokens = tokenize_query(query)
    if not tokens:
        return mask

    for token in tokens:
        m = re.match(r"cat:(.+)", token, re.IGNORECASE)
        if m:
            mask = mask & (df["category"].str.lower() == m.group(1).lower())
            continue

        m = re.match(r"acc:(.+)", token, re.IGNORECASE)
        if m:
            mask = mask & df["account"].str.lower().str.contains(m.group(1).lower(), na=False)
            continue

        m = re.match(r"person:(.+)", token, re.IGNORECASE)
        if m:
            person = m.group(1).strip().lower()
            mask = mask & df["people"].apply(
                lambda ps, p=person: any(p in x.lower() for x in ps)
            )
            continue

        m = re.match(r">(-?\d+\.?\d*)", token)
        if m:
            mask = mask & (df["amount"] > float(m.group(1)))
            continue

        m = re.match(r"<(-?\d+\.?\d*)", token)
        if m:
            mask = mask & (df["amount"] < float(m.group(1)))
            continue

        # Free text: description search
        mask = mask & df["description"].str.contains(token, case=False, na=False)

    return mask


class SearchBar(Input):
    """Search input with prefix filter syntax."""

    class FilterChanged(Message):
        """Emitted when the filter changes."""

        def __init__(self, mask: pd.Series | None):
            super().__init__()
            self.mask = mask

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(
            placeholder="Search: cat:Food  acc:Revolut_01  person:Mom  >100  <-50  or free text...",
            **kwargs,
        )
        self._df = df

    def update_df(self, df: pd.DataFrame):
        self._df = df

    @on(Input.Changed)
    def _on_change(self, event: Input.Changed):
        query = event.value.strip()
        if not query:
            self.post_message(self.FilterChanged(None))
            return
        self.post_message(self.FilterChanged(build_filter_mask(self._df, query)))
