"""
Filtering rules for bank statement expense analysis.
Rule 3.1: Global exclusions. Rule 3.3: Month-specific exclusions.
(Rule 3.2 global inclusions reserved for future use.)
"""

import re

import pandas as pd

# --- Constants ---
MAX_SINGLE_TRANSACTION_VND = 100_000_000

# Rule 3.1: Global exclusion keywords (ignore entirely)
GLOBAL_EXCLUSION_KEYWORDS = [
    "PHAT LOC REAL ESTATE",
    "Sinh loi tu dong",
    "team bonding",
    "HOAN TRA LCT",
    "Thanh toan no the tin dung",
]

# Rule 3.3: Month-specific exclusions: (year, month) -> list of keywords.
# Exclude any transaction whose description contains any of these keywords.
MONTH_SPECIFIC_EXCLUSIONS = {
    (2025, 12): [
        "VO THI HONG",
        "TRAN TRUNG HIEU",
        "Dat Tran",
        "NGUYEN THI CAM TU",
        "Anh Dung",
        "VO QUOC CUONG",
    ],
    (2026, 1): [
        "LE THANH PHONG",
        "DUONG HUYNH BICH NGOC",
        "Anh Dung",
    ],
    (2026, 2): [
        "VU PHAM LOAN THAO",
        "TRANG THI KIEU DUYEN",
        "NGUYEN THI BAO TRANG",
        "TRAN TUAN DAT",
    ],
}


def _description_contains(desc: str, keyword: str) -> bool:
    if pd.isna(desc):
        return False
    return keyword.strip().upper() in str(desc).upper()


def _matches_custom_exclusion(desc: str, amount: float, custom_parts: list[str]) -> bool:
    """Check if transaction matches any custom exclusion (keyword or exact amount)."""
    if not desc and amount is None:
        return False
    desc_str = "" if pd.isna(desc) else str(desc).upper()
    for part in custom_parts:
        part = part.strip()
        if not part:
            continue
        # Try as number (exact amount match); support 15.000.000 or 15,000,000
        try:
            num_str = re.sub(r"[^\d\-]", "", part)
            if num_str:
                num = float(num_str)
                if amount is not None and abs(float(amount) - num) < 1:
                    return True
        except (ValueError, TypeError):
            pass
        # Keyword match
        if part.upper() in desc_str:
            return True
    return False


def apply_global_exclusions(df: pd.DataFrame, desc_col: str, amount_col: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply Rule 3.1: exclude rows that match global exclusion keywords or amount > 100M.
    Returns (included_df, excluded_df).
    """
    if df.empty:
        return df.copy(), pd.DataFrame()
    mask_exclude = pd.Series(False, index=df.index)
    # Amount > 100M
    mask_exclude |= (df[amount_col] > MAX_SINGLE_TRANSACTION_VND)
    for kw in GLOBAL_EXCLUSION_KEYWORDS:
        mask_exclude |= df[desc_col].apply(lambda x: _description_contains(x, kw))
    excluded = df[mask_exclude].copy()
    included = df[~mask_exclude].copy()
    return included, excluded


def apply_month_specific_exclusions(
    df: pd.DataFrame, year: int, month: int, desc_col: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply Rule 3.3: exclude transactions whose description contains any month-specific keyword.
    Returns (included_df, excluded_df) for that month's rules only.
    """
    if df.empty:
        return df.copy(), pd.DataFrame()
    keywords = MONTH_SPECIFIC_EXCLUSIONS.get((year, month), [])
    mask_exclude = pd.Series(False, index=df.index)
    for keyword in keywords:
        mask_exclude |= df[desc_col].apply(lambda x: _description_contains(x, keyword))
    excluded = df[mask_exclude].copy()
    included = df[~mask_exclude].copy()
    return included, excluded


def apply_custom_exclusions(
    df: pd.DataFrame, desc_col: str, amount_col: str, custom_text: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Exclude rows matching user-provided comma-separated keywords or exact amounts.
    Returns (included_df, excluded_df).
    """
    if df.empty or not (custom_text or "").strip():
        return df.copy(), pd.DataFrame()
    parts = [p.strip() for p in custom_text.split(",") if p.strip()]
    mask_exclude = df.apply(
        lambda row: _matches_custom_exclusion(row[desc_col], row[amount_col], parts),
        axis=1,
    )
    excluded = df[mask_exclude].copy()
    included = df[~mask_exclude].copy()
    return included, excluded


def apply_all_rules(
    df: pd.DataFrame,
    year: int,
    month: int,
    desc_col: str = "Description",
    amount_col: str = "Debit",
    custom_exclusions_text: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply global exclusions, then month-specific, then custom.
    Returns (valid_expenses_df, excluded_df).
    """
    if df.empty:
        return df.copy(), pd.DataFrame()
    all_excluded = []
    current = df.copy()

    # 1. Global exclusions
    current, excl1 = apply_global_exclusions(current, desc_col, amount_col)
    all_excluded.append(excl1)

    # 2. Month-specific
    current, excl2 = apply_month_specific_exclusions(current, year, month, desc_col)
    all_excluded.append(excl2)

    # 3. Custom
    current, excl3 = apply_custom_exclusions(current, desc_col, amount_col, custom_exclusions_text)
    all_excluded.append(excl3)

    excluded_combined = pd.concat([e for e in all_excluded if not e.empty], ignore_index=True) if any(not e.empty for e in all_excluded) else pd.DataFrame()
    if not excluded_combined.empty and not current.empty:
        # Deduplicate by index if we had same row in multiple steps (use first occurrence)
        excluded_combined = excluded_combined.drop_duplicates(keep="first")
    return current, excluded_combined
