# Project Standards — Expense Tracker

**Project:** Expense Tracker  
**Configured:** 2026-02-25  
**Output folder:** `_bmad-output` (from `_bmad/core/config.yaml`)

---

## 1. Cursor Rules

Project standards are enforced via Cursor rules in `.cursor/rules/`. Rules are applied automatically when matching files are open (or always, if `alwaysApply: true`).

| Rule file | Scope | Purpose |
|-----------|--------|--------|
| **python-standards.mdc** | `**/*.py` | Type hints, docstrings, naming, shared constants, exception handling |
| **streamlit-app.mdc** | `app.py` | Session state init, sidebar usage, main() orchestration, data_editor persistence |
| **project-structure.mdc** | Always | Module boundaries: `src/ui` (UI), `src/services` (e.g. pdf_parser), `src/core` (filter_rules, constants) |

### Location

- `.cursor/rules/python-standards.mdc`
- `.cursor/rules/streamlit-app.mdc`
- `.cursor/rules/project-structure.mdc`

---

## 2. Conventions Summary

- **Python**: 3.10+, type hints on public APIs, snake_case, constants in `constants.py`.
- **Streamlit**: Single session-state init, sidebar for inputs, `main()` as orchestrator, persist widget state to session state.
- **Layout**: `src/ui` (UI), `src/core` (rules, constants), `src/services` (PDF parsing). No parsing in UI, no UI in services/core.

---

## 3. Adding or Changing Standards

- **New rule**: Add a `.mdc` file under `.cursor/rules/` with YAML frontmatter (`description`, `globs` or `alwaysApply`). Keep content concise (&lt; 50 lines per rule when possible).
- **Update this doc**: Edit `_bmad-output/PROJECT_STANDARDS.md` when adding/removing rules or changing conventions.
