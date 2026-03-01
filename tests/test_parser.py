"""Tests for the markdown parser."""

from datetime import date

import pytest

from finance_tui.parser import (
    _extract_people,
    parse_all_accounts,
    parse_all_categories,
    parse_all_transactions,
    parse_transaction,
)


class TestParseTransaction:
    """Test individual transaction line parsing."""

    def test_basic_expense(self):
        line = "- [ ] `-9.61` [[Wellbeing]] Farmacia Bco Grande ➕ 2021-12-28 [[Revolut_01]] 🆔 3215"
        txn = parse_transaction(line, "2021.md", 6)
        assert txn is not None
        assert txn.id == 3215
        assert txn.amount == -9.61
        assert txn.category == "Wellbeing"
        assert txn.description == "Farmacia Bco Grande"
        assert txn.date == date(2021, 12, 28)
        assert txn.account == "Revolut_01"
        assert txn.validated is False
        assert txn.is_expense is True
        assert txn.is_income is False

    def test_basic_income(self):
        line = "- [ ] `2782.11` [[Sales]] Payment from CELONIS SL ➕ 2026-02-25 [[Revolut_01]] 🆔 4307"
        txn = parse_transaction(line, "2026.md", 11)
        assert txn is not None
        assert txn.amount == 2782.11
        assert txn.category == "Sales"
        assert txn.is_income is True
        assert txn.is_expense is False

    def test_caixabank_account(self):
        line = "- [ ] `-45.00` [[Subscriptions]] CENTRO CULTUR. ➕ 2026-02-17 [[CaixaBank_01]] 🆔 4315"
        txn = parse_transaction(line, "2026.md", 33)
        assert txn is not None
        assert txn.account == "CaixaBank_01"

    def test_bizum_incoming_name(self):
        line = "- [ ] `30.00` [[Other]] Bizum < Ivan C.L. ➕ 2026-02-15 [[Revolut_01]] 🆔 4276"
        txn = parse_transaction(line, "2026.md", 43)
        assert txn is not None
        assert txn.description == "Bizum < Ivan C.L."
        assert "Ivan C.L." in txn.people

    def test_bizum_incoming_phone(self):
        line = "- [ ] `6.00` [[Other]] Bizum < +34633810716 ➕ 2026-02-11 [[Revolut_01]] 🆔 4263"
        txn = parse_transaction(line, "2026.md", 56)
        assert txn is not None
        assert txn.people == []  # Phone numbers are not people

    def test_bizum_outgoing_wikilink(self):
        line = "- [ ] `-25.85` [[Other]] Bizum > [[Andres]] ➕ 2026-02-07 [[Revolut_01]] 🆔 4250"
        txn = parse_transaction(line, "2026.md", 68)
        assert txn is not None
        assert "Andres" in txn.people

    def test_bizum_outgoing_plain(self):
        line = "- [ ] `-16.20` [[Entertainment]] Bizum > Beltran ➕ 2024-11-19 [[CaixaBank_01]] 🆔 55"
        txn = parse_transaction(line, "2024.md", 43)
        assert txn is not None
        assert "Beltran" in txn.people

    def test_bizum_payment_from_name(self):
        line = "- [ ] `9.00` [[Other]] Bizum payment from: Maria guillermina M.O. ➕ 2025-12-30 [[Revolut_01]] 🆔 4162"
        txn = parse_transaction(line, "2025.md", 7)
        assert txn is not None
        assert "Maria guillermina M.O." in txn.people

    def test_bizum_payment_from_phone(self):
        line = "- [ ] `365.60` [[Sales]] Bizum payment from: +34669495222 ➕ 2025-06-26 [[Revolut_01]] 🆔 3384"
        txn = parse_transaction(line, "2025.md", 777)
        assert txn is not None
        assert txn.people == []

    def test_transfer_to_wikilink(self):
        line = "- [ ] `-1252.00` [[Other]] To [[Mom]] ➕ 2026-02-05 [[Revolut_01]] 🆔 4244"
        txn = parse_transaction(line, "2026.md", 71)
        assert txn is not None
        assert "Mom" in txn.people

    def test_transfer_to_plain_name(self):
        line = "- [ ] `-45.45` [[Other]] To Manuel Eguren Moreno ➕ 2022-09-17 [[Revolut_01]] 🆔 3232"
        txn = parse_transaction(line, "2022.md", 6)
        assert txn is not None
        assert "Manuel Eguren Moreno" in txn.people

    def test_bizum_generic(self):
        line = "- [ ] `20.25` [[Entertainment]] Bizum Padel ➕ 2024-11-17 [[CaixaBank_01]] 🆔 58"
        txn = parse_transaction(line, "2024.md", 46)
        assert txn is not None
        assert txn.description == "Bizum Padel"

    def test_description_with_dots(self):
        line = "- [ ] `-25.45` [[Education]] DeepLearning.AI ➕ 2026-02-17 [[Revolut_01]] 🆔 4285"
        txn = parse_transaction(line, "2026.md", 34)
        assert txn is not None
        assert txn.description == "DeepLearning.AI"

    def test_description_with_parentheses(self):
        line = "- [ ] `-26.05` [[Food]] Drinks (Paula's bday) ➕ 2024-10-26 [[CaixaBank_01]] 🆔 78"
        txn = parse_transaction(line, "2024.md", 69)
        assert txn is not None
        assert txn.description == "Drinks (Paula's bday)"

    def test_non_transaction_line(self):
        assert parse_transaction("---", "test.md", 1) is None
        assert parse_transaction("tags:", "test.md", 2) is None
        assert parse_transaction("", "test.md", 3) is None
        assert parse_transaction("  - finance/transactions", "test.md", 4) is None

    def test_month_property(self):
        line = "- [ ] `-9.61` [[Wellbeing]] Farmacia Bco Grande ➕ 2021-12-28 [[Revolut_01]] 🆔 3215"
        txn = parse_transaction(line, "2021.md", 6)
        assert txn.month == "2021-12"

    def test_large_negative_amount(self):
        line = "- [ ] `-1252.00` [[Other]] To [[Mom]] ➕ 2026-01-13 [[Revolut_01]] 🆔 4183"
        txn = parse_transaction(line, "2026.md", 137)
        assert txn.amount == -1252.00

    def test_description_with_ampersand(self):
        line = "- [ ] `-3.60` [[Food]] Emka Coffee Specialty & Brunch ➕ 2026-02-10 [[Revolut_01]] 🆔 4260"
        txn = parse_transaction(line, "2026.md", 59)
        assert txn.description == "Emka Coffee Specialty & Brunch"


