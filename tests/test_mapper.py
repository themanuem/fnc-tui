"""Tests for LLM column mapper."""

from unittest.mock import patch

import pandas as pd
import pytest

from finance_tui.importers.mapper import ColumnMapping, detect_columns, _extract_json, _parse_mapping
from finance_tui.importers.llm import Provider


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "Fecha": ["2026-01-15", "2026-01-16"],
        "Concepto": ["Mercadona", "Nomina"],
        "Importe": [-45.20, 2100.00],
        "Saldo": [1234.56, 3334.56],
    })


@pytest.fixture
def split_df():
    return pd.DataFrame({
        "Date": ["2026-01-15", "2026-01-16"],
        "Desc": ["Grocery", "Salary"],
        "Debit": [45.20, 0.0],
        "Credit": [0.0, 2100.00],
    })


class TestColumnMapping:
    def test_single_amount_valid(self):
        m = ColumnMapping(date_col="Date", description_col="Desc", amount_col="Amount")
        m.validate()
        assert not m.is_split

    def test_split_amount_valid(self):
        m = ColumnMapping(date_col="Date", description_col="Desc", debit_col="Debit", credit_col="Credit")
        m.validate()
        assert m.is_split

    def test_no_amount_raises(self):
        m = ColumnMapping(date_col="Date", description_col="Desc")
        with pytest.raises(ValueError, match="amount.*debit.*credit"):
            m.validate()


class TestExtractJSON:
    def test_extracts_from_plain_json(self):
        result = _extract_json('{"date": "Fecha", "description": "Concepto", "amount": "Importe"}')
        assert result["date"] == "Fecha"

    def test_extracts_from_wrapped_text(self):
        text = 'Here is the mapping:\n{"date": "Fecha", "description": "Concepto", "amount": "Importe"}\nDone.'
        result = _extract_json(text)
        assert result["amount"] == "Importe"

    def test_raises_on_no_json(self):
        with pytest.raises(ValueError, match="No JSON"):
            _extract_json("I don't know")


class TestParseMapping:
    def test_single_amount(self):
        m = _parse_mapping({"date": "Fecha", "description": "Concepto", "amount": "Importe"})
        assert m.date_col == "Fecha"
        assert m.amount_col == "Importe"
        assert m.debit_col is None

    def test_split_columns(self):
        m = _parse_mapping({"date": "Date", "description": "Desc", "debit": "Debit", "credit": "Credit"})
        assert m.is_split
        assert m.debit_col == "Debit"
        assert m.credit_col == "Credit"


class TestDetectColumns:
    def test_single_amount_response(self, sample_df):
        mock_response = '{"date": "Fecha", "description": "Concepto", "amount": "Importe"}'
        with patch("finance_tui.importers.mapper.llm_complete", return_value=mock_response):
            with patch("finance_tui.importers.mapper.cache_get", return_value=None):
                with patch("finance_tui.importers.mapper.cache_set"):
                    mapping = detect_columns(sample_df, provider=Provider.OLLAMA)
        assert mapping.date_col == "Fecha"
        assert mapping.description_col == "Concepto"
        assert mapping.amount_col == "Importe"

    def test_split_amount_response(self, split_df):
        mock_response = '{"date": "Date", "description": "Desc", "debit": "Debit", "credit": "Credit"}'
        with patch("finance_tui.importers.mapper.llm_complete", return_value=mock_response):
            with patch("finance_tui.importers.mapper.cache_get", return_value=None):
                with patch("finance_tui.importers.mapper.cache_set"):
                    mapping = detect_columns(split_df, provider=Provider.OLLAMA)
        assert mapping.is_split
        assert mapping.debit_col == "Debit"

    def test_uses_cache(self, sample_df):
        cached = {"date": "Fecha", "description": "Concepto", "amount": "Importe"}
        with patch("finance_tui.importers.mapper.cache_get", return_value=cached):
            mapping = detect_columns(sample_df, provider=Provider.OLLAMA)
        assert mapping.date_col == "Fecha"

    def test_caches_result(self, sample_df):
        mock_response = '{"date": "Fecha", "description": "Concepto", "amount": "Importe"}'
        with patch("finance_tui.importers.mapper.llm_complete", return_value=mock_response):
            with patch("finance_tui.importers.mapper.cache_get", return_value=None):
                with patch("finance_tui.importers.mapper.cache_set") as mock_cache:
                    detect_columns(sample_df, provider=Provider.OLLAMA)
        mock_cache.assert_called_once()


class TestLLMProviders:
    def test_ollama_unavailable_detected(self):
        with patch("finance_tui.importers.llm._ollama_available", return_value=False):
            with patch.dict("os.environ", {}, clear=True):
                from finance_tui.importers.llm import detect_provider
                assert detect_provider() is None

    def test_ollama_preferred_over_anthropic(self):
        with patch("finance_tui.importers.llm._ollama_available", return_value=True):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
                from finance_tui.importers.llm import detect_provider
                assert detect_provider() == Provider.OLLAMA

    def test_anthropic_fallback(self):
        with patch("finance_tui.importers.llm._ollama_available", return_value=False):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
                from finance_tui.importers.llm import detect_provider
                assert detect_provider() == Provider.ANTHROPIC

    def test_anthropic_no_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            from finance_tui.importers.llm import _anthropic_complete
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                _anthropic_complete("test", "", "model")
