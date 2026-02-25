# Bank Statement Expense Analyzer

A Streamlit app to parse Techcombank PDF statements (Checking + Credit Card), apply filtering rules, and compute monthly living expenses.

## Setup

```bash
cd expense_tracker
python3 -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
./run_streamlit.sh
# Or: streamlit run app.py
```

**If you see `PermissionError: [Errno 1] Operation not permitted: '/Users/.../.streamlit'`**  
Streamlit is trying to write to your home directory. Run with the script above (it sets `HOME` to the project so Streamlit uses `.streamlit/` inside the repo), or from the project root run: `HOME=$(pwd) streamlit run app.py`.

## Testing

Tests use pytest. Install dev dependencies and run from the project root:

```bash
pip install -r requirements-dev.txt
pytest
# Or with coverage:
pytest --cov=src --cov-report=term-missing
```

Tests live under `tests/`: `tests/unit/` for core and services. Run with `pytest tests/ -v`.

## Features

- **Upload PDFs**: Sidebar upload for Checking account and Credit card statements (multiple files each).
- **Standardized columns**: Date, Description, Debit (outflow), Credit (inflow); only outflows are used for expense totals.
- **Filtering rules**:
  - **Global exclusions**: Transactions > 100M VND; keywords (e.g. PHAT LOC REAL ESTATE, Sinh loi tu dong, team bonding, HOAN TRA LCT, Thanh toan no the tin dung).
  - **Month-specific exclusions**: Configurable per month in `filter_rules.py` (Dec 2025, Jan 2026, Feb 2026).
- **Custom exclusions**: Sidebar text input — comma-separated keywords or exact amounts — applied without code changes.
- **Interactive table**: "Valid Expenses" table has a "Count as Expense" checkbox per row; uncheck to exclude from Total Monthly Expense (KPI updates on change).
- **KPIs**: Total Monthly Expense (reactive to checkboxes), Total Credit Card Expense.
- **Transparency**: "Excluded Transactions" table lists all ignored transactions.

## Adding new month-specific exclusions

Edit `src/core/filter_rules.py` and add entries to `MONTH_SPECIFIC_EXCLUSIONS`, e.g.:

```python
(2026, 3): [
    ("KEYWORD", [amount1, amount2]),  # exclude when description contains KEYWORD and amount in list
],
```

## Tech stack

- Python 3.10+
- Streamlit, Pandas, pdfplumber
