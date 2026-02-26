"""
One-off script to inspect sample PDFs: table structure per page and parser output.
Run from project root: python scripts/inspect_sample_pdfs.py
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pdfplumber

from src.services.pdf_parser import (
    _extract_table_from_page,
    _fallback_column_map,
    _map_headers,
    extract_transactions_from_pdf,
)

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"


def inspect_pdf(path: Path) -> None:
    print(f"\n{'='*60}\n{path.name}\n{'='*60}")
    with open(path, "rb") as f:
        pdf_bytes = f.read()

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            print(f"\n--- Page {page_num} ({len(tables)} table(s)) ---")
            if not tables:
                continue
            for ti, t in enumerate(tables):
                if not t:
                    continue
                header = t[0]
                col_map = _map_headers(header)
                fallback = _fallback_column_map(header)
                chosen = col_map or fallback
                print(f"  Table {ti}: rows={len(t)}, cols={len(header)}")
                print(f"    Header: {header[:6]}...")
                print(f"    _map_headers: {col_map}")
                print(f"    fallback: {fallback}")
                print(f"    chosen: {chosen}")
                # First 2 data rows
                for row in t[1:4]:
                    print(f"    Row: {row[:6]}...")
            # What our extractor picks for this page
            raw = _extract_table_from_page(page)
            if raw:
                print(f"  _extract_table_from_page picked: {len(raw)} rows, header {raw[0][:5]}...")
            else:
                print("  _extract_table_from_page picked: (empty)")

    # Full parse and monthly counts
    df = extract_transactions_from_pdf(pdf_bytes, source_type="checking")
    print(f"\nParser output: {len(df)} rows total")
    if not df.empty and "Date" in df.columns:
        df = df.copy()
        df["Date"] = df["Date"].astype("datetime64[ns]")
        for (y, m), g in df.groupby([df["Date"].dt.year, df["Date"].dt.month]):
            print(f"  {y}-{m:02d}: {len(g)} transactions")


def main():
    if not SAMPLES_DIR.is_dir():
        print(f"No samples dir: {SAMPLES_DIR}")
        return
    for p in sorted(SAMPLES_DIR.glob("*.pdf")):
        try:
            inspect_pdf(p)
        except Exception as e:
            print(f"Error {p.name}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
