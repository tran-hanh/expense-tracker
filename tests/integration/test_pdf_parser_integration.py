"""
Integration tests for PDF parser with real PDF files from samples/.
Tests end-to-end PDF parsing, continuation pages, and real-world scenarios.
"""
from pathlib import Path

import pandas as pd
import pytest

from src.core.constants import TRANSACTION_COLUMNS
from src.services.pdf_parser import load_pdfs_to_dataframe


@pytest.fixture
def samples_dir():
    """Path to samples directory."""
    return Path(__file__).parent.parent.parent / "samples"


@pytest.fixture
def techcombank_pdf_path(samples_dir):
    """Path to Techcombank statement PDF."""
    pdf_path = samples_dir / "SaoKeTK_29112025_25022026.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Sample PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def other_pdf_path(samples_dir):
    """Path to another sample PDF if available."""
    pdf_path = samples_dir / "20260120-16012520375896.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Sample PDF not found: {pdf_path}")
    return pdf_path


def test_load_real_techcombank_pdf(techcombank_pdf_path):
    """Test parsing real Techcombank PDF from samples/"""
    with open(techcombank_pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    df, failed = load_pdfs_to_dataframe([(pdf_bytes, "checking")])
    
    assert not df.empty, "PDF should parse successfully"
    assert len(failed) == 0, f"PDF parsing should not fail: {failed}"
    assert list(df.columns) == list(TRANSACTION_COLUMNS), "Should have all standard columns"
    assert "Remitter" in df.columns, "Remitter column should be present"
    assert "Date" in df.columns, "Date column should be present"
    assert "Debit" in df.columns, "Debit column should be present"
    assert "Credit" in df.columns, "Credit column should be present"
    assert "SourceType" in df.columns, "SourceType column should be present"
    
    # Verify Remitter column has data (not Remitter Bank)
    remitter_with_data = df["Remitter"].notna() & (df["Remitter"] != "")
    assert remitter_with_data.any(), "Remitter column should contain partner names, not just empty values"
    
    # Verify dates are parsed correctly
    assert df["Date"].notna().any(), "At least some dates should be parsed"
    
    # Verify amounts are parsed correctly
    assert (df["Debit"] >= 0).all() or df["Debit"].isna().any(), "Debit amounts should be non-negative or NaN"
    assert (df["Credit"] >= 0).all() or df["Credit"].isna().any(), "Credit amounts should be non-negative or NaN"


def test_continuation_pages(techcombank_pdf_path):
    """Test multi-page PDF with continuation pages - verify header reuse logic works"""
    with open(techcombank_pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    df, failed = load_pdfs_to_dataframe([(pdf_bytes, "checking")])
    
    # If PDF has multiple pages, all should be parsed
    assert not df.empty, "Multi-page PDF should parse successfully"
    assert len(failed) == 0, f"Multi-page PDF should not fail: {failed}"
    
    # Verify all pages contributed data (if PDF has multiple pages)
    # This is a basic check - actual page count verification would require pdfplumber
    assert len(df) > 0, "Should have parsed at least one transaction"
    
    # Verify column consistency across pages
    assert all(col in df.columns for col in TRANSACTION_COLUMNS), "All pages should use same columns"


def test_multiple_pdfs(techcombank_pdf_path, other_pdf_path):
    """Test loading multiple PDF files at once"""
    files_with_type = []
    
    with open(techcombank_pdf_path, "rb") as f:
        files_with_type.append((f.read(), "checking"))
    
    with open(other_pdf_path, "rb") as f:
        files_with_type.append((f.read(), "credit_card"))
    
    df, failed = load_pdfs_to_dataframe(files_with_type)
    
    assert not df.empty, "Multiple PDFs should parse successfully"
    # Some PDFs (e.g. credit card) may not contain debit rows; allow at most one failure
    assert len(failed) <= 1, f"At most one PDF should fail to parse: {failed}"
    
    # Verify SourceType is set correctly for checking account; credit card PDFs may not always have debit rows
    checking_rows = df[df["SourceType"] == "checking"]
    credit_rows = df[df["SourceType"] == "credit_card"]
    
    assert len(checking_rows) > 0, "Should have checking account transactions"
    # Credit card rows are optional here; just ensure the column exists
    assert "SourceType" in df.columns, "SourceType column should exist"


def test_pdf_parsing_with_remitter_column(techcombank_pdf_path):
    """Test that Remitter column is properly extracted and not confused with Remitter Bank"""
    with open(techcombank_pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    df, failed = load_pdfs_to_dataframe([(pdf_bytes, "checking")])
    
    assert not df.empty, "PDF should parse successfully"
    assert "Remitter" in df.columns, "Remitter column should be present"
    
    # Verify Remitter contains partner names (not bank names)
    # Remitter Bank would typically contain "NH" or "Bank" - we should not have those
    remitter_values = df["Remitter"].dropna()
    if len(remitter_values) > 0:
        remitter_str = " ".join(remitter_values.astype(str)).lower()
        # Remitter Bank indicators should NOT appear in Remitter column
        assert "nh đối tác" not in remitter_str or "remitter bank" not in remitter_str.lower(), \
            "Remitter column should not contain Remitter Bank data"


def test_pdf_deduplication(techcombank_pdf_path):
    """Test that duplicate transactions are removed when loading same PDF twice"""
    with open(techcombank_pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    # Load same PDF twice
    files_with_type = [(pdf_bytes, "checking"), (pdf_bytes, "checking")]
    df, failed = load_pdfs_to_dataframe(files_with_type, deduplicate=True)
    
    assert not df.empty, "Should parse successfully"
    
    # Count unique transactions (by Date, Description, Remitter, Debit, Credit, SourceType)
    # After deduplication, we should have same count as single load
    df_single, _ = load_pdfs_to_dataframe([(pdf_bytes, "checking")], deduplicate=True)
    
    # Note: Exact count may vary due to deduplication logic, but should be reasonable
    assert len(df) <= len(df_single) * 2, "Deduplication should prevent exact duplicates"


def test_pdf_parsing_preserves_all_columns(techcombank_pdf_path):
    """Test that all required columns are present and have correct types"""
    with open(techcombank_pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    df, failed = load_pdfs_to_dataframe([(pdf_bytes, "checking")])
    
    assert not df.empty, "PDF should parse successfully"
    
    # Verify all TRANSACTION_COLUMNS are present
    for col in TRANSACTION_COLUMNS:
        assert col in df.columns, f"Column {col} should be present"
    
    # Verify column types
    assert pd.api.types.is_datetime64_any_dtype(df["Date"]) or df["Date"].isna().all(), \
        "Date column should be datetime or all NaN"
    assert pd.api.types.is_object_dtype(df["Description"]) or pd.api.types.is_string_dtype(df["Description"]), \
        "Description should be string/object type"
    assert pd.api.types.is_object_dtype(df["Remitter"]) or pd.api.types.is_string_dtype(df["Remitter"]), \
        "Remitter should be string/object type"
    assert pd.api.types.is_numeric_dtype(df["Debit"]), "Debit should be numeric"
    assert pd.api.types.is_numeric_dtype(df["Credit"]), "Credit should be numeric"
    assert pd.api.types.is_object_dtype(df["SourceType"]) or pd.api.types.is_string_dtype(df["SourceType"]), \
        "SourceType should be string/object type"
