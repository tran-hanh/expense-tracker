"""
Techcombank Bank Statement Expense Analyzer — Streamlit UI.
Upload PDFs, apply filtering rules, view monthly expense report with dynamic exclusions.
"""

import re

import pandas as pd
import streamlit as st

from src.core.constants import TRANSACTION_COLUMNS
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
    return f"{int(value):,} VND".replace(",", ",")


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
    if st.session_state.raw_all is not None and not st.session_state.raw_all.empty:
        df = st.session_state.raw_all.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        dates = df["Date"].dropna()
        if not dates.empty:
            periods = sorted(
                dates.dt.to_period("M").unique(),
                key=lambda p: (p.year, p.month),
                reverse=True,
            )
            return [f"{ts.month:02d}/{ts.year}" for ts in periods]
    return [f"{m:02d}/{y}" for y in [2026, 2025] for m in range(12, 0, -1)]


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


def ensure_raw_all_loaded(files_with_type: list[tuple[bytes, str]]) -> bool:
    """
    If there are new uploads, parse PDFs and set session_state.raw_all.
    Returns True if we have raw_all (with at least one row or from previous load), False if parse failed or no data yet.
    """
    if files_with_type:
        with st.spinner("Parsing PDFs..."):
            raw_all = load_pdfs_to_dataframe(files_with_type)
        st.session_state.raw_all = raw_all
        if raw_all.empty:
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


def render_kpis(valid_df: pd.DataFrame, display_total: float) -> None:
    """Render Top KPI cards: Total Monthly Expense and Total Credit Card Expense."""
    credit_card_expense = valid_df[valid_df["SourceType"] == "credit_card"]["Debit"].sum()
    k1, k2 = st.columns(2)
    with k1:
        st.metric("Total Monthly Expense", format_vnd(display_total))
    with k2:
        st.metric("Total Credit Card Expense", format_vnd(credit_card_expense))


def render_valid_expenses_table(valid_df: pd.DataFrame) -> None:
    """Render interactive Valid Expenses table with Count as Expense checkbox; persist state and update display_total."""
    st.subheader("Valid Expenses")
    st.caption("Uncheck 'Count as Expense' to exclude a row from the Total Monthly Expense.")
    display_valid = valid_df.copy()
    display_valid["Debit (VND)"] = display_valid["Debit"].apply(lambda x: f"{int(x):,}".replace(",", ","))
    display_valid["Credit (VND)"] = display_valid["Credit"].apply(
        lambda x: f"{int(x):,}".replace(",", ",") if x and x > 0 else ""
    )
    cols_show = [c for c in ["Count as Expense", "Date", "Description", "Debit (VND)", "Credit (VND)", "SourceType"] if c in display_valid.columns]
    edited = st.data_editor(
        display_valid[cols_show],
        use_container_width=True,
        column_config={
            "Count as Expense": st.column_config.CheckboxColumn("Count as Expense", default=True),
            "Date": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY"),
            "Description": st.column_config.TextColumn("Description", width="large"),
            "Debit (VND)": st.column_config.TextColumn("Debit (VND)"),
            "Credit (VND)": st.column_config.TextColumn("Credit (VND)"),
            "SourceType": st.column_config.TextColumn("Source Type"),
        },
        key="valid_expenses_editor",
    )
    if "Count as Expense" in edited.columns:
        mask = edited["Count as Expense"].fillna(True).values
        if len(mask) == len(valid_df):
            st.session_state.valid_df["Count as Expense"] = mask
            total_from_checkboxes = valid_df["Debit"].values[mask].sum()
            st.session_state.display_total = total_from_checkboxes
            st.caption(f"**Total from checked rows:** {format_vnd(total_from_checkboxes)}")


def render_excluded_table(excluded_df: pd.DataFrame | None) -> None:
    """Render Excluded Transactions table (or info message if empty)."""
    st.subheader("Excluded Transactions")
    st.caption("Transactions ignored by the filtering rules (for transparency).")
    if excluded_df is not None and not excluded_df.empty:
        display_excluded = excluded_df.copy()
        display_excluded["Debit (VND)"] = display_excluded["Debit"].apply(lambda x: f"{int(x):,}".replace(",", ","))
        display_excluded["Date"] = pd.to_datetime(display_excluded["Date"], errors="coerce")
        st.dataframe(
            display_excluded[["Date", "Description", "Debit (VND)", "SourceType"]],
            use_container_width=True,
            column_config={
                "Date": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY"),
                "Description": st.column_config.TextColumn("Description", width="large"),
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

    total_monthly_expense = (
        valid_df.loc[valid_df["Count as Expense"].fillna(True), "Debit"].sum()
        if "Count as Expense" in valid_df.columns
        else valid_df["Debit"].sum()
    )

    st.divider()
    # Render table first so checkbox state is available; then KPI uses current run's total
    render_valid_expenses_table(valid_df)
    display_total = (
        st.session_state.display_total
        if st.session_state.display_total is not None
        else total_monthly_expense
    )
    render_kpis(valid_df, display_total)
    render_excluded_table(excluded_df)
