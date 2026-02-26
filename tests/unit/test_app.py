"""Tests for src.ui.app pure functions (format_vnd, parse_month_year_filter, _cache_key)."""
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


def _import_app_functions():
    """Import app after mocking streamlit so set_page_config and other UI code don't run."""
    with patch.dict(sys.modules, {"streamlit": MagicMock()}):
        from src.ui import app
        return (
            app.format_vnd,
            app.parse_month_year_filter,
            app._cache_key,
            app._totals_from_count_as_expense_mask,
        )


format_vnd, parse_month_year_filter, _cache_key, _totals_from_count_as_expense_mask = _import_app_functions()


def test_format_vnd_none_nan():
    assert format_vnd(None) == "0 VND"
    assert format_vnd(float("nan")) == "0 VND"


def test_format_vnd_positive():
    assert format_vnd(1_000_000) == "1,000,000 VND"
    assert format_vnd(0) == "0 VND"


def test_format_vnd_negative():
    assert format_vnd(-50_000) == "-50,000 VND"


def test_parse_month_year_filter_empty():
    assert parse_month_year_filter("") is None
    assert parse_month_year_filter(None) is None


def test_parse_month_year_filter_mm_yyyy():
    assert parse_month_year_filter("12/2025") == (2025, 12)
    assert parse_month_year_filter("01/2026") == (2026, 1)


def test_parse_month_year_filter_yyyy_mm():
    assert parse_month_year_filter("2025-12") == (2025, 12)
    assert parse_month_year_filter("2026-01") == (2026, 1)


def test_parse_month_year_filter_invalid():
    assert parse_month_year_filter("invalid") is None
    assert parse_month_year_filter("13/2025") == (2025, 13)


def test_cache_key_empty():
    assert _cache_key([]) == ()


def test_cache_key_stable_by_content():
    b1, b2 = b"aa", b"bb"
    k1 = _cache_key([(b1, "checking"), (b2, "credit_card")])
    k2 = _cache_key([(b1, "checking"), (b2, "credit_card")])
    assert k1 == k2
    assert len(k1) == 2
    assert k1[0][0] == hash(b1) and k1[0][1] == "checking"
    assert k1[1][0] == hash(b2) and k1[1][1] == "credit_card"


# --- _totals_from_count_as_expense_mask (simulates "Count as Expense" checkbox logic) ---
def test_totals_from_mask_all_checked():
    """All rows counted: total = sum of all Debit."""
    valid_df = pd.DataFrame({
        "Debit": [10_000.0, 20_000.0, 30_000.0],
        "SourceType": ["checking", "checking", "credit_card"],
    })
    mask = pd.Series([True, True, True])
    total, cc_total = _totals_from_count_as_expense_mask(valid_df, mask)
    assert total == 60_000.0
    assert cc_total == 30_000.0


def test_totals_from_mask_first_row_unchecked():
    """First row unchecked: total excludes first row (simulates first untick)."""
    valid_df = pd.DataFrame({
        "Debit": [10_000.0, 20_000.0, 30_000.0],
        "SourceType": ["checking", "checking", "credit_card"],
    })
    mask = pd.Series([False, True, True])  # first row unticked
    total, cc_total = _totals_from_count_as_expense_mask(valid_df, mask)
    assert total == 50_000.0, "Total must update on first untick (exclude 10k)"
    assert cc_total == 30_000.0


def test_totals_from_mask_none_uses_all_true():
    """None mask: treat as all checked."""
    valid_df = pd.DataFrame({"Debit": [5.0], "SourceType": ["checking"]})
    total, cc_total = _totals_from_count_as_expense_mask(valid_df, None)
    assert total == 5.0
    assert cc_total == 0.0


def test_totals_from_mask_all_unchecked():
    """All unchecked: total and cc_total are 0."""
    valid_df = pd.DataFrame({
        "Debit": [10.0, 20.0],
        "SourceType": ["checking", "credit_card"],
    })
    mask = pd.Series([False, False])
    total, cc_total = _totals_from_count_as_expense_mask(valid_df, mask)
    assert total == 0.0
    assert cc_total == 0.0
