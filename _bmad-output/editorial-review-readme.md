# Editorial Review: README.md

**Task:** Editorial Review - Prose  
**Content:** README.md  
**Reader type:** humans  

---

## Suggested fixes

| Original Text | Revised Text | Changes |
|--------------|--------------|---------|
| Configurable per month in `filter_rules.py` (Dec 2025, Jan 2026, Feb 2026). | Configurable per month in `src/core/filter_rules.py` (Dec 2025, Jan 2026, Feb 2026). | Use full path so it matches the repo layout and the "Adding new month-specific exclusions" section. |
| uncheck to exclude from Total Monthly Expense (KPI updates on change). | uncheck to exclude from Total Monthly Expense (KPIs update when you change checkboxes). | Clarify what updates and how. |
| or from the project root run: `HOME=$(pwd) streamlit run app.py` | or run this from the project root: `HOME=$(pwd) streamlit run app.py` | Avoid repeating "run"; makes the two options parallel. |
| Edit `src/core/filter_rules.py` and add entries to `MONTH_SPECIFIC_EXCLUSIONS`, e.g.:<br><br>```python<br>(2026, 3): [<br>    ("KEYWORD", [amount1, amount2]),  # exclude when description contains KEYWORD and amount in list<br>],<br>``` | Edit `src/core/filter_rules.py` and add entries to `MONTH_SPECIFIC_EXCLUSIONS`, e.g.:<br><br>```python<br>(2026, 3): [<br>    "KEYWORD",  # exclude when description contains this keyword<br>],<br>``` | Example matched the old format (keyword + amounts). The code uses keyword-only lists; revise example so it reflects current usage. |

---

*Review complete. Apply changes as needed.*
