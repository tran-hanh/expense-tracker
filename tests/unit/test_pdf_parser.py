"""Tests for src.services.pdf_parser."""
import pandas as pd
import pytest

from src.core.constants import TRANSACTION_COLUMNS
from src.services.pdf_parser import (
    load_pdfs_to_dataframe,
    extract_transactions_from_pdf,
)


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
