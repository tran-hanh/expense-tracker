# Adversarial Review: src/

**Task:** `_bmad/core/tasks/review-adversarial-general.xml`  
**Content reviewed:** Entire `src/` package (core, services, ui)  
**Content type:** Python source code (package)

---

## Findings

1. **constants.py — TRANSACTION_COLUMNS is mutable.** It is defined as a list; any code that mutates it (e.g. append) affects all consumers. Should be a tuple (or otherwise immutable) to prevent accidental mutation.

2. **filter_rules.py — GLOBAL_INCLUSION_KEYWORDS is dead code.** The constant is defined and documented as "explicitly count as expenses" but is never referenced in the module. Misleads maintainers and suggests unimplemented inclusion logic.

3. **filter_rules.py — Unused parameter in apply_month_specific_exclusions.** The function accepts `amount_col` but never uses it. Signature is misleading and suggests amount-based logic that does not exist.

4. **pdf_parser.py — _parse_vnd_amount silently normalizes all failures to 0.0.** On ValueError (or any invalid input after the try block) the function returns 0.0. Invalid numeric strings are indistinguishable from legitimate zero; there is no logging or way to detect parse failures.

5. **pdf_parser.py — Broad exception handling in _parse_date.** Both try/except blocks catch generic Exception and return None. Unexpected errors (e.g. memory, system) are swallowed with only a debug log, making production debugging harder.

6. **pdf_parser.py — Continuation-page column map reuse assumes identical layout.** When reusing last_col_map for a page with no recognized header, the code assumes column order and meaning are unchanged. If a later page has reordered or different columns, data will be misassigned with no warning or validation.

7. **pdf_parser.py — load_pdfs_to_dataframe hides failure details from callers.** Failed files are only logged; the returned DataFrame gives no indication of which files were skipped or how many failed. Callers cannot surface or act on partial failure.

8. **ui/app.py — format_vnd contains a no-op replace.** The expression `.replace(",", ",")` does nothing. Suggests incomplete localization or copy-paste; if a different thousands separator was intended, it is not implemented.

9. **ui/app.py — No defensive check for Date column.** get_month_options and load_and_filter_data assume st.session_state.raw_all (or raw_all) has a "Date" column. If the schema is wrong or the DataFrame is corrupted, KeyError will be raised with no clear message or guard.

10. **ui/app.py — No caching of parsed PDFs.** On every Streamlit rerun, uploaded files are re-read and re-parsed. For multiple or large PDFs this repeats expensive work with no cache keyed by file identity or content.

11. **core/__init__.py — Incomplete package surface.** Only TRANSACTION_COLUMNS and apply_all_rules are exported. Other public functions in filter_rules (e.g. apply_global_exclusions, apply_custom_exclusions) are not in __all__, so the public API is inconsistent for callers who need finer-grained control.

12. **ui/app.py — Display tables assume fixed schema.** render_valid_expenses_table and render_excluded_table build display DataFrames using columns such as "Debit (VND)" and "SourceType". If the source DataFrame is missing any of these (e.g. after a filter change or schema evolution), KeyError or missing columns can occur without validation or user-facing error handling.
