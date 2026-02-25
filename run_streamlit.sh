#!/usr/bin/env bash
# Run Streamlit with HOME set to the project directory so Streamlit writes
# to .streamlit/ here instead of ~/.streamlit (avoids PermissionError in restricted environments).
set -e
cd "$(dirname "$0")"
# Use project dir as HOME so Streamlit writes to .streamlit/ here, not ~/.streamlit
export HOME="$(pwd)"
exec .venv/bin/streamlit run app.py "$@"
