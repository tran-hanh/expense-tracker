# Adversarial Review: pdf_parser.py

**Task:** `_bmad/core/tasks/review-adversarial-general.xml`  
**Content reviewed:** `pdf_parser.py` (Techcombank PDF table extraction)  
**Content type:** Python module (bank statement parser)

---

## Findings (issues to fix or improve)

1. **Column mapping index corruption when retrying headers** — When `_map_headers(raw[0])` returns empty, the code retries with `_map_headers([h for h in headers if h])`. Filtering out falsy headers changes list length and indices, so the resulting `col_map` indices no longer align with the actual table columns (e.g. index 1 in the filtered list is not index 1 in the raw row). Rows from that page will have wrong values (e.g. Debit and Credit swapped or taken from wrong cells).

2. **Using first page’s column map for all pages** — `col_map_global` is set from the first page that yields a non-empty map and then reused for every subsequent page. If later pages have a different table layout (e.g. different column order or extra columns), the same column indices are applied and Debit/Credit/Date/Description can be read from the wrong cells, producing incorrect or zero amounts.

3. **“Largest table” heuristic can pick the wrong table** — `_extract_table_from_page` chooses the table with maximum `(len(x), len(x[0]))`. A large non-transaction table (e.g. fee schedule, terms, or summary) can win over the real transaction table. There is no check that the first row looks like a header (e.g. text) or that cells look like dates/amounts.

4. **Ambiguous “Amount” header** — DEBIT_ALIASES includes the generic token `"amount"`. A single column labeled only “Amount” or “Số tiền” is always mapped to Debit. Some statements use one “Amount” column with sign or separate in/out; such a column may be misclassified and all amounts treated as outflows.

5. **Vietnamese thousand-separator assumption in amount parsing** — `_parse_vnd_amount` strips `.` and `,` and parses the rest as an integer. If a source ever uses decimal notation (e.g. `1234.56`) the result would be wrong (e.g. 123456). The code does not document or enforce “VND has no decimal part,” and there is no sanity check (e.g. rejecting values with more than two decimal digits).

6. **Negative amounts and refunds dropped silently** — Debit is parsed with `_parse_vnd_amount` (which preserves `-`), but then `df = df[df["Debit"] > 0]` keeps only positive debits. Refunds or reversals (negative debit) are dropped with no logging or way to include them in reporting, which can understate net outflows.

7. **Date format ambiguity (DD/MM vs MM/DD)** — The regex assumes day first: `(\d{1,2})/(\d{1,2})/(\d{2,4})` → (d, mo, y). If Techcombank or a locale uses MM/DD/YYYY, dates would be wrong (e.g. 03/05/2026 interpreted as 3 May instead of 5 Mar). There is no config or hint for date order.

8. **Invalid or unparseable dates become None and rows are dropped upstream** — `_parse_date` catches `Exception` and returns `None`. The app then drops rows with null Date. Users get no indication that some rows were skipped due to date parsing failures; there is no logging or error reporting.

9. **Short or malformed rows produce zero amounts** — In `_table_to_rows`, if a row has fewer cells than the max column index in `col_map`, missing cells are simply absent. Later, `df["Debit"] = df["Debit"].apply(_parse_vnd_amount)` sees `None` and returns `0.0`. The row is then dropped by `Debit > 0`. A row that actually has a debit in a merged or mis-detected cell could be lost without any signal.

10. **No handling of merged or split table cells** — pdfplumber’s `extract_tables()` can return merged cells as repeated values or empty strings. The code does not normalize merged cells or handle tables where the transaction spans multiple rows; such rows may be duplicated, partially filled, or misaligned with the header.

11. **Failures in `load_pdfs_to_dataframe` are silent** — `except Exception: continue` swallows all errors (corrupted PDF, password-protected, wrong format, OOM). The user receives no message that a file failed; the result simply omits that file’s data, which can look like “no transactions” instead of “parse error.”

12. **Duplicate uploads produce duplicate transactions** — Concatenation is done without deduplication. Uploading the same PDF twice (or the same statement in two files) doubles those transactions in the combined DataFrame and inflates totals.

13. **No validation of input type for `extract_transactions_from_pdf`** — The function expects `pdf_bytes: bytes`. If the caller passes a file path (str) or None, pdfplumber will raise later with a less clear error. There is no upfront check or helpful message for wrong input type.

14. **Two-column transaction tables are ignored** — The condition `len(t[0]) >= 3` in `_extract_table_from_page` skips tables with only two columns. Some statement layouts might use “Date” and “Amount” (or “Description” and “Amount”) only; those tables would never be extracted.

15. **Description “nan” vs pandas NA** — `df["Description"].astype(str).replace("nan", "")` replaces the string `"nan"`. Values that are `pd.NA` or `None` become the string `"None"` when cast to str and are not replaced, so descriptions can show `"None"` in the UI.
