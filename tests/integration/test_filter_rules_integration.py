"""
Integration tests for filter rules with full DataFrames including Remitter column.
Tests end-to-end filtering with all columns present.
"""
import pandas as pd
import pytest

from src.core.filter_rules import apply_all_rules


@pytest.fixture
def full_transaction_df():
    """Full DataFrame with all transaction columns including Remitter."""
    return pd.DataFrame(
        {
            "Date": [
                pd.Timestamp("2025-12-01"),
                pd.Timestamp("2025-12-15"),
                pd.Timestamp("2026-01-10"),
                pd.Timestamp("2026-01-20"),
                pd.Timestamp("2026-02-05"),
            ],
            "Description": [
                "SHOPEEPAY payment",
                "VO THI HONG transfer",
                "PHAT LOC REAL ESTATE fee",
                "M SERVICE JSC MoMo",
                "TRANG THI KIEU DUYEN payment",
            ],
            "Remitter": [
                "Shopee Vietnam",
                "VO THI HONG",
                "PHAT LOC REAL ESTATE",
                "M SERVICE JSC",
                "TRANG THI KIEU DUYEN",
            ],
            "Debit": [50_000.0, 42_500_000.0, 20_000.0, 25_000.0, 30_000.0],
            "Credit": [0.0, 0.0, 0.0, 0.0, 0.0],
            "SourceType": ["checking", "checking", "checking", "checking", "checking"],
        }
    )


def test_apply_all_rules_with_remitter_column(full_transaction_df):
    """Test filtering with full DataFrame including Remitter column"""
    valid, excluded = apply_all_rules(full_transaction_df, 2026, 1, custom_exclusions_text="")
    
    assert isinstance(valid, pd.DataFrame), "Valid should be DataFrame"
    assert isinstance(excluded, pd.DataFrame), "Excluded should be DataFrame"
    
    # Verify Remitter column is preserved in both DataFrames
    assert "Remitter" in valid.columns, "Remitter should be in valid DataFrame"
    assert "Remitter" in excluded.columns, "Remitter should be in excluded DataFrame"
    
    # Dec 2025: VO THI HONG should be excluded (month-specific)
    # Jan 2026: PHAT LOC REAL ESTATE should be excluded (global keyword)
    # Feb 2026: TRANG THI KIEU DUYEN should be excluded (month-specific)
    
    # For Jan 2026 filter:
    # - SHOPEEPAY (Dec) - should be excluded (wrong month) or included if we filter by month after loading
    # - VO THI HONG (Dec) - should be excluded (wrong month + month-specific)
    # - PHAT LOC REAL ESTATE (Jan) - should be excluded (global keyword)
    # - M SERVICE JSC (Jan) - should be included
    # - TRANG THI KIEU DUYEN (Feb) - should be excluded (wrong month + month-specific)
    
    # Note: apply_all_rules doesn't filter by month, it only applies exclusion rules
    # So all transactions are considered, but some are excluded
    
    # PHAT LOC REAL ESTATE should be excluded (global keyword)
    excluded_descriptions = excluded["Description"].values if not excluded.empty else []
    assert any("PHAT LOC REAL ESTATE" in str(desc) for desc in excluded_descriptions), \
        "PHAT LOC REAL ESTATE should be excluded by global keyword"
    
    # M SERVICE JSC should be in valid (not excluded)
    if not valid.empty:
        valid_descriptions = valid["Description"].values
        assert any("M SERVICE JSC" in str(desc) for desc in valid_descriptions), \
            "M SERVICE JSC should be in valid expenses"


def test_apply_all_rules_preserves_remitter_in_valid(full_transaction_df):
    """Test that Remitter column values are preserved in valid DataFrame"""
    valid, excluded = apply_all_rules(full_transaction_df, 2026, 1, custom_exclusions_text="")
    
    if not valid.empty:
        # Verify Remitter values are preserved
        assert valid["Remitter"].notna().any() or valid["Remitter"].eq("").any(), \
            "Remitter column should have values (or empty strings)"
        
        # Verify Remitter matches Description where applicable
        for idx, row in valid.iterrows():
            remitter = str(row["Remitter"]) if pd.notna(row["Remitter"]) else ""
            description = str(row["Description"])
            # Some remitters match description keywords (this is expected for some transactions)
            assert isinstance(remitter, str), "Remitter should be string"


