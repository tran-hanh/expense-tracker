"""
Pytest fixtures shared across tests.
"""
import pandas as pd
import pytest

from src.core.constants import TRANSACTION_COLUMNS


@pytest.fixture
def transaction_columns():
    """Standard transaction column list."""
    return list(TRANSACTION_COLUMNS)


@pytest.fixture
def sample_transactions_df():
    """Minimal DataFrame with Date, Description, Debit, Credit for filter tests."""
    return pd.DataFrame(
        {
            "Date": [
                pd.Timestamp("2025-12-01"),
                pd.Timestamp("2026-01-15"),
                pd.Timestamp("2026-02-10"),
            ],
            "Description": [
                "SHOPEEPAY payment",
                "PHAT LOC REAL ESTATE",
                "M SERVICE JSC MoMo",
            ],
            "Debit": [50_000.0, 150_000_000.0, 25_000.0],
            "Credit": [0.0, 0.0, 0.0],
        }
    )
