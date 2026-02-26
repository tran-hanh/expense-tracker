"""Tests for src.core.filter_rules."""
import pandas as pd
import pytest

from src.core.constants import TRANSACTION_COLUMNS
from src.core.filter_rules import (
    apply_all_rules,
    apply_global_exclusions,
    apply_month_specific_exclusions,
    apply_custom_exclusions,
)


def test_apply_global_exclusions_empty_df():
    df = pd.DataFrame(columns=["Date", "Description", "Debit"])
    inc, excl = apply_global_exclusions(df, "Description", "Debit")
    assert inc.empty
    assert excl.empty


def test_apply_global_exclusions_by_amount():
    df = pd.DataFrame(
        {"Description": ["A", "B"], "Debit": [50_000_000.0, 101_000_000.0]}
    )
    inc, excl = apply_global_exclusions(df, "Description", "Debit")
    assert len(inc) == 1
    assert len(excl) == 1
    assert excl["Debit"].iloc[0] == 101_000_000.0


def test_apply_global_exclusions_by_keyword():
    df = pd.DataFrame(
        {"Description": ["Normal payment", "PHAT LOC REAL ESTATE fee"], "Debit": [10_000.0, 20_000.0]}
    )
    inc, excl = apply_global_exclusions(df, "Description", "Debit")
    assert len(inc) == 1
    assert "Normal payment" in inc["Description"].values
    assert len(excl) == 1
    assert "PHAT LOC REAL ESTATE" in excl["Description"].iloc[0]


def test_apply_month_specific_exclusions_dec_2025():
    df = pd.DataFrame(
        {
            "Description": ["VO THI HONG transfer", "Shop payment"],
            "Debit": [42_500_000.0, 100_000.0],
        }
    )
    inc, excl = apply_month_specific_exclusions(df, 2025, 12, "Description")
    assert len(excl) == 1
    assert "VO THI HONG" in excl["Description"].iloc[0]
    assert len(inc) == 1
    assert "Shop" in inc["Description"].iloc[0]


def test_apply_custom_exclusions_keyword():
    df = pd.DataFrame(
        {"Description": ["Pay Nguyen Van A", "Other"], "Debit": [5_000.0, 6_000.0]}
    )
    inc, excl = apply_custom_exclusions(df, "Description", "Debit", "Nguyen Van A")
    assert len(excl) == 1
    assert len(inc) == 1
    assert "Other" in inc["Description"].iloc[0]


def test_apply_custom_exclusions_amount():
    df = pd.DataFrame(
        {"Description": ["Tx1", "Tx2"], "Debit": [15_000_000.0, 20_000.0]}
    )
    inc, excl = apply_custom_exclusions(df, "Description", "Debit", "15000000")
    assert len(excl) == 1
    assert excl["Debit"].iloc[0] == 15_000_000.0


def test_apply_all_rules_returns_valid_and_excluded():
    df = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2026-01-01")],
            "Description": ["SHOPEEPAY"],
            "Debit": [50_000.0],
            "Credit": [0.0],
        }
    )
    valid, excluded = apply_all_rules(df, 2026, 1, custom_exclusions_text="")
    assert isinstance(valid, pd.DataFrame)
    assert isinstance(excluded, pd.DataFrame)
    assert len(valid) == 1
    assert len(excluded) == 0


def test_apply_all_rules_empty_df():
    df = pd.DataFrame(columns=["Date", "Description", "Debit", "Credit"])
    valid, excluded = apply_all_rules(df, 2026, 1)
    assert valid.empty
    assert excluded.empty


def test_apply_all_rules_global_and_month_specific():
    df = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2025-12-01"), pd.Timestamp("2025-12-02")],
            "Description": ["VO THI HONG", "Regular expense"],
            "Debit": [42_500_000.0, 30_000.0],
            "Credit": [0.0, 0.0],
        }
    )
    valid, excluded = apply_all_rules(df, 2025, 12)
    assert len(valid) == 1
    assert "Regular" in valid["Description"].iloc[0]
    assert len(excluded) == 1
    assert "VO THI HONG" in excluded["Description"].iloc[0]