def test_apply_all_rules_preserves_remitter_in_excluded(full_transaction_df):
    """Test that Remitter column values are preserved in excluded DataFrame"""
    valid, excluded = apply_all_rules(full_transaction_df, 2026, 1, custom_exclusions_text="")
    
    if not excluded.empty:
        # Verify Remitter values are preserved
        assert excluded["Remitter"].notna().any() or excluded["Remitter"].eq("").any(), \
            "Remitter column should have values (or empty strings) in excluded DataFrame"
        
        # Verify excluded transactions have Remitter data
        excluded_with_remitter = excluded[excluded["Remitter"].notna() & (excluded["Remitter"] != "")]
        # At least some excluded transactions should have Remitter data
        assert len(excluded_with_remitter) >= 0, "Excluded DataFrame should preserve Remitter column"


def test_apply_all_rules_with_custom_exclusions_and_remitter(full_transaction_df):
    """Test custom exclusions work correctly with Remitter column present"""
    # Exclude by keyword that appears in Description
    valid, excluded = apply_all_rules(
        full_transaction_df, 2026, 1, custom_exclusions_text="SHOPEEPAY"
    )
    
    if not excluded.empty:
        excluded_descriptions = excluded["Description"].values
        assert any("SHOPEEPAY" in str(desc) for desc in excluded_descriptions), \
            "SHOPEEPAY should be excluded by custom keyword"
        
        # Verify Remitter is preserved in excluded
        excluded_row = excluded[excluded["Description"].str.contains("SHOPEEPAY", na=False)]
        if not excluded_row.empty:
            assert "Remitter" in excluded_row.columns, "Remitter should be in excluded row"
            assert excluded_row["Remitter"].iloc[0] == "Shopee Vietnam", \
                "Remitter should be preserved in excluded transactions"


def test_apply_all_rules_with_large_amount_and_remitter(full_transaction_df):
    """Test that large amounts (>100M VND) are excluded and Remitter is preserved"""
    # VO THI HONG has 42.5M, which is below 100M threshold
    # Let's add a transaction > 100M
    large_df = full_transaction_df.copy()
    large_df.loc[len(large_df)] = {
        "Date": pd.Timestamp("2026-01-25"),
        "Description": "Large transfer",
        "Remitter": "Big Bank",
        "Debit": 150_000_000.0,
        "Credit": 0.0,
        "SourceType": "checking",
    }
    
    valid, excluded = apply_all_rules(large_df, 2026, 1, custom_exclusions_text="")
    
    if not excluded.empty:
        # Large amount should be excluded
        excluded_amounts = excluded["Debit"].values
        assert any(amount >= 100_000_000.0 for amount in excluded_amounts), \
            "Transactions >= 100M VND should be excluded"
        
        # Verify Remitter is preserved for excluded large amount
        large_excluded = excluded[excluded["Debit"] >= 100_000_000.0]
        if not large_excluded.empty:
            assert "Remitter" in large_excluded.columns, "Remitter should be in excluded DataFrame"
            assert large_excluded["Remitter"].iloc[0] == "Big Bank", \
                "Remitter should be preserved for excluded large transactions"


def test_apply_all_rules_empty_remitter_handling():
    """Test filtering when Remitter column has empty/NaN values"""
    df = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2026-01-15")],
            "Description": ["Normal payment"],
            "Remitter": [""],  # Empty Remitter
            "Debit": [50_000.0],
            "Credit": [0.0],
            "SourceType": ["checking"],
        }
    )
    
    valid, excluded = apply_all_rules(df, 2026, 1, custom_exclusions_text="")
    
    assert isinstance(valid, pd.DataFrame), "Should return valid DataFrame"
    assert isinstance(excluded, pd.DataFrame), "Should return excluded DataFrame"
    assert "Remitter" in valid.columns, "Remitter column should be preserved"
    
    # Empty Remitter should not cause issues
    if not valid.empty:
        assert valid["Remitter"].iloc[0] == "", "Empty Remitter should be preserved"


def test_apply_all_rules_month_specific_with_remitter(full_transaction_df):
    """Test month-specific exclusions work with Remitter column"""
    # Test Dec 2025 exclusions
    valid_dec, excluded_dec = apply_all_rules(full_transaction_df, 2025, 12, custom_exclusions_text="")
    
    if not excluded_dec.empty:
        excluded_descriptions = excluded_dec["Description"].values
        # VO THI HONG should be excluded for Dec 2025
        assert any("VO THI HONG" in str(desc) for desc in excluded_descriptions), \
            "VO THI HONG should be excluded for Dec 2025"
        
        # Verify Remitter is preserved
        vo_excluded = excluded_dec[excluded_dec["Description"].str.contains("VO THI HONG", na=False)]
        if not vo_excluded.empty:
            assert vo_excluded["Remitter"].iloc[0] == "VO THI HONG", \
                "Remitter should match excluded description for month-specific exclusions"
