"""Tests for the writer module - round-trip fidelity."""

from finance_tui.parser import parse_transaction
from finance_tui.writer import change_category, serialize_transaction, toggle_validated


SAMPLE_LINES = [
    "- [ ] `-9.61` [[Wellbeing]] Farmacia Bco Grande ➕ 2021-12-28 [[Revolut_01]] 🆔 3215",
    "- [ ] `2782.11` [[Sales]] Payment from CELONIS SL ➕ 2026-02-25 [[Revolut_01]] 🆔 4307",
    "- [ ] `-25.85` [[Other]] Bizum > [[Andres]] ➕ 2026-02-07 [[Revolut_01]] 🆔 4250",
    "- [ ] `-1252.00` [[Other]] To [[Mom]] ➕ 2026-02-05 [[Revolut_01]] 🆔 4244",
    "- [ ] `30.00` [[Other]] Bizum < Ivan C.L. ➕ 2026-02-15 [[Revolut_01]] 🆔 4276",
    "- [ ] `6.00` [[Other]] Bizum < +34633810716 ➕ 2026-02-11 [[Revolut_01]] 🆔 4263",
    "- [ ] `9.00` [[Other]] Bizum payment from: Maria guillermina M.O. ➕ 2025-12-30 [[Revolut_01]] 🆔 4162",
    "- [ ] `-45.00` [[Subscriptions]] CENTRO CULTUR. ➕ 2026-02-17 [[CaixaBank_01]] 🆔 4315",
    "- [ ] `-3.60` [[Food]] Emka Coffee Specialty & Brunch ➕ 2026-02-10 [[Revolut_01]] 🆔 4260",
    "- [ ] `-26.05` [[Food]] Drinks (Paula's bday) ➕ 2024-10-26 [[CaixaBank_01]] 🆔 78",
]


class TestRoundTrip:
    """Test that serialize(parse(line)) == line for all formats."""

    def test_round_trip_all_samples(self):
        for line in SAMPLE_LINES:
            txn = parse_transaction(line, "test.md", 1)
            assert txn is not None, f"Failed to parse: {line}"
            result = serialize_transaction(
                txn.validated,
                txn.amount,
                txn.category,
                txn.description,
                txn.date.isoformat(),
                txn.account,
                txn.id,
            )
            assert result == line, f"Round-trip failed:\n  IN:  {line}\n  OUT: {result}"

    def test_round_trip_all_real_transactions(self, store):
        """Round-trip test for ALL parsed transactions."""
        failures = []
        for _, row in store.df.iterrows():
            original = row["raw_line"]
            txn = parse_transaction(original, row["source_file"], row["line_number"])
            if txn is None:
                failures.append(f"Parse failed: {original}")
                continue
            result = serialize_transaction(
                txn.validated,
                txn.amount,
                txn.category,
                txn.description,
                txn.date.isoformat(),
                txn.account,
                txn.id,
            )
            if result != original:
                failures.append(f"Mismatch:\n  IN:  {original}\n  OUT: {result}")
        assert not failures, f"{len(failures)} round-trip failures:\n" + "\n".join(failures[:5])


class TestToggleValidated:
    def test_toggle_unchecked(self):
        line = "- [ ] `-9.61` [[Wellbeing]] Test ➕ 2021-12-28 [[Revolut_01]] 🆔 3215"
        result = toggle_validated(line)
        assert "- [x] " in result

    def test_toggle_checked(self):
        line = "- [x] `-9.61` [[Wellbeing]] Test ➕ 2021-12-28 [[Revolut_01]] 🆔 3215"
        result = toggle_validated(line)
        assert "- [ ] " in result


class TestChangeCategory:
    def test_change_category(self):
        line = "- [ ] `-9.61` [[Wellbeing]] Test ➕ 2021-12-28 [[Revolut_01]] 🆔 3215"
        result = change_category(line, "Food")
        assert "[[Food]]" in result
        assert "[[Wellbeing]]" not in result

    def test_preserves_rest(self):
        line = "- [ ] `-25.85` [[Other]] Bizum > [[Andres]] ➕ 2026-02-07 [[Revolut_01]] 🆔 4250"
        result = change_category(line, "Food")
        assert "[[Food]]" in result
        assert "[[Andres]]" in result  # Other wikilinks preserved
        assert "[[Revolut_01]]" in result
