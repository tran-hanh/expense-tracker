"""
Techcombank Bank Statement Expense Analyzer — Streamlit UI.
Upload PDFs, apply filtering rules, view monthly expense report with dynamic exclusions.
"""

import re

import pandas as pd
import streamlit as st

from src.core.constants import (
    EXCLUDED_TABLE_DISPLAY_COLUMNS,
    REQUIRED_VALID_EXPENSE_COLUMNS,
    TRANSACTION_COLUMNS,
    VALID_EXPENSE_DISPLAY_COLUMNS,
)
from src.core.filter_rules import apply_all_rules
from src.services.pdf_parser import load_pdfs_to_dataframe

# --- Page config ---
st.set_page_config(page_title="Expense Tracker", page_icon="📊", layout="wide", initial_sidebar_state="expanded")


def init_session_state() -> None:
    """Initialize session state keys for raw data, filtered tables, and reactive total."""
    if "raw_all" not in st.session_state:
        st.session_state.raw_all = None
    if "valid_df" not in st.session_state:
        st.session_state.valid_df = None
    if "excluded_df" not in st.session_state:
        st.session_state.excluded_df = None
    if "display_total" not in st.session_state:
        st.session_state.display_total = None


def format_vnd(value: float) -> str:
    """Format number as Vietnamese currency (e.g. 10,000,000 VND)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "0 VND"
    return f"{int(value):,} VND"


def _format_cell_vnd(value: float) -> str:
    """Format a single numeric cell for table display (thousands separator, no unit)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return f"{int(value):,}"


def parse_month_year_filter(option: str) -> tuple[int, int] | None:
    """Parse 'MM/YYYY' or 'YYYY-MM' into (year, month)."""
    if not option:
        return None
    m = re.match(r"(\d{1,2})/(\d{4})", option)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.match(r"(\d{4})-(\d{1,2})", option)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def get_month_options() -> list[str]:
    """Build list of month/year options for the dropdown (from raw_all or defaults)."""
    raw = st.session_state.raw_all
    if raw is not None and not raw.empty and "Date" in raw.columns:
        df = raw.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        dates = df["Date"].dropna()
        if not dates.empty:
            periods = sorted(
                dates.dt.to_period("M").unique(),
                key=lambda p: (p.year, p.month),
                reverse=True,
            )
            return [f"{ts.month:02d}/{ts.year}" for ts in periods]
    _default_years = (2026, 2025)
    return [f"{m:02d}/{y}" for y in _default_years for m in range(12, 0, -1)]


def get_sidebar_inputs() -> tuple[list[tuple[bytes, str]], str]:
    """Collect uploaded files (bytes, source_type) and custom exclusions text. Returns (files_with_type, custom_exclusions)."""
    st.sidebar.header("Upload statements")
    st.sidebar.caption("Use one or both: Checking only, Credit card only, or both.")
    st.sidebar.subheader("Checking account PDFs")
    checking_files = st.sidebar.file_uploader(
        "Checking account statements",
        type=["pdf"],
        accept_multiple_files=True,
        key="checking_upload",
    )
    st.sidebar.subheader("Credit card PDFs")
    credit_files = st.sidebar.file_uploader(
        "Credit card statements",
        type=["pdf"],
        accept_multiple_files=True,
        key="credit_upload",
    )
    files_with_type: list[tuple[bytes, str]] = []
    if checking_files:
        for f in checking_files:
            files_with_type.append((f.read(), "checking"))
    if credit_files:
        for f in credit_files:
            files_with_type.append((f.read(), "credit_card"))
    st.sidebar.divider()
    st.sidebar.subheader("Custom exclusions")
    custom_exclusions = st.sidebar.text_input(
        "Custom exclusions (comma-separated)",
        placeholder="e.g. Nguyen Van A, 15000000, tra tien nha",
        help="Keywords or exact amounts to exclude from expenses. Matches description or amount.",
    )
    return files_with_type, custom_exclusions or ""


def _cache_key(files: list[tuple[bytes, str]]) -> tuple[tuple[int, str], ...]:
    """Stable cache key from file content hashes and types (for st.cache_data)."""
    return tuple((hash(b), t) for b, t in files)


@st.cache_data(show_spinner=False)
def _load_pdfs_cached(_key: tuple, files: list[tuple[bytes, str]]) -> tuple[pd.DataFrame, list[tuple[int, str]]]:
    """Cached PDF loading; _key is content-based so same uploads avoid re-parsing."""
    return load_pdfs_to_dataframe(files)


