"""Tests for src.core.constants."""
import pytest

from src.core.constants import TRANSACTION_COLUMNS


def test_transaction_columns_is_immutable_tuple():
    assert isinstance(TRANSACTION_COLUMNS, tuple)


def test_transaction_columns_has_required_columns():
    required = ["Date", "Description", "Remitter", "Debit", "Credit", "SourceType"]
    for col in required:
        assert col in TRANSACTION_COLUMNS, f"Missing column: {col}"


def test_transaction_columns_length():
    assert len(TRANSACTION_COLUMNS) == 6


def test_transaction_columns_order():
    assert TRANSACTION_COLUMNS[0] == "Date"
    assert TRANSACTION_COLUMNS[2] == "Remitter"
    assert TRANSACTION_COLUMNS[-1] == "SourceType"
