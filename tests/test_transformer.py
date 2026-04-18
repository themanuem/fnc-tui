"""Tests for import transformer and bulk writer."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from finance_tui.importers.mapper import ColumnMapping
from finance_tui.importers.transformer import (
    _next_id,
    _normalize_amount,
    _parse_date,
    detect_duplicates,
    transform,
)
from finance_tui.parser import parse_transaction
from finance_tui.writer import bulk_prepend_transactions, serialize_transaction


@pytest.fixture
def single_amount_mapping():
    return ColumnMapping(date_col="Date", description_col="Desc", amount_col="Amount")


@pytest.fixture
def split_mapping():
    return ColumnMapping(date_col="Date", description_col="Desc", debit_col="Debit", credit_col="Credit")


class TestParseDate:
    def test_iso_format(self):
        assert _parse_date("2026-01-15") == date(2026, 1, 15)

    def test_european_format(self):
        assert _parse_date("15/01/2026") == date(2026, 1, 15)

    def test_date_object_passthrough(self):
        d = date(2026, 3, 1)
        assert _parse_date(d) is d

    def test_verbose_format(self):
        assert _parse_date("15-Jan-2026") == date(2026, 1, 15)


class TestNormalizeAmount:
    def test_single_column(self, single_amount_mapping):
        row = pd.Series({"Date": "2026-01-15", "Desc": "Test", "Amount": -45.20})
        assert _normalize_amount(row, single_amount_mapping) == -45.20

    def test_split_columns_debit(self, split_mapping):
        row = pd.Series({"Date": "2026-01-15", "Desc": "Test", "Debit": 45.20, "Credit": 0.0})
        assert _normalize_amount(row, split_mapping) == -45.20

    def test_split_columns_credit(self, split_mapping):
        row = pd.Series({"Date": "2026-01-15", "Desc": "Test", "Debit": 0.0, "Credit": 2100.00})
        assert _normalize_amount(row, split_mapping) == 2100.00

    def test_string_amount_with_comma(self, single_amount_mapping):
        row = pd.Series({"Date": "2026-01-15", "Desc": "Test", "Amount": "1.234,56"})
        assert _normalize_amount(row, single_amount_mapping) == 1234.56


class TestTransform:
    def test_basic_transform(self, tmp_path, single_amount_mapping):
        df = pd.DataFrame({
            "Date": ["2026-01-15", "2026-01-16"],
            "Desc": ["Groceries", "Salary"],
            "Amount": [-45.20, 2100.00],
        })
        txns = transform(df, single_amount_mapping, "Test_01", transactions_dir=tmp_path)
        assert len(txns) == 2
        assert txns[0].date == date(2026, 1, 15)
        assert txns[0].description == "Groceries"
        assert txns[0].amount == -45.20
        assert txns[0].account == "Test_01"
        assert txns[0].category == "Other"
        assert not txns[0].validated

    def test_ids_are_sequential(self, tmp_path, single_amount_mapping):
        df = pd.DataFrame({
            "Date": ["2026-01-15", "2026-01-16", "2026-01-17"],
            "Desc": ["A", "B", "C"],
            "Amount": [-10, -20, -30],
        })
        txns = transform(df, single_amount_mapping, "Test_01", transactions_dir=tmp_path)
        assert txns[0].id == 1
        assert txns[1].id == 2
        assert txns[2].id == 3

    def test_ids_dont_collide_with_existing(self, tmp_path, single_amount_mapping):
        existing = "---\n---\n- [ ] `-10.00` [[Other]] Old txn ➕ 2025-12-01 [[Test_01]] 🆔 50\n"
        (tmp_path / "2025.md").write_text(existing)
        df = pd.DataFrame({"Date": ["2026-01-15"], "Desc": ["New"], "Amount": [-5.0]})
        txns = transform(df, single_amount_mapping, "Test_01", transactions_dir=tmp_path)
        assert txns[0].id == 51

    def test_split_amounts(self, tmp_path, split_mapping):
        df = pd.DataFrame({
            "Date": ["2026-01-15"],
            "Desc": ["Purchase"],
            "Debit": [99.99],
            "Credit": [0.0],
        })
        txns = transform(df, split_mapping, "Test_01", transactions_dir=tmp_path)
        assert txns[0].amount == -99.99


class TestNextId:
    def test_empty_dir(self, tmp_path):
        assert _next_id(tmp_path) == 1

    def test_nonexistent_dir(self, tmp_path):
        assert _next_id(tmp_path / "nope") == 1

    def test_finds_max(self, tmp_path):
        content = (
            "---\n---\n"
            "- [ ] `-10.00` [[Food]] A ➕ 2026-01-01 [[T_01]] 🆔 5\n"
            "- [ ] `-20.00` [[Food]] B ➕ 2026-01-02 [[T_01]] 🆔 100\n"
        )
        (tmp_path / "2026.md").write_text(content)
        assert _next_id(tmp_path) == 101


class TestDetectDuplicates:
    def test_finds_duplicate(self):
        txn = type("T", (), {"date": date(2026, 1, 15), "amount": -45.20, "description": "Mercadona groceries"})()
        existing = pd.DataFrame({
            "date": pd.to_datetime(["2026-01-15"]),
            "amount": [-45.20],
            "description": ["Mercadona groceries"],
            "id": [1],
        })
        dupes = detect_duplicates([txn], existing)
        assert len(dupes) == 1
        assert dupes[0]["similarity"] >= 0.8

    def test_no_false_positives(self):
        txn = type("T", (), {"date": date(2026, 1, 15), "amount": -45.20, "description": "Mercadona"})()
        existing = pd.DataFrame({
            "date": pd.to_datetime(["2026-02-15"]),
            "amount": [-45.20],
            "description": ["Mercadona"],
            "id": [1],
        })
        dupes = detect_duplicates([txn], existing)
        assert len(dupes) == 0

    def test_empty_existing(self):
        txn = type("T", (), {"date": date(2026, 1, 15), "amount": -10, "description": "X"})()
        dupes = detect_duplicates([txn], pd.DataFrame())
        assert dupes == []


class TestBulkPrepend:
    def test_creates_new_files(self, tmp_path):
        lines = [
            (2026, "- [ ] `-10.00` [[Food]] A ➕ 2026-01-01 [[T_01]] 🆔 1"),
            (2026, "- [ ] `-20.00` [[Food]] B ➕ 2026-01-02 [[T_01]] 🆔 2"),
        ]
        result = bulk_prepend_transactions(lines, tmp_path)
        assert 2026 in result
        content = result[2026].read_text()
        assert "🆔 1" in content
        assert "🆔 2" in content
        assert content.startswith("---\n---\n")

    def test_prepends_to_existing(self, tmp_path):
        existing = "---\n---\n- [ ] `-5.00` [[Food]] Old ➕ 2026-01-01 [[T_01]] 🆔 99\n"
        (tmp_path / "2026.md").write_text(existing)
        lines = [(2026, "- [ ] `-10.00` [[Food]] New ➕ 2026-01-15 [[T_01]] 🆔 100")]
        bulk_prepend_transactions(lines, tmp_path)
        content = (tmp_path / "2026.md").read_text()
        new_pos = content.index("🆔 100")
        old_pos = content.index("🆔 99")
        assert new_pos < old_pos

    def test_groups_by_year(self, tmp_path):
        lines = [
            (2025, "- [ ] `-10.00` [[Food]] A ➕ 2025-12-01 [[T_01]] 🆔 1"),
            (2026, "- [ ] `-20.00` [[Food]] B ➕ 2026-01-01 [[T_01]] 🆔 2"),
        ]
        result = bulk_prepend_transactions(lines, tmp_path)
        assert 2025 in result
        assert 2026 in result
        assert (tmp_path / "2025.md").exists()
        assert (tmp_path / "2026.md").exists()


class TestRoundTrip:
    def test_transform_write_parse(self, tmp_path, single_amount_mapping):
        """Full round-trip: transform → serialize → write → parse → compare."""
        df = pd.DataFrame({
            "Date": ["2026-03-15", "2026-03-16"],
            "Desc": ["Supermarket", "Salary"],
            "Amount": [-78.50, 2100.00],
        })
        txns = transform(df, single_amount_mapping, "BBVA_01", transactions_dir=tmp_path)

        lines = []
        for t in txns:
            serialized = serialize_transaction(
                t.validated, t.amount, t.category, t.description,
                t.date.isoformat(), t.account, t.id,
            )
            lines.append((t.date.year, serialized))

        bulk_prepend_transactions(lines, tmp_path)

        content = (tmp_path / "2026.md").read_text()
        parsed = []
        for i, line in enumerate(content.splitlines(), start=1):
            p = parse_transaction(line, "2026.md", i)
            if p:
                parsed.append(p)

        assert len(parsed) == 2
        for orig, back in zip(txns, parsed):
            assert back.date == orig.date
            assert back.amount == orig.amount
            assert back.description == orig.description
            assert back.account == orig.account
            assert back.id == orig.id
            assert back.category == orig.category
