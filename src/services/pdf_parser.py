"""
Extract transaction tables from Techcombank (and similar) PDF bank statements.
Standardizes columns to: Date, Description, Debit (Outflow), Credit (Inflow).

VND amounts are assumed to have no decimal part; thousand separators may be . or ,.
"""

import io
import logging
import re
from typing import Literal

import pandas as pd
import pdfplumber

from src.core.constants import TRANSACTION_COLUMNS

logger = logging.getLogger(__name__)

# Column name normalization: various PDF headers -> standard names.
# Avoid generic "amount" alone so single "Amount" column is not forced to Debit.
DATE_ALIASES = ["date", "ngày", "ngay", "ngày giao dịch", "transaction date"]
DESC_ALIASES = ["description", "nội dung", "noi dung", "diễn giải", "dien giai", "details", "chi tiết", "chi tiet", "content"]
REMITTER_ALIASES = ["remitter", "đối tác", "doi tac", "partner", "người chuyển", "nguoi chuyen"]
# Headers that mean "Remitter Bank" (NH Đối tác) — do not map these to Remitter.
REMITTER_BANK_INDICATORS = ["remitter bank", "nh đối tác", "nh doi tac", "ngân hàng đối tác", "ngan hang doi tac"]


def _is_remitter_bank_header(normalized: str) -> bool:
    """True if this header is the Remitter Bank column (NH Đối tác), not the Remitter (partner) column."""
    return any(ind in normalized for ind in REMITTER_BANK_INDICATORS)


DEBIT_ALIASES = ["debit", "ghi nợ", "ghi no", "số tiền ghi nợ", "outflow", "phát sinh nợ", "phat sinh no", "ghi nợ (vnđ)", "nợ tktt"]
CREDIT_ALIASES = ["credit", "ghi có", "ghi co", "số tiền ghi có", "inflow", "phát sinh có", "phat sinh co", "ghi có (vnđ)", "có tktt"]


