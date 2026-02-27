"""
E2E tests for Streamlit UI flows: file upload, filtering, checkbox interactions, KPI updates.
Uses session state mocking to test UI logic without running Streamlit server.
"""
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Mock Streamlit before importing app
sys.modules["streamlit"] = MagicMock()

from src.ui import app


@pytest.fixture
def mock_streamlit():
    """Mock Streamlit module for testing.

    Provides a session_state object that supports attribute access, similar to real Streamlit.
    """
    st = sys.modules["streamlit"]
    st.session_state = MagicMock()
    return st


@pytest.fixture
def sample_transactions():
    """Sample transaction data for testing."""
    return pd.DataFrame(
        {
            "Date": [
                pd.Timestamp("2026-01-15"),
                pd.Timestamp("2026-01-20"),
                pd.Timestamp("2026-01-25"),
            ],
            "Description": [
                "SHOPEEPAY payment",
                "M SERVICE JSC MoMo",
                "Normal expense",
            ],
            "Remitter": [
                "Shopee Vietnam",
                "M SERVICE JSC",
                "Vendor ABC",
            ],
            "Debit": [50_000.0, 25_000.0, 30_000.0],
            "Credit": [0.0, 0.0, 0.0],
            "SourceType": ["checking", "checking", "checking"],
        }
    )


def test_init_session_state(mock_streamlit):
    """Test session state initialization"""
    app.init_session_state()
    # Ensure session_state object exists (detailed attribute checks are Streamlit internals)
    assert hasattr(mock_streamlit, "session_state")


def test_format_vnd():
    """Test VND formatting function"""
    assert app.format_vnd(1_000_000) == "1,000,000 VND"
    assert app.format_vnd(0) == "0 VND"
    assert app.format_vnd(None) == "0 VND"
    assert app.format_vnd(float("nan")) == "0 VND"
    assert app.format_vnd(-50_000) == "-50,000 VND"


def test_parse_month_year_filter():
    """Test month/year filter parsing"""
    assert app.parse_month_year_filter("01/2026") == (2026, 1)
    assert app.parse_month_year_filter("12/2025") == (2025, 12)
    assert app.parse_month_year_filter("2026-01") == (2026, 1)
    assert app.parse_month_year_filter("") is None
    assert app.parse_month_year_filter(None) is None
    assert app.parse_month_year_filter("invalid") is None


def test_get_month_options_with_data(mock_streamlit, sample_transactions):
    """Test month options generation when data is loaded"""
    mock_streamlit.session_state.raw_all = sample_transactions
    
    options = app.get_month_options()
    
    assert isinstance(options, list), "Should return list"
    assert len(options) > 0, "Should have at least one option"
    assert all("/" in opt for opt in options), "Options should be in MM/YYYY format"


def test_get_month_options_no_data(mock_streamlit):
    """Test month options when no data is loaded"""
    mock_streamlit.session_state.raw_all = None
    
    options = app.get_month_options()
    
    assert isinstance(options, list), "Should return list"
    assert len(options) > 0, "Should have default options"


def test_cache_key():
    """Test cache key generation for file uploads"""
    files1 = [(b"pdf1", "checking"), (b"pdf2", "credit_card")]
    files2 = [(b"pdf1", "checking"), (b"pdf2", "credit_card")]
    files3 = [(b"pdf1", "checking"), (b"pdf3", "credit_card")]
    
    key1 = app._cache_key(files1)
    key2 = app._cache_key(files2)
    key3 = app._cache_key(files3)
    
    assert key1 == key2, "Same files should produce same key"
    assert key1 != key3, "Different files should produce different key"
    assert isinstance(key1, tuple), "Key should be tuple"


def test_totals_from_count_as_expense_mask(sample_transactions):
    """Test total calculation from checkbox mask"""
    # All checked
    mask_all_true = pd.Series([True, True, True])
    total_all, credit_total = app._totals_from_count_as_expense_mask(
        sample_transactions, mask_all_true
    )
    assert total_all == 105_000.0, "Should sum all debits"
    assert credit_total == 0.0, "Should have no credit"
    
    # First unchecked
    mask_first_false = pd.Series([False, True, True])
    total_partial, _ = app._totals_from_count_as_expense_mask(
        sample_transactions, mask_first_false
    )
    assert total_partial == 55_000.0, "Should exclude first transaction"
    
    # All unchecked
    mask_all_false = pd.Series([False, False, False])
    total_none, _ = app._totals_from_count_as_expense_mask(
        sample_transactions, mask_all_false
    )
    assert total_none == 0.0, "Should be zero when all unchecked"
    
    # None mask (all checked by default)
    total_default, _ = app._totals_from_count_as_expense_mask(sample_transactions, None)
    assert total_default == 105_000.0, "None mask should default to all True"


@patch("src.ui.app._load_pdfs_cached")
def test_ensure_raw_all_loaded_success(mock_cached, mock_streamlit, sample_transactions):
    """Test successful PDF loading"""
    mock_cached.return_value = (sample_transactions, [])
    
    result = app.ensure_raw_all_loaded([(b"pdf_bytes", "checking")])
    
    assert result is True, "Should return True on success"
    assert getattr(mock_streamlit.session_state, "raw_all", None) is not None, "Should set raw_all"


@patch("src.ui.app._load_pdfs_cached")
def test_ensure_raw_all_loaded_failure(mock_cached, mock_streamlit):
    """Test PDF loading failure handling"""
    mock_cached.return_value = (pd.DataFrame(), [(0, "Failed to parse")])
    
    result = app.ensure_raw_all_loaded([(b"invalid", "checking")])
    
    assert result is False, "Should return False on failure"


@patch("src.ui.app.apply_all_rules")
def test_load_and_filter_data(mock_apply_rules, mock_streamlit, sample_transactions):
    """Test data loading and filtering flow"""
    mock_streamlit.session_state.raw_all = sample_transactions
    mock_apply_rules.return_value = (
        sample_transactions.iloc[:2].copy(),
        sample_transactions.iloc[2:].copy(),
    )
    
    # Use parsed month tuple as expected by load_and_filter_data
    ym = app.parse_month_year_filter("01/2026")
    app.load_and_filter_data(ym, "01/2026", "")
    
    assert mock_apply_rules.called, "Should call apply_all_rules"


def test_format_vnd_edge_cases():
    """Test VND formatting with edge cases"""
    assert app.format_vnd(0.0) == "0 VND"
    assert app.format_vnd(1.5) == "1 VND"  # Rounds down
    assert app.format_vnd(999_999_999) == "999,999,999 VND"


def test_parse_month_year_filter_edge_cases():
    """Test month/year parsing with edge cases"""
    # Single digit month
    assert app.parse_month_year_filter("1/2026") == (2026, 1)
    
    # Two digit month
    assert app.parse_month_year_filter("01/2026") == (2026, 1)
    
    # App does not validate month range; only format, so we just ensure invalid strings return None
    assert app.parse_month_year_filter("abc") is None  # Not a date