class TestExtractPeople:
    """Test people extraction from descriptions."""

    def test_no_people(self):
        assert _extract_people("Amazon") == []

    def test_wikilink_person(self):
        people = _extract_people("To [[Mom]]")
        assert "Mom" in people

    def test_bizum_from_name(self):
        people = _extract_people("Bizum < Ivan C.L.")
        assert "Ivan C.L." in people

    def test_bizum_from_phone_excluded(self):
        people = _extract_people("Bizum < +34633810716")
        assert people == []

    def test_bizum_to_wikilink(self):
        people = _extract_people("Bizum > [[Andres]]")
        assert "Andres" in people

    def test_no_duplicates(self):
        people = _extract_people("Bizum > [[Andres]]")
        assert people.count("Andres") == 1


class TestParseAllData:
    """Integration tests against real data."""

    def test_transaction_count(self, store):
        assert store.transaction_count == 1752

    def test_global_balance(self, store):
        assert abs(store.global_balance - 19146.35) < 0.01

    def test_categories_count(self, store):
        assert len(store.categories) == 16

    def test_accounts_count(self, store):
        assert len(store.accounts) == 3

    def test_category_budgets(self, store):
        assert store.categories["Food"]["budget"] == -200
        assert store.categories["Sales"]["budget"] == 2800
        assert store.categories["Charity"]["budget"] == -30
        assert store.categories["Debt"]["budget"] == 0

    def test_category_tracking(self, store):
        assert store.categories["Food"]["track"] is True
        assert store.categories["Debt"]["track"] is False

    def test_all_categories_present(self, store):
        expected = {
            "Charity", "Debt", "Education", "Entertainment", "Food",
            "Housing", "Investments", "Other", "Passive", "Sales",
            "Savings", "Shopping", "Subscriptions", "Taxes",
            "Transportation", "Wellbeing",
        }
        assert set(store.categories.keys()) == expected

    def test_dataframe_columns(self, store):
        expected_cols = {
            "id", "date", "amount", "category", "description", "account",
            "validated", "source_file", "line_number", "raw_line", "people",
            "is_expense", "is_income", "month", "running_sum", "day_end_total",
        }
        assert expected_cols.issubset(set(store.df.columns))

    def test_sorted_by_date(self, store):
        dates = store.df["date"].tolist()
        assert dates == sorted(dates)

    def test_running_sum_final(self, store):
        # The last running_sum should equal global balance
        assert abs(store.df["running_sum"].iloc[-1] - store.global_balance) < 0.01