def _normalize_header(h: str) -> str:
    if h is None or (isinstance(h, str) and not str(h).strip()):
        return ""
    s = str(h).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _parse_vnd_amount(val) -> float:
    """
    Parse VND amount. VND has no decimal part; . and , are thousand separators.
    Supports negative (e.g. refunds). Rejects decimal-style values (e.g. 1234.56).
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return 0.0
    negative = s.lstrip().startswith("-")
    s = re.sub(r"[^\d.,\-]", "", s).lstrip("-")
    # If it looks like decimal (one . or , with 1-2 digits after), parse as float
    if re.search(r"^[0-9,.]*[.,]\d{1,2}$", s) and s.count(".") + s.count(",") == 1:
        try:
            v = float(s.replace(",", "."))
            return -v if negative else v
        except ValueError:
            pass
    # Thousand separators only
    s = s.replace(".", "").replace(",", "")
    try:
        return -float(s) if negative else float(s)
    except ValueError:
        logger.debug("VND amount parse failed for %r, treating as 0", val)
        return 0.0


def _parse_date(val, day_first: bool = True) -> pd.Timestamp | None:
    """
    Parse date; assumes DD/MM/YYYY when day_first=True (Vietnam/Techcombank default).
    Returns None on failure (caller may log).
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s:
        return None
    m = re.match(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", s)
    if m:
        g1, g2, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        d, mo = (g1, g2) if day_first else (g2, g1)
        try:
            return pd.Timestamp(year=y, month=mo, day=d)
        except (ValueError, TypeError) as e:
            logger.debug("Date parse failed for %r: %s", val, e)
            return None
    try:
        return pd.to_datetime(val)
    except (ValueError, TypeError) as e:
        logger.debug("Date parse failed for %r: %s", val, e)
        return None


def _map_headers(headers: list) -> dict[int, str]:
    """Map column index to standard name. Uses original header text when possible."""
    mapping = {}
    for i, h in enumerate(headers):
        n = _normalize_header(h)
        if not n:
            continue
        for alias, std in [
            (DATE_ALIASES, "Date"),
            (DESC_ALIASES, "Description"),
            (REMITTER_ALIASES, "Remitter"),
            (DEBIT_ALIASES, "Debit"),
            (CREDIT_ALIASES, "Credit"),
        ]:
            if any(a in n for a in alias):
                if std == "Remitter" and _is_remitter_bank_header(n):
                    continue  # Map Remitter Bank column to something else or leave unmapped
                mapping[i] = std
                break
    return mapping


def _fallback_column_map(headers: list) -> dict[int, str]:
    """
    Fallback column mapping when we can't recognize headers from aliases.
    Assumes a common layout: Date, Description, Debit, Credit in the first columns.
    This is intentionally conservative and only used when _map_headers() finds nothing.
    """
    if not headers:
        return {}
    ncols = len(headers)
    mapping: dict[int, str] = {}
    if ncols >= 1:
        mapping[0] = "Date"
    if ncols >= 2:
        mapping[1] = "Description"
    if ncols >= 3:
        mapping[2] = "Debit"
    if ncols >= 4:
        mapping[3] = "Credit"
    return mapping


def _transaction_map_complete(col_map: dict[int, str]) -> bool:
    """True if col_map has at least Date and Debit (required to keep transaction rows)."""
    vals = set(col_map.values()) if col_map else set()
    return "Date" in vals and "Debit" in vals


def _first_row_looks_like_data(headers: list) -> bool:
    """True if first row looks like a data row (e.g. first cell is date-like), not a header."""
    if not headers or not headers[0]:
        return False
    first_cell = str(headers[0]).strip()
    return bool(re.match(r"^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}", first_cell))


def _looks_like_header_row(row: list) -> bool:
    """True if row looks like a header (mostly non-numeric text)."""
    if not row:
        return False
    numeric = 0
    for cell in row:
        if cell is None:
            continue
        s = str(cell).strip()
        if s and re.match(r"^[\d.,\s\-]+$", s):
            numeric += 1
    return numeric <= len(row) // 2


def _score_table_as_transactions(raw_table: list[list]) -> float:
    """
    Score how likely this table is the transaction table (not fee schedule/terms).
    Higher = better. Uses: header-like first row, enough columns, multiple data rows.
    """
    if not raw_table or len(raw_table) < 2:
        return 0.0
    header = raw_table[0]
    ncols = len(header) if header else 0
    if ncols < 2:
        return 0.0
    score = 0.0
    if _looks_like_header_row(header):
        score += 10.0
    # Prefer 3+ columns (Date, Description, Debit/Credit)
    if ncols >= 3:
        score += 5.0
    elif ncols >= 2:
        score += 2.0
    score += min(len(raw_table) - 1, 20) * 0.5
    return score


def _extract_table_from_page(page) -> list[list]:
    """
    Extract the best transaction-like table from the page.
    Allows 2+ column tables; picks by transaction score. On continuation pages
    where the first row may not look like a header, falls back to the largest
    table so all pages are processed.
    """
    tables = page.extract_tables()
    if not tables:
        return []
    best_table: list[list] = []
    best_score = 0.0
    # Fallback: largest table by (rows, cols) when no table scores (e.g. continuation page with no header row)
    fallback_table: list[list] = []
    fallback_size = (0, 0)
    for t in tables:
        if not t or len(t) < 2:
            continue
        ncols = len(t[0]) if t[0] else 0
        if ncols < 2:
            continue
        score = _score_table_as_transactions(t)
        if score > best_score:
            best_score = score
            best_table = t
        # Keep largest table as fallback so we never skip a page with table data
        size = (len(t), ncols)
        if size > fallback_size:
            fallback_size = size
            fallback_table = t
    return best_table if best_table else fallback_table


def _table_to_rows(raw_table: list[list], col_map: dict) -> list[dict]:
    """
    Convert raw table rows to list of dicts using col_map.
    Rows are padded to header length so column indices stay aligned; missing cells become None.
    """
    if not raw_table or not col_map:
        return []
    headers = raw_table[0]
    ncols = len(headers)
    rows = []
    for r in raw_table[1:]:
        if not r:
            continue
        # Pad so we don't misalign when row is shorter than header (e.g. merged cells)
        r_padded = (list(r) + [None] * (ncols - len(r)))[:ncols]
        row = {}
        for i, std_name in col_map.items():
            if i < len(r_padded) and std_name:
                row[std_name] = r_padded[i]
        if row:
            rows.append(row)
    return rows


def extract_transactions_from_pdf(
    pdf_bytes: bytes,
    source_type: Literal["checking", "credit_card"] = "checking",
    day_first: bool = True,
) -> pd.DataFrame:
    """
    Extract transaction table from a single PDF file.
    pdf_bytes must be bytes (not path or None).
    Returns DataFrame with columns: Date, Description, Debit, Credit, SourceType.
    Keeps rows with non-zero Debit (positive = outflow, negative = refund); zero-Debit rows dropped.
    """
    if not isinstance(pdf_bytes, bytes):
        raise TypeError(f"pdf_bytes must be bytes, got {type(pdf_bytes).__name__}")
    if not pdf_bytes:
        raise ValueError("pdf_bytes must not be empty")

    all_rows = []
    last_col_map: dict[int, str] | None = None
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            raw = _extract_table_from_page(page)
            if not raw:
                continue
            headers = raw[0]
            ncols = len(headers) if headers else 0
            # Continuation page: first row is data (e.g. date in first cell), not a header. Reuse previous map.
            if last_col_map and ncols >= len(last_col_map) and _first_row_looks_like_data(headers):
                logger.debug("Continuation page (date-like first cell), reusing previous column map, ncols=%s", ncols)
                col_map = {i: last_col_map[i] for i in last_col_map if i < ncols}
            else:
                col_map = _map_headers(headers) or _fallback_column_map(headers)
                # Partial/false match (e.g. only {3: 'Date'} from "ngay" in description): reuse last map if complete.
                if last_col_map and ncols >= len(last_col_map) and not _transaction_map_complete(col_map):
                    logger.debug("Reusing previous page column map (incomplete or false match), ncols=%s", ncols)
                    col_map = {i: last_col_map[i] for i in last_col_map if i < ncols}
            if not col_map or not _transaction_map_complete(col_map):
                continue
            last_col_map = col_map
            for row_dict in _table_to_rows(raw, col_map):
                all_rows.append(row_dict)

    if not all_rows:
        return pd.DataFrame(columns=TRANSACTION_COLUMNS)

    df = pd.DataFrame(all_rows)
    rename = {}
    for c in df.columns:
        n = _normalize_header(c)
        for alias, std in [
            (DATE_ALIASES, "Date"),
            (DESC_ALIASES, "Description"),
            (REMITTER_ALIASES, "Remitter"),
            (DEBIT_ALIASES, "Debit"),
            (CREDIT_ALIASES, "Credit"),
        ]:
            if any(a in n for a in alias):
                if std == "Remitter" and _is_remitter_bank_header(n):
                    continue
                rename[c] = std
                break
    df = df.rename(columns=rename)

    for col in ["Date", "Description", "Remitter", "Debit", "Credit"]:
        if col not in df.columns:
            df[col] = None

    df["Debit"] = df["Debit"].apply(_parse_vnd_amount)
    df["Credit"] = df["Credit"].apply(_parse_vnd_amount)
    df["Date"] = df["Date"].apply(lambda v: _parse_date(v, day_first=day_first))
    _str_col = lambda x: "" if pd.isna(x) or x is None or str(x).strip().lower() in ("nan", "none") else str(x)
    df["Description"] = df["Description"].apply(_str_col)
    df["Remitter"] = df["Remitter"].apply(_str_col)

    # Keep rows with non-zero Debit (outflows and refunds)
    df = df[df["Debit"] != 0].copy()
    df["SourceType"] = source_type
    return df[list(TRANSACTION_COLUMNS)]


def load_pdfs_to_dataframe(
    files: list[tuple[bytes, Literal["checking", "credit_card"]]],
    deduplicate: bool = True,
) -> tuple[pd.DataFrame, list[tuple[int, str]]]:
    """
    Load multiple PDFs and concatenate into one DataFrame.
    files: list of (pdf_bytes, source_type).
    Returns (dataframe, failed_files) where failed_files is list of (index, error_message) for callers to display.
    If deduplicate is True, drops duplicate rows (Date, Description, Debit, Credit, SourceType).
    """
    if not files:
        return pd.DataFrame(columns=TRANSACTION_COLUMNS), []
    dfs = []
    failed: list[tuple[int, str]] = []
    for i, (pdf_bytes, source_type) in enumerate(files):
        try:
            if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
                msg = f"Invalid or empty file (got {type(pdf_bytes).__name__})"
                logger.warning("File index %s: %s", i, msg)
                failed.append((i, msg))
                continue
            df = extract_transactions_from_pdf(pdf_bytes, source_type=source_type)
            if not df.empty:
                dfs.append(df)
            else:
                failed.append((i, "No transaction table found or no debit rows in this PDF"))
        except Exception as e:
            msg = str(e).strip() or type(e).__name__
            logger.warning("File index %s failed to parse: %s", i, e)
            failed.append((i, msg))
            continue
    if not dfs:
        return pd.DataFrame(columns=TRANSACTION_COLUMNS), failed
    out = pd.concat(dfs, ignore_index=True)
    if deduplicate and not out.empty:
        subset = [c for c in TRANSACTION_COLUMNS if c in out.columns]
        out = out.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)
    return out, failed
