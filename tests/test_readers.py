"""Tests for multi-format file readers."""

from pathlib import Path

import pytest

from finance_tui.importers.readers import read_file

FIXTURES = Path(__file__).parent / "fixtures"


class TestReadCSV:
    def test_reads_semicolon_delimited(self):
        df = read_file(FIXTURES / "sample.csv")
        assert list(df.columns) == ["Fecha", "Concepto", "Importe", "Saldo"]
        assert len(df) == 3
        assert df.iloc[0]["Concepto"] == "Supermercado Mercadona"

    def test_reads_values(self):
        df = read_file(FIXTURES / "sample.csv")
        assert df.iloc[0]["Importe"] == -45.20
        assert df.iloc[1]["Importe"] == 2100.00


class TestReadJSON:
    def test_reads_flat_array(self):
        df = read_file(FIXTURES / "sample.json")
        assert list(df.columns) == ["date", "description", "amount"]
        assert len(df) == 3

    def test_reads_nested_object(self):
        df = read_file(FIXTURES / "nested.json")
        assert "desc" in df.columns
        assert len(df) == 2
        assert df.iloc[0]["desc"] == "Grocery"


class TestReadMDTable:
    def test_reads_pipe_table(self):
        df = read_file(FIXTURES / "sample.md")
        assert list(df.columns) == ["Date", "Description", "Amount"]
        assert len(df) == 3
        assert df.iloc[0]["Description"] == "Grocery shopping"

    def test_skips_separator_rows(self):
        df = read_file(FIXTURES / "sample.md")
        for _, row in df.iterrows():
            assert "---" not in str(row["Date"])


class TestUnsupported:
    def test_raises_on_unknown_extension(self, tmp_path):
        bad = tmp_path / "data.parquet"
        bad.write_text("nope")
        with pytest.raises(ValueError, match="Unsupported file format"):
            read_file(bad)

    def test_error_lists_supported_formats(self, tmp_path):
        bad = tmp_path / "data.txt"
        bad.write_text("nope")
        with pytest.raises(ValueError, match=r"\.csv"):
            read_file(bad)


class TestReadXLSX:
    def test_missing_openpyxl_raises(self, tmp_path, monkeypatch):
        xlsx = tmp_path / "data.xlsx"
        xlsx.write_bytes(b"fake")
        import finance_tui.importers.readers as mod
        original = mod._read_xlsx

        def patched(path):
            import builtins
            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "openpyxl":
                    raise ImportError("no openpyxl")
                return real_import(name, *args, **kwargs)

            monkeypatch.setattr(builtins, "__import__", mock_import)
            try:
                return original(path)
            finally:
                monkeypatch.setattr(builtins, "__import__", real_import)

        with pytest.raises(ImportError, match="openpyxl is required"):
            patched(xlsx)
