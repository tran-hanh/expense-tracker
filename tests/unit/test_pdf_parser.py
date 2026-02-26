"""Tests for src.services.pdf_parser."""
import io
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core.constants import TRANSACTION_COLUMNS
from src.services.pdf_parser import (
    _looks_like_header_row,
    _map_headers,
    _normalize_header,
    _parse_date,
    _parse_vnd_amount,
    _score_table_as_transactions,
    _table_to_rows,
    extract_transactions_from_pdf,
    load_pdfs_to_dataframe,
)


# --- _normalize_header ---
def test_normalize_header_none_or_empty():
    assert _normalize_header(None) == ""
    assert _normalize_header("") == ""
    assert _normalize_header("   ") == ""


def test_normalize_header_strips_and_lowercases():
    assert _normalize_header("  Date  ") == "date"
    assert _normalize_header("NGÀY GIAO DỊCH") != ""


def test_normalize_header_collapses_whitespace():
    assert _normalize_header("ghi   nợ") == "ghi nợ"


# --- _parse_vnd_amount ---
def test_parse_vnd_amount_none_nan_empty():
    assert _parse_vnd_amount(None) == 0.0
    assert _parse_vnd_amount(pd.NA) == 0.0
    assert _parse_vnd_amount(float("nan")) == 0.0
    assert _parse_vnd_amount("") == 0.0
    assert _parse_vnd_amount("   ") == 0.0


def test_parse_vnd_amount_int_float():
    assert _parse_vnd_amount(100) == 100.0
    assert _parse_vnd_amount(1.5) == 1.5


def test_parse_vnd_amount_string_with_thousand_sep():
    assert _parse_vnd_amount("1,000,000") == 1_000_000.0
    assert _parse_vnd_amount("10.500.000") == 10_500_000.0


def test_parse_vnd_amount_negative():
    assert _parse_vnd_amount("-50,000") == -50_000.0


def test_parse_vnd_amount_decimal_style_parsed_as_float():
    """One . or , with 1-2 digits after is treated as decimal."""
    assert _parse_vnd_amount("123.45") == 123.45
    assert _parse_vnd_amount("123,4") == 123.4


def test_parse_vnd_amount_invalid_returns_zero():
    assert _parse_vnd_amount("abc") == 0.0
    assert _parse_vnd_amount("--") == 0.0


# --- _parse_date ---
def test_parse_date_none_nan_empty():
    assert _parse_date(None) is None
    assert _parse_date("") is None
    assert _parse_date("   ") is None
    # pd.NA may yield None or NaT depending on pandas/pd.to_datetime
    result = _parse_date(pd.NA)
    assert result is None or pd.isna(result)


def test_parse_date_dd_mm_yyyy():
    t = _parse_date("01/12/2025", day_first=True)
    assert t is not None
    assert t.year == 2025 and t.month == 12 and t.day == 1


def test_parse_date_two_digit_year():
    t = _parse_date("15/06/25", day_first=True)
    assert t is not None
    assert t.year == 2025 and t.month == 6 and t.day == 15


def test_parse_date_yyyy_mm_dd_with_day_first_false():
    t = _parse_date("2025-12-01", day_first=False)
    assert t is not None
    assert t.year == 2025 and t.month == 12 and t.day == 1


def test_parse_date_invalid_returns_none():
    assert _parse_date("not-a-date") is None
    assert _parse_date("32/01/2025") is None


# --- _map_headers ---
def test_map_headers_empty():
    assert _map_headers([]) == {}


def test_map_headers_recognizes_standard_aliases():
    m = _map_headers(["Date", "Description", "Debit", "Credit"])
    assert m == {0: "Date", 1: "Description", 2: "Debit", 3: "Credit"}


def test_map_headers_skips_empty():
    m = _map_headers(["Date", "", "Debit"])
    assert 0 in m and 2 in m
    assert 1 not in m


def test_map_headers_vietnamese():
    m = _map_headers(["ngày giao dịch", "nội dung", "ghi nợ", "ghi có"])
    assert m.get(0) == "Date"
    assert m.get(1) == "Description"
    assert m.get(2) == "Debit"
    assert m.get(3) == "Credit"


# --- _looks_like_header_row ---
def test_looks_like_header_row_empty():
    assert _looks_like_header_row([]) is False


def test_looks_like_header_row_mostly_text():
    assert _looks_like_header_row(["Date", "Description", "Amount"]) is True


def test_looks_like_header_row_mostly_numeric():
    assert _looks_like_header_row(["1", "2", "3", "4"]) is False


# --- _score_table_as_transactions ---
def test_score_table_empty_or_short():
    assert _score_table_as_transactions([]) == 0.0
    assert _score_table_as_transactions([["A"]]) == 0.0


def test_score_table_two_cols():
    t = [["Col1", "Col2"], ["a", "1"]]
    assert _score_table_as_transactions(t) >= 2.0


def test_score_table_header_like_and_many_rows():
    t = [["Date", "Description", "Debit"], ["1", "2", "3"]] + [["a", "b", "c"]] * 5
    s = _score_table_as_transactions(t)
    assert s > 10.0


# --- _table_to_rows ---
def test_table_to_rows_empty():
    assert _table_to_rows([], {0: "A"}) == []
    assert _table_to_rows([["A"]], {}) == []


def test_table_to_rows_maps_columns():
    raw = [["Date", "Amount"], ["01/01/2025", "100,000"]]
    col_map = {0: "Date", 1: "Debit"}
    rows = _table_to_rows(raw, col_map)
    assert len(rows) == 1
    assert rows[0]["Date"] == "01/01/2025"
    assert rows[0]["Debit"] == "100,000"


