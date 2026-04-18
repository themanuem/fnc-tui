"""Tests for category CRUD writer functions."""

from pathlib import Path

import pytest

from finance_tui.parser import parse_category_file, parse_transaction
from finance_tui.writer import (
    delete_category_file,
    rename_category_everywhere,
    write_category_file,
)


@pytest.fixture
def categories_dir(tmp_path):
    d = tmp_path / "categories"
    d.mkdir()
    return d


@pytest.fixture
def transactions_dir(tmp_path):
    d = tmp_path / "transactions"
    d.mkdir()
    return d


class TestWriteCategoryFile:
    def test_creates_file(self, categories_dir):
        path = write_category_file("Food", 500.0, False, categories_dir)
        assert path.exists()
        assert path.name == "Food.md"

    def test_writes_budget(self, categories_dir):
        write_category_file("Food", 500.0, False, categories_dir)
        cat = parse_category_file(categories_dir / "Food.md")
        assert cat.budget == 500.0
        assert cat.name == "Food"

    def test_writes_track(self, categories_dir):
        write_category_file("Misc", 0.0, True, categories_dir)
        cat = parse_category_file(categories_dir / "Misc.md")
        assert cat.track is True
        assert cat.budget == 0.0

    def test_no_budget_no_track(self, categories_dir):
        write_category_file("Other", 0.0, False, categories_dir)
        cat = parse_category_file(categories_dir / "Other.md")
        assert cat.budget == 0.0
        assert cat.track is False

    def test_overwrites_existing(self, categories_dir):
        write_category_file("Food", 500.0, False, categories_dir)
        write_category_file("Food", 750.0, True, categories_dir)
        cat = parse_category_file(categories_dir / "Food.md")
        assert cat.budget == 750.0
        assert cat.track is True


class TestDeleteCategoryFile:
    def test_deletes_existing(self, categories_dir):
        write_category_file("Food", 500.0, False, categories_dir)
        assert (categories_dir / "Food.md").exists()
        delete_category_file("Food", categories_dir)
        assert not (categories_dir / "Food.md").exists()

    def test_noop_on_missing(self, categories_dir):
        delete_category_file("Nonexistent", categories_dir)


class TestRenameCategoryEverywhere:
    def test_renames_category_file(self, categories_dir, transactions_dir):
        write_category_file("Food", 500.0, False, categories_dir)
        rename_category_everywhere("Food", "Groceries", categories_dir, transactions_dir)
        assert not (categories_dir / "Food.md").exists()
        assert (categories_dir / "Groceries.md").exists()
        cat = parse_category_file(categories_dir / "Groceries.md")
        assert cat.budget == 500.0

    def test_updates_transaction_files(self, categories_dir, transactions_dir):
        write_category_file("Food", 500.0, False, categories_dir)
        txn_file = transactions_dir / "2026.md"
        txn_file.write_text(
            "---\n---\n"
            "- [ ] `-45.20` [[Food]] Groceries ➕ 2026-01-15 [[Test_01]] 🆔 1\n"
            "- [ ] `-12.99` [[Food]] Restaurant ➕ 2026-01-16 [[Test_01]] 🆔 2\n"
            "- [ ] `2100.00` [[Sales]] Salary ➕ 2026-01-17 [[Test_01]] 🆔 3\n"
        )
        modified = rename_category_everywhere("Food", "Groceries", categories_dir, transactions_dir)
        assert txn_file in modified

        content = txn_file.read_text()
        assert "[[Groceries]]" in content
        assert "[[Food]]" not in content
        assert "[[Sales]]" in content

        for i, line in enumerate(content.splitlines(), 1):
            txn = parse_transaction(line, "2026.md", i)
            if txn and txn.id in (1, 2):
                assert txn.category == "Groceries"
            if txn and txn.id == 3:
                assert txn.category == "Sales"

    def test_returns_modified_paths(self, categories_dir, transactions_dir):
        write_category_file("Food", 100.0, False, categories_dir)
        (transactions_dir / "2025.md").write_text(
            "---\n---\n- [ ] `-10.00` [[Food]] A ➕ 2025-01-01 [[T_01]] 🆔 1\n"
        )
        (transactions_dir / "2026.md").write_text(
            "---\n---\n- [ ] `-20.00` [[Other]] B ➕ 2026-01-01 [[T_01]] 🆔 2\n"
        )
        modified = rename_category_everywhere("Food", "Meal", categories_dir, transactions_dir)
        paths = [p.name for p in modified]
        assert "Meal.md" in paths
        assert "2025.md" in paths
        assert "2026.md" not in paths
