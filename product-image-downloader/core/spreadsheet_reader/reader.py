"""Read product codes from Excel files and public Google Spreadsheets."""

from __future__ import annotations

import io
import logging
import re
from typing import List, Tuple

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# ── Column / row parsing ──────────────────────────────────────────────

def parse_column_index(col_letter: str) -> int:
    """Convert a column letter (A-Z, AA, AB …) to a 0-based index."""
    col_letter = col_letter.strip().upper()
    idx = 0
    for ch in col_letter:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def parse_row_spec(row_spec: str) -> List[int]:
    """Parse a row specification string into a list of 1-based row numbers.

    Supported formats:
        "5-8"     → [5, 6, 7, 8]
        "2,3,4"   → [2, 3, 4]
        "2, 5-7, 10" → [2, 5, 6, 7, 10]
    """
    rows: List[int] = []
    for part in row_spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s.strip()), int(end_s.strip())
            rows.extend(range(start, end + 1))
        else:
            rows.append(int(part))
    return rows


# ── Excel reader ──────────────────────────────────────────────────────

def read_excel(
    file_content: bytes,
    column: str,
    row_spec: str,
) -> List[str]:
    """Read product codes from specific cells of an Excel file.

    Args:
        file_content: Raw bytes of the .xlsx file.
        column: Column letter (e.g. "C").
        row_spec: Row specification (e.g. "5-8" or "2,3,4").

    Returns:
        List of non-empty string values from the specified cells.
    """
    col_idx = parse_column_index(column)
    rows = parse_row_spec(row_spec)

    df = pd.read_excel(io.BytesIO(file_content), header=None, dtype=str)
    values: List[str] = []

    for row_num in rows:
        # row_num is 1-based; DataFrame is 0-based
        r = row_num - 1
        if r < 0 or r >= len(df) or col_idx >= len(df.columns):
            logger.warning("Cell %s%d is out of range, skipping", column.upper(), row_num)
            continue
        val = df.iloc[r, col_idx]
        if pd.notna(val) and str(val).strip():
            values.append(str(val).strip())

    logger.info("Read %d product code(s) from Excel", len(values))
    return values


# ── Google Spreadsheet reader ─────────────────────────────────────────

def _extract_sheet_id(url: str) -> str:
    """Extract the spreadsheet ID from a Google Sheets URL."""
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        raise ValueError(f"Cannot extract spreadsheet ID from URL: {url}")
    return m.group(1)


def _extract_gid(url: str) -> str:
    """Extract gid (sheet tab) from URL, default '0'."""
    m = re.search(r"[#&?]gid=(\d+)", url)
    return m.group(1) if m else "0"


def read_google_sheet(
    url: str,
    column: str,
    row_spec: str,
) -> List[str]:
    """Read product codes from a *public* Google Spreadsheet.

    Converts the URL to a CSV export link and downloads it with pandas.

    Args:
        url: Full Google Sheets URL.
        column: Column letter (e.g. "D").
        row_spec: Row specification (e.g. "2-5").

    Returns:
        List of non-empty string values.
    """
    sheet_id = _extract_sheet_id(url)
    gid = _extract_gid(url)
    csv_url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )

    logger.info("Downloading Google Sheet as CSV: %s", csv_url)
    resp = requests.get(csv_url, timeout=30)
    resp.raise_for_status()

    col_idx = parse_column_index(column)
    rows = parse_row_spec(row_spec)

    df = pd.read_csv(io.StringIO(resp.text), header=None, dtype=str)
    values: List[str] = []

    for row_num in rows:
        r = row_num - 1
        if r < 0 or r >= len(df) or col_idx >= len(df.columns):
            logger.warning("Cell %s%d is out of range, skipping", column.upper(), row_num)
            continue
        val = df.iloc[r, col_idx]
        if pd.notna(val) and str(val).strip():
            values.append(str(val).strip())

    logger.info("Read %d product code(s) from Google Sheet", len(values))
    return values