def test_table_to_rows_pads_short_row():
    raw = [["A", "B"], ["x"]]
    rows = _table_to_rows(raw, {0: "A", 1: "B"})
    assert len(rows) == 1
    assert rows[0]["A"] == "x"
    assert rows[0]["B"] is None


# --- load_pdfs_to_dataframe failure cases ---
def test_load_pdfs_to_dataframe_invalid_bytes_reports_failed():
    df, failed = load_pdfs_to_dataframe([(b"", "checking")])
    assert df.empty
    assert len(failed) == 1
    assert failed[0][0] == 0
    assert "Invalid" in failed[0][1] or "empty" in failed[0][1].lower()


def test_load_pdfs_to_dataframe_non_bytes_reports_failed():
    df, failed = load_pdfs_to_dataframe([("not bytes", "checking")])  # type: ignore[arg-type]
    assert df.empty
    assert len(failed) == 1
    assert failed[0][0] == 0


def test_load_pdfs_to_dataframe_parse_exception_reports_failed():
    """When extract_transactions_from_pdf raises, we get (empty df, failed with message)."""
    with patch("src.services.pdf_parser.extract_transactions_from_pdf") as mock_extract:
        mock_extract.side_effect = RuntimeError("Corrupted PDF")
        df, failed = load_pdfs_to_dataframe([(b"valid bytes", "checking")])
    assert df.empty
    assert len(failed) == 1
    assert failed[0][0] == 0
    assert "Corrupted" in failed[0][1]


def test_load_pdfs_to_dataframe_empty_extract_reports_failed():
    """When extract returns empty DataFrame, file is reported as failed."""
    with patch("src.services.pdf_parser.extract_transactions_from_pdf") as mock_extract:
        mock_extract.return_value = pd.DataFrame(columns=TRANSACTION_COLUMNS)
        df, failed = load_pdfs_to_dataframe([(b"x", "checking")])
    assert df.empty
    assert len(failed) == 1
    assert "No transaction" in failed[0][1]


def test_load_pdfs_to_dataframe_success_deduplicate():
    """One successful parse returns df and no failed; deduplicate runs."""
    with patch("src.services.pdf_parser.extract_transactions_from_pdf") as mock_extract:
        mock_extract.return_value = pd.DataFrame(
            [["2025-12-01", "Pay", 50_000.0, 0.0, "checking"]],
            columns=TRANSACTION_COLUMNS,
        )
        df, failed = load_pdfs_to_dataframe([(b"pdf1", "checking")], deduplicate=True)
    assert not df.empty
    assert len(failed) == 0
    assert list(df.columns) == list(TRANSACTION_COLUMNS)


# --- extract_transactions_from_pdf with mocked pdfplumber ---
@patch("src.services.pdf_parser.pdfplumber.open")
def test_extract_transactions_from_pdf_with_mock_table(mock_open):
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_tables.return_value = [
        [
            ["Date", "Description", "Debit", "Credit"],
            ["01/12/2025", "Test payment", "100,000", ""],
        ]
    ]
    mock_pdf.pages = [mock_page]
    mock_open.return_value.__enter__.return_value = mock_pdf
    mock_open.return_value.__exit__.return_value = None

    df = extract_transactions_from_pdf(b"dummy", source_type="checking")
    assert not df.empty
    assert list(df.columns) == list(TRANSACTION_COLUMNS)
    assert df["Debit"].iloc[0] == 100_000.0
    assert df["SourceType"].iloc[0] == "checking"
    assert df["Description"].iloc[0] == "Test payment"


@patch("src.services.pdf_parser.pdfplumber.open")
def test_extract_transactions_from_pdf_no_tables_returns_empty(mock_open):
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_tables.return_value = []
    mock_pdf.pages = [mock_page]
    mock_open.return_value.__enter__.return_value = mock_pdf
    mock_open.return_value.__exit__.return_value = None

    df = extract_transactions_from_pdf(b"dummy")
    assert df.empty
    assert list(df.columns) == list(TRANSACTION_COLUMNS)


def test_load_pdfs_to_dataframe_empty():
    df, failed = load_pdfs_to_dataframe([])
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert list(df.columns) == list(TRANSACTION_COLUMNS)
    assert failed == []


def test_load_pdfs_to_dataframe_deduplicate():
    # Two identical in-memory "PDFs" that yield no rows (invalid bytes) are skipped;
    # use empty list to test deduplicate path with no rows.
    df, _ = load_pdfs_to_dataframe([], deduplicate=True)
    assert df.empty
    df, _ = load_pdfs_to_dataframe([], deduplicate=False)
    assert df.empty


def test_extract_transactions_from_pdf_rejects_non_bytes():
    with pytest.raises(TypeError, match="pdf_bytes must be bytes"):
        extract_transactions_from_pdf("not bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="pdf_bytes must be bytes"):
        extract_transactions_from_pdf(None)  # type: ignore[arg-type]


def test_extract_transactions_from_pdf_rejects_empty_bytes():
    with pytest.raises(ValueError, match="must not be empty"):
        extract_transactions_from_pdf(b"")


def test_load_pdfs_to_dataframe_returns_expected_columns():
    """Empty loader returns DataFrame with TRANSACTION_COLUMNS and failed list."""
    df, failed = load_pdfs_to_dataframe([])
    assert list(df.columns) == list(TRANSACTION_COLUMNS)
    assert failed == []