def ensure_raw_all_loaded(files_with_type: list[tuple[bytes, str]]) -> bool:
    """
    If there are new uploads, parse PDFs and set session_state.raw_all.
    Returns True if we have raw_all (with at least one row or from previous load), False if parse failed or no data yet.
    """
    if files_with_type:
        with st.spinner("Parsing PDFs..."):
            raw_all, failed = _load_pdfs_cached(_cache_key(files_with_type), files_with_type)
        if failed:
            details = " — ".join(f"File {i + 1}: {msg}" for i, msg in failed)
            st.warning(
                f"**Could not parse {len(failed)} file(s).** {details} "
                "Check that the files are valid Techcombank statement PDFs (checking or credit card)."
            )
        st.session_state.raw_all = raw_all
        if raw_all.empty:
            if not failed:
                st.warning(
                    "No transactions extracted from the uploaded PDFs. "
                    "Check that the files are valid Techcombank statement PDFs."
                )
            st.session_state.raw_all = None
            return False
    return st.session_state.raw_all is not None and not st.session_state.raw_all.empty


def load_and_filter_data(
    year_month: tuple[int, int] | None,
    selected_month: str,
    custom_exclusions: str,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """
    Filter raw_all by selected month and apply rules. Requires session_state.raw_all already set.
    Returns (valid_df, excluded_df); either can be None or empty DataFrame.
    """
    raw_all = st.session_state.raw_all
    if raw_all is None or raw_all.empty:
        return st.session_state.valid_df, st.session_state.excluded_df
    if "Date" not in raw_all.columns:
        st.error("Transaction data is missing the Date column. Re-upload valid statement PDFs.")
        return st.session_state.valid_df, st.session_state.excluded_df

    raw_all = raw_all.copy()
    raw_all["Date"] = pd.to_datetime(raw_all["Date"], errors="coerce")
    raw_all = raw_all.dropna(subset=["Date"])
    if year_month:
        y, m = year_month
        raw_month = raw_all[(raw_all["Date"].dt.year == y) & (raw_all["Date"].dt.month == m)]
    else:
        raw_month = raw_all
        year_month = (
            (int(raw_month["Date"].iloc[0].year), int(raw_month["Date"].iloc[0].month))
            if not raw_month.empty
            else None
        )

    if raw_month.empty:
        st.info(f"No transactions in {selected_month}. Choose another month from the dropdown.")
        return pd.DataFrame(columns=TRANSACTION_COLUMNS), pd.DataFrame()

    valid, excluded = apply_all_rules(
        raw_month,
        year=year_month[0],
        month=year_month[1],
        desc_col="Description",
        amount_col="Debit",
        custom_exclusions_text=custom_exclusions,
    )
    if "Count as Expense" not in valid.columns:
        valid = valid.copy()
        valid.insert(0, "Count as Expense", True)
    st.session_state.valid_df = valid
    st.session_state.excluded_df = excluded
    st.session_state.display_total = None
    return valid, excluded


def render_kpis(display_total: float, credit_card_total: float) -> None:
    """Render Top KPI cards: Total Monthly Expense and Total Credit Card Expense."""
    k1, k2 = st.columns(2)
    with k1:
        st.metric("Total Monthly Expense", format_vnd(display_total))
    with k2:
        st.metric("Total Credit Card Expense", format_vnd(credit_card_total))


def _totals_from_count_as_expense_mask(
    valid_df: pd.DataFrame, mask: pd.Series | None
) -> tuple[float, float]:
    """
    Compute (total_monthly_expense, credit_card_expense) from valid_df and Count-as-Expense mask.
    mask: True = count row, False = exclude. Same length as valid_df. Used by UI and tests.
    """
    if mask is None or len(mask) != len(valid_df):
        mask_arr = pd.Series(True, index=valid_df.index)
    else:
        mask_arr = pd.Series(mask, index=valid_df.index).fillna(True).astype(bool)
    total = (valid_df["Debit"].values * mask_arr.values).sum()
    is_cc = (valid_df["SourceType"] == "credit_card").values
    cc_total = (valid_df["Debit"].values * (mask_arr.values & is_cc)).sum()
    return float(total), float(cc_total)


def _render_expense_editor_and_totals() -> None:
    """
    Render Valid Expenses table and KPIs. Uses data_editor return value so total updates
    on first checkbox change (no fragment = full rerun with current widget value).
    """
    valid_df = st.session_state.valid_df
    if valid_df is None or valid_df.empty:
        return
    if not REQUIRED_VALID_EXPENSE_COLUMNS.issubset(valid_df.columns):
        missing = REQUIRED_VALID_EXPENSE_COLUMNS - set(valid_df.columns)
        st.error(f"Valid expenses table is missing columns: {missing}. Cannot render.")
        return
    st.subheader("Valid Expenses")
    st.caption("Uncheck 'Count as Expense' to exclude a row from the total.")
    display_valid = valid_df.copy()
    display_valid["Debit (VND)"] = display_valid["Debit"].apply(_format_cell_vnd)
    display_valid["Credit (VND)"] = display_valid["Credit"].apply(
        lambda x: _format_cell_vnd(x) if x and x > 0 else ""
    )
    display_columns = [c for c in VALID_EXPENSE_DISPLAY_COLUMNS if c in display_valid.columns]
    edited_returned = st.data_editor(
        display_valid[display_columns],
        width="stretch",
        column_config={
            "Count as Expense": st.column_config.CheckboxColumn("Count as Expense", default=True),
            "Date": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY"),
            "Description": st.column_config.TextColumn("Description", width="large"),
            "Remitter": st.column_config.TextColumn("Remitter"),
            "Debit (VND)": st.column_config.TextColumn("Debit (VND)"),
            "Credit (VND)": st.column_config.TextColumn("Credit (VND)"),
            "SourceType": st.column_config.TextColumn("Source Type"),
        },
        key="valid_expenses_editor",
    )
    edited = edited_returned if isinstance(edited_returned, pd.DataFrame) else display_valid[display_columns].copy()
    if "Count as Expense" not in edited.columns:
        return
    mask = edited["Count as Expense"]
    if len(mask) != len(valid_df):
        return
    st.session_state.valid_df["Count as Expense"] = mask.values
    total_from_checkboxes, credit_card_total = _totals_from_count_as_expense_mask(valid_df, mask)
    st.session_state.display_total = total_from_checkboxes
    st.caption(f"**Total from checked rows:** {format_vnd(total_from_checkboxes)}")
    render_kpis(total_from_checkboxes, credit_card_total)


def render_excluded_table(excluded_df: pd.DataFrame | None) -> None:
    """Render Excluded Transactions table (or info message if empty)."""
    st.subheader("Excluded Transactions")
    st.caption("Transactions ignored by the filtering rules (for transparency).")
    if excluded_df is not None and not excluded_df.empty:
        required_excluded = {"Debit", "Date", "Description"}
        if not required_excluded.issubset(excluded_df.columns):
            st.warning(f"Excluded table is missing columns: {required_excluded - set(excluded_df.columns)}. Showing raw table.")
            st.dataframe(excluded_df, width="stretch")
            return
        display_excluded = excluded_df.copy()
        display_excluded["Debit (VND)"] = display_excluded["Debit"].apply(_format_cell_vnd)
        display_excluded["Date"] = pd.to_datetime(display_excluded["Date"], errors="coerce")
        disp_cols = [c for c in EXCLUDED_TABLE_DISPLAY_COLUMNS if c in display_excluded.columns]
        st.dataframe(
            display_excluded[disp_cols],
            width="stretch",
            column_config={
                "Date": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY"),
                "Description": st.column_config.TextColumn("Description", width="large"),
                "Remitter": st.column_config.TextColumn("Remitter"),
            },
        )
    else:
        st.info("No excluded transactions for this period.")


def main() -> None:
    init_session_state()

    st.title("Bank Statement Expense Analyzer")
    st.caption("Upload Techcombank PDFs (Checking & Credit Card), filter by rules, and view monthly living expenses.")

    files_with_type, custom_exclusions = get_sidebar_inputs()

    # Parse uploads first so the month dropdown shows only months that have data
    if not ensure_raw_all_loaded(files_with_type):
        if not files_with_type and st.session_state.raw_all is None:
            st.info("Upload Checking and/or Credit card PDF statements in the sidebar to get started.")
        return

    month_options = get_month_options()
    selected_month = st.selectbox("Month / Year", options=month_options, key="month_filter")
    year_month = parse_month_year_filter(selected_month)

    valid_df, excluded_df = load_and_filter_data(year_month, selected_month, custom_exclusions)

    if valid_df is None:
        valid_df = st.session_state.valid_df
    if excluded_df is None:
        excluded_df = st.session_state.excluded_df

    if valid_df is None or valid_df.empty:
        st.info("No valid expenses for the selected period. Try another month from the dropdown, or upload Checking and/or Credit card PDFs.")
        return

    st.divider()
    _render_expense_editor_and_totals()
    # First load: total not yet set by editor; show from valid_df
    if st.session_state.display_total is None:
        total = (
            valid_df.loc[valid_df["Count as Expense"].fillna(True), "Debit"].sum()
            if "Count as Expense" in valid_df.columns
            else valid_df["Debit"].sum()
        )
        cc_total = valid_df[valid_df["SourceType"] == "credit_card"]["Debit"].sum()
        render_kpis(total, cc_total)
    render_excluded_table(excluded_df)
