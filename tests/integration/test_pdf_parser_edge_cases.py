"""
Edge case tests for PDF parser: continuation pages, malformed data, missing columns.
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core.constants import TRANSACTION_COLUMNS
from src.services.pdf_parser import (
    _first_row_looks_like_data,
    _transaction_map_complete,
    extract_transactions_from_pdf,
    load_pdfs_to_dataframe,
)


def test_transaction_map_complete():
    """Test _transaction_map_complete function for continuation page detection"""
    # Complete map (has Date and Debit)
    assert _transaction_map_complete({0: "Date", 1: "Description", 2: "Debit"}) is True
    
    # Incomplete map (missing Date)
    assert _transaction_map_complete({1: "Description", 2: "Debit"}) is False
    
    # Incomplete map (missing Debit)
    assert _transaction_map_complete({0: "Date", 1: "Description"}) is False
    
    # Empty map
    assert _transaction_map_complete({}) is False
    
    # Map with Date and Debit (minimal required)
    assert _transaction_map_complete({0: "Date", 3: "Debit"}) is True


def test_first_row_looks_like_data():
    """Test detection of data rows vs header rows for continuation pages"""
    # Date-like first cell (data row) - DD/MM or DD-MM formats
    assert _first_row_looks_like_data(["01/12/2025", "Description", "Amount"]) is True
    assert _first_row_looks_like_data(["15-06-25", "Other"]) is True
    
    # Header-like first cell
    assert _first_row_looks_like_data(["Date", "Description", "Amount"]) is False
    assert _first_row_looks_like_data(["Ngày giao dịch", "Đối tác"]) is False
    assert _first_row_looks_like_data(["", "Description"]) is False
    
    # Empty row
    assert _first_row_looks_like_data([]) is False
    assert _first_row_looks_like_data([None]) is False


@patch("src.services.pdf_parser.pdfplumber.open")
def test_continuation_page_header_reuse(mock_open):
    """Test that continuation pages reuse column map from previous page"""
    mock_pdf = MagicMock()
    
    # Page 1: Has header row
    page1 = MagicMock()
    page1.extract_tables.return_value = [
        [
            ["Ngày giao dịch", "Đối tác", "Diễn giải", "Nợ TKTT", "Có TKTT"],
            ["01/12/2025", "Partner A", "Payment 1", "100,000", ""],
        ]
    ]
    
    # Page 2: Continuation page - first row is data (date-like), not header
    page2 = MagicMock()
    page2.extract_tables.return_value = [
        [
            ["02/12/2025", "Partner B", "Payment 2", "200,000", ""],  # Data row, not header
            ["03/12/2025", "Partner C", "Payment 3", "300,000", ""],
        ]
    ]
    
    mock_pdf.pages = [page1, page2]
    mock_open.return_value.__enter__.return_value = mock_pdf
    mock_open.return_value.__exit__.return_value = None
    
    df = extract_transactions_from_pdf(b"dummy", source_type="checking")
    
    # Should parse both pages
    assert len(df) >= 2, "Should parse transactions from both pages"
    assert list(df.columns) == list(TRANSACTION_COLUMNS), "Should have standard columns"


@patch("src.services.pdf_parser.pdfplumber.open")
def test_malformed_header_handling(mock_open):
    """Test handling of malformed or unexpected header formats"""
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    
    # Malformed header: missing expected columns
    mock_page.extract_tables.return_value = [
        [
            ["Col1", "Col2"],  # Only 2 columns, missing Date/Debit
            ["Data1", "Data2"],
        ]
    ]
    
    mock_pdf.pages = [mock_page]
    mock_open.return_value.__enter__.return_value = mock_pdf
    mock_open.return_value.__exit__.return_value = None
    
    df = extract_transactions_from_pdf(b"dummy")
    
    # Should return empty DataFrame or handle gracefully
    assert isinstance(df, pd.DataFrame), "Should return DataFrame"
    assert list(df.columns) == list(TRANSACTION_COLUMNS), "Should have standard columns"


@patch("src.services.pdf_parser.pdfplumber.open")
def test_missing_columns_handled_gracefully(mock_open):
    """Test that missing columns are handled and filled with None"""
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    
    # Table with Date and Debit, but missing Description and Remitter
    mock_page.extract_tables.return_value = [
        [
            ["Date", "Debit"],  # Minimal columns
            ["01/12/2025", "100,000"],
        ]
    ]
    
    mock_pdf.pages = [mock_page]
    mock_open.return_value.__enter__.return_value = mock_pdf
    mock_open.return_value.__exit__.return_value = None
    
    df = extract_transactions_from_pdf(b"dummy")
    
    # Should have all standard columns
    assert list(df.columns) == list(TRANSACTION_COLUMNS), "Should have all standard columns"
    
    # Missing columns should be None or empty string
    if not df.empty:
        assert "Description" in df.columns, "Description column should exist"
        assert "Remitter" in df.columns, "Remitter column should exist"


@patch("src.services.pdf_parser.pdfplumber.open")
def test_date_format_variations_in_same_pdf(mock_open):
    """Test handling of different date formats in the same PDF"""
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    
    # Mixed date formats
    mock_page.extract_tables.return_value = [
        [
            ["Date", "Description", "Debit"],
            ["01/12/2025", "Payment 1", "100,000"],  # DD/MM/YYYY
            ["2025-12-02", "Payment 2", "200,000"],  # YYYY-MM-DD
            ["15/06/25", "Payment 3", "300,000"],  # DD/MM/YY
        ]
    ]
    
    mock_pdf.pages = [mock_page]
    mock_open.return_value.__enter__.return_value = mock_pdf
    mock_open.return_value.__exit__.return_value = None
    
    df = extract_transactions_from_pdf(b"dummy", day_first=True)
    
    # Should parse all dates
    assert len(df) == 3, "Should parse all transactions"
    assert df["Date"].notna().all(), "All dates should be parsed"


@patch("src.services.pdf_parser.pdfplumber.open")
def test_amount_format_variations(mock_open):
    """Test handling of different amount formats (comma vs dot separators)"""
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    
    # Mixed amount formats
    mock_page.extract_tables.return_value = [
        [
            ["Date", "Description", "Debit"],
            ["01/12/2025", "Payment 1", "1,000,000"],  # Comma separator
            ["02/12/2025", "Payment 2", "2.500.000"],  # Dot separator
            ["03/12/2025", "Payment 3", "500000"],  # No separator
        ]
    ]
    
    mock_pdf.pages = [mock_page]
    mock_open.return_value.__enter__.return_value = mock_pdf
    mock_open.return_value.__exit__.return_value = None
    
    df = extract_transactions_from_pdf(b"dummy")
    
    # Should parse all amounts
    assert len(df) == 3, "Should parse all transactions"
    assert df["Debit"].notna().all(), "All amounts should be parsed"
    assert df["Debit"].iloc[0] == 1_000_000.0, "Comma separator should work"
    assert df["Debit"].iloc[1] == 2_500_000.0, "Dot separator should work"
    assert df["Debit"].iloc[2] == 500_000.0, "No separator should work"


def test_load_pdfs_to_dataframe_empty_list():
    """Test loading empty list of PDFs"""
    df, failed = load_pdfs_to_dataframe([])
    
    assert isinstance(df, pd.DataFrame), "Should return DataFrame"
    assert df.empty, "Should be empty"
    assert list(df.columns) == list(TRANSACTION_COLUMNS), "Should have standard columns"
    assert failed == [], "Should have no failed files"


def test_load_pdfs_to_dataframe_all_fail():
    """Test when all PDFs fail to parse"""
    df, failed = load_pdfs_to_dataframe([
        (b"invalid pdf bytes", "checking"),
        (b"", "credit_card"),
    ])
    
    assert isinstance(df, pd.DataFrame), "Should return DataFrame"
    assert len(failed) == 2, "Should report 2 failed files"
    assert all(f[0] in [0, 1] for f in failed), "Failed indices should be 0 and 1"
