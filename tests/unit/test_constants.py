"""Tests for src.core.constants."""
import pytest

from src.core.constants import TRANSACTION_COLUMNS


def test_transaction_columns_is_list():
    assert isinstance(TRANSACTION_COLUMNS, list)


def test_transaction_columns_has_required_columns():
    required = ["Date", "Description", "Debit", "Credit", "SourceType"]
    for col in required:
        assert col in TRANSACTION_COLUMNS, f"Missing column: {col}"


def test_transaction_columns_length():
    assert len(TRANSACTION_COLUMNS) == 5


def test_transaction_columns_order():
    assert TRANSACTION_COLUMNS[0] == "Date"
    assert TRANSACTION_COLUMNS[-1] == "SourceType"
