"""
Shared constants for the expense tracker app and PDF parser.
"""

# Standard DataFrame columns for transaction data (order used in CSV/display). Immutable.
TRANSACTION_COLUMNS = ("Date", "Description", "Debit", "Credit", "SourceType")

# UI: column names required for valid expenses table to render
REQUIRED_VALID_EXPENSE_COLUMNS = frozenset({"Debit", "Credit", "Date", "Description"})

# UI: display column order for Valid Expenses data_editor
VALID_EXPENSE_DISPLAY_COLUMNS = (
    "Count as Expense",
    "Date",
    "Description",
    "Debit (VND)",
    "Credit (VND)",
    "SourceType",
)

# UI: display columns for Excluded table
EXCLUDED_TABLE_DISPLAY_COLUMNS = ("Date", "Description", "Debit (VND)", "SourceType")
