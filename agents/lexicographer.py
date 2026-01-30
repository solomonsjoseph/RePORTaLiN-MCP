#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = ["pandas", "openpyxl"]
# ///
"""📖 The Lexicographer - Excel Data Dictionary to Markdown/JSONL Converter.

Mission: "Extract with 100% accuracy, convert to clean Markdown or JSONL."

Algorithm: 2D table detection (empty rows AND columns as boundaries)
- Ported from proven load_dictionary.py implementation

Usage:
    python lexicographer.py                           # Use default paths (JSONL)
    python lexicographer.py --format markdown         # Output as Markdown
    python lexicographer.py --xlsx path/to/file.xlsx  # Custom input
    python lexicographer.py --output dictionary/      # Custom output dir
    python lexicographer.py --dry-run                 # Preview without writing

Output Structure:
    dictionary/
    ├── Codelists/
    │   ├── Codelists_table_1.jsonl (or .md)
    │   └── extras/              # Tables after "ignore below"
    ├── tblENROL/
    │   └── tblENROL_table_1.jsonl (or .md)
    └── ...
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# =============================================================================
# Configuration (Shared Constants)
# =============================================================================
AGENT_NAME = "Lexicographer"
DEFAULT_XLSX = Path("data/raw/data_dictionary_and_mapping_specifications/RePORT_DEB_to_Tables_mapping.xlsx")
DEFAULT_OUTPUT = Path("dictionary")
IGNORE_MARKER = "ignore below"
EXTRAS_DIR = "extras"


# =============================================================================
# Utility: Clean Value to String
# =============================================================================
def _val_to_str(val: Any, escape_md: bool = False) -> str:
    """Convert cell value to clean string, optionally escape for Markdown.
    
    Handles: NaN, None, NaT, "nan", "none", "nat", "<na>", inf, floats-as-ints, and pipe escaping.
    """
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "nat", "<na>", "inf", "-inf"):
        return ""
    # Handle infinity
    try:
        import math
        if isinstance(val, float) and math.isinf(val):
            return ""
    except (TypeError, ValueError):
        pass
    # Float that is really an int → remove .0
    try:
        f = float(val)
        if not (f != f) and f == int(f):  # not NaN and is whole number
            s = str(int(f))
    except (ValueError, TypeError, OverflowError):
        pass
    if escape_md:
        s = s.replace("|", "\\|").replace("\n", "<br>")
    return s


# =============================================================================
# Core: 2D Table Detection (from proven load_dictionary.py)
# =============================================================================
def _deduplicate_columns(columns: list[Any]) -> list[str]:
    """Make column names unique: ['A', 'A', 'B'] → ['A', 'A_1', 'B']"""
    result, counts = [], {}
    for col in columns:
        col_str = str(col).strip() if pd.notna(col) and str(col).strip() else "Unnamed"
        if col_str.lower() == "nan":
            col_str = "Unnamed"
        if col_str in counts:
            counts[col_str] += 1
            result.append(f"{col_str}_{counts[col_str]}")
        else:
            counts[col_str] = 0
            result.append(col_str)
    return result


def _split_sheet_into_tables(df: pd.DataFrame) -> list[pd.DataFrame]:
    """Split DataFrame into tables using empty row/column boundaries.
    
    Algorithm:
    1. Find horizontal strips (separated by fully empty rows)
    2. Within each strip, find vertical segments (separated by fully empty columns)
    3. Each segment is a separate table
    """
    if df.empty:
        return []
    
    # Find empty rows → horizontal boundaries
    empty_rows = df.index[df.isnull().all(axis=1)].tolist()
    row_bounds = [-1] + empty_rows + [len(df)]
    
    # Extract horizontal strips
    strips = []
    for i in range(len(row_bounds) - 1):
        start, end = row_bounds[i] + 1, row_bounds[i + 1]
        if start < end:
            strips.append(df.iloc[start:end])
    
    # For each strip, find vertical segments (empty columns)
    tables = []
    for strip in strips:
        empty_cols = [i for i, col in enumerate(strip.columns) if strip[col].isnull().all()]
        col_bounds = [-1] + empty_cols + [len(strip.columns)]
        
        for j in range(len(col_bounds) - 1):
            start_c, end_c = col_bounds[j] + 1, col_bounds[j + 1]
            if start_c < end_c:
                table = strip.iloc[:, start_c:end_c].copy()
                table = table.dropna(how="all")  # Remove empty rows within table
                if not table.empty and len(table) >= 2:  # Need header + data
                    tables.append(table)
    
    return tables


def _check_ignore_marker(row: pd.Series) -> bool:
    """Check if row contains 'ignore below' marker."""
    return any(IGNORE_MARKER in str(v).lower() for v in row if pd.notna(v))


def _table_to_markdown(df: pd.DataFrame, table_name: str) -> str:
    """Convert DataFrame to GitHub Markdown table."""
    if df.empty or len(df) < 1:
        return ""
    
    df = df.reset_index(drop=True)
    
    # Check for ignore marker and truncate
    truncate_at = len(df)
    for idx in range(len(df)):
        if _check_ignore_marker(df.iloc[idx]):
            truncate_at = idx
            break
    df = df.iloc[:truncate_at]
    
    if len(df) < 2:
        return ""
    
    # First row = headers
    headers = _deduplicate_columns(df.iloc[0].tolist())
    
    # Data rows
    rows = []
    for idx in range(1, len(df)):
        cells = [_val_to_str(v, escape_md=True) for v in df.iloc[idx].tolist()]
        # Pad/trim to match header count
        cells = (cells + [""] * len(headers))[:len(headers)]
        if any(c.strip() for c in cells):  # Skip empty rows
            rows.append(cells)
    
    if not rows:
        return ""
    
    # Build Markdown
    lines = [f"## {table_name}\n"]
    
    # Calculate column widths
    widths = [max(3, len(h)) for h in headers]
    for row in rows:
        for i, c in enumerate(row):
            widths[i] = max(widths[i], len(c))
    
    # Header
    lines.append("| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |")
    # Separator
    lines.append("| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |")
    # Rows
    for row in rows:
        lines.append("| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |")
    
    return "\n".join(lines)


def _table_to_jsonl(df: pd.DataFrame, sheet_name: str, table_name: str) -> tuple[str, int]:
    """Convert DataFrame to JSONL (one JSON object per line) with metadata."""
    if df.empty or len(df) < 2:
        return "", 0
    
    df = df.reset_index(drop=True)
    
    # Check for ignore marker and truncate
    truncate_at = len(df)
    for idx in range(len(df)):
        if _check_ignore_marker(df.iloc[idx]):
            truncate_at = idx
            break
    df = df.iloc[:truncate_at]
    
    if len(df) < 2:
        return "", 0
    
    # First row = headers
    headers = _deduplicate_columns(df.iloc[0].tolist())
    
    # Data rows → JSONL
    lines = []
    for idx in range(1, len(df)):
        cells = [_val_to_str(v) for v in df.iloc[idx].tolist()]
        cells = (cells + [""] * len(headers))[:len(headers)]
        if any(c.strip() for c in cells):
            record = {h: cells[i] for i, h in enumerate(headers)}
            record["__sheet__"] = sheet_name
            record["__table__"] = table_name
            lines.append(json.dumps(record, ensure_ascii=False))
    
    return "\n".join(lines), len(lines)


# =============================================================================
# Main Processing
# =============================================================================
def process_workbook(xlsx_path: Path, output_dir: Path, fmt: str = "markdown", dry_run: bool = False) -> dict:
    """Process Excel workbook → one folder per sheet, one file per table."""
    if not xlsx_path.exists():
        return {"success": False, "error": f"File not found: {xlsx_path}"}
    
    try:
        xl = pd.ExcelFile(xlsx_path, engine="openpyxl")
    except Exception as e:
        return {"success": False, "error": f"Failed to open Excel: {e}"}
    
    stats = {"sheets": 0, "tables": 0, "rows": 0, "extras": 0}
    
    for sheet_name in xl.sheet_names:
        try:
            # Read with proper NA handling (preserve literal 'NA' strings)
            df = pd.read_excel(
                xl, sheet_name=sheet_name, header=None,
                keep_default_na=False, na_values=[""]
            )
            if df.empty:
                continue
            
            tables = _split_sheet_into_tables(df)
            if not tables:
                continue
            
            # Sanitize folder name
            safe_name = re.sub(r'[\\/*?:"<>|]', "_", sheet_name)[:50].strip("_") or "Unnamed"
            sheet_dir = output_dir / safe_name
            
            ignore_mode = False
            table_num = 0
            
            for table_df in tables:
                table_num += 1
                
                # Check for ignore marker in first row
                if not ignore_mode and _check_ignore_marker(table_df.iloc[0]):
                    ignore_mode = True
                
                # Determine output path
                if ignore_mode:
                    target_dir = sheet_dir / EXTRAS_DIR
                    table_name = f"{EXTRAS_DIR}_table_{table_num}"
                    stats["extras"] += 1
                else:
                    target_dir = sheet_dir
                    table_name = f"{safe_name}_table_{table_num}"
                
                # Generate content based on format
                jsonl_content, row_count = _table_to_jsonl(table_df, sheet_name, table_name)
                md_content = _table_to_markdown(table_df, table_name)
                
                if not jsonl_content and not md_content:
                    continue
                
                stats["rows"] += row_count if row_count else max(0, md_content.count("\n") - 2)
                stats["tables"] += 1
                
                if not dry_run:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    if fmt in ("jsonl", "both") and jsonl_content:
                        (target_dir / f"{table_name}.jsonl").write_text(jsonl_content, encoding="utf-8")
                    if fmt in ("markdown", "both") and md_content:
                        (target_dir / f"{table_name}.md").write_text(f"# {sheet_name}\n\n{md_content}\n", encoding="utf-8")
            
            if table_num > 0:
                stats["sheets"] += 1
                print(f"  ✓ {sheet_name}: {table_num} table(s)")
                
        except Exception as e:
            print(f"  ✗ {sheet_name}: {e}")
    
    return {"success": True, **stats, "output_dir": str(output_dir)}


# =============================================================================
# CLI
# =============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description="📖 Lexicographer: Excel Data Dictionary → Markdown/JSONL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-x", "--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("-f", "--format", choices=["markdown", "jsonl", "both"], default="jsonl", help="Output format (default: jsonl)")
    parser.add_argument("-n", "--dry-run", action="store_true")
    
    args = parser.parse_args()
    
    if not args.xlsx.exists():
        print(f"❌ File not found: {args.xlsx}", file=sys.stderr)
        return 1
    
    fmt_label = {"jsonl": "JSONL", "markdown": "Markdown", "both": "JSONL + Markdown"}[args.format]
    mode = "[DRY-RUN] " if args.dry_run else ""
    print(f"📖 {AGENT_NAME} {mode}")
    print(f"   Input:  {args.xlsx}")
    print(f"   Output: {args.output}")
    print(f"   Format: {fmt_label}\n")
    
    result = process_workbook(args.xlsx, args.output, args.format, args.dry_run)
    
    if not result["success"]:
        print(f"\n❌ {result.get('error')}", file=sys.stderr)
        return 1
    
    print(f"\n✅ Done: {result['sheets']} sheets → {result['tables']} tables ({result['rows']} rows)")
    if result["extras"]:
        print(f"   📁 Extras: {result['extras']} table(s) in '{EXTRAS_DIR}/' folders")
    print(f"   📁 Output: {result['output_dir']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
