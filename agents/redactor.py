#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = ["pandas", "openpyxl", "tabulate"]
# ///
"""✂️ The Redactor - Privacy-First Clinical Data Extractor.

Mission: "Extract with 100% accuracy, protect with zero tolerance."

Compliance: India DPDP Act 2023, IT Act 2000 Section 43A
Output: Nested folder structure with per-folder audit logs

Features:
    - Pattern-based PHI/PII detection (column names AND cell values)
    - Consistent pseudonymization (same ID → same hash across dataset)
    - Smart masking (dates, locations, ages)
    - Value scanning for embedded PII (emails, phones, MRNs)
    - No date shifting (preserves temporal relationships)

Usage:
    python redactor.py                                    # Use defaults (JSONL)
    python redactor.py -i data/raw/study -o processed    # Custom paths
    python redactor.py --format markdown                  # Output Markdown only
    python redactor.py --format both                      # Output both formats
    python redactor.py --dry-run                          # Preview only
    python redactor.py --no-privacy                       # Skip PII protection
    python redactor.py --audit-only                       # Show PII report only

Output Structure:
    processed_datasets/
    ├── 10_TST/
    │   └── Sheet1/
    │       ├── Table_1.jsonl        # Machine-readable JSONL (default)
    │       └── _privacy_audit.json  # Per-folder compliance log
    └── processing_summary.json      # Global summary
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


# =============================================================================
# Utility: Clean Value to String (Unified, matches Lexicographer)
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
# Configuration
# =============================================================================
AGENT_NAME = "Redactor"
DEFAULT_INPUT = Path("data/raw/Indo-vap_csv_files")
DEFAULT_OUTPUT = Path("processed_datasets")
DEFAULT_SALT = "DPDP2023"  # Consistent salt for pseudonymization


# =============================================================================
# PII Detection Rules: Column Name Patterns
# =============================================================================
# Pattern → (action, description, priority)
# Actions: HASH, MASK_DATE, MASK_LOC, GENERALIZE_AGE, REDACT, SCAN, PASS
# Priority: Lower = higher priority (1 = most specific)

COLUMN_PII_RULES: list[tuple[str, str, str, int]] = [
    # === Direct Identifiers → HASH (priority 1) ===
    (r"(?i)^SUBJID\d*$", "HASH", "Subject ID", 1),
    (r"(?i)^FID$", "HASH", "Family ID", 1),
    (r"(?i)^PATID$", "HASH", "Patient ID", 1),
    (r"(?i)^MRN$", "HASH", "Medical Record Number", 1),
    (r"(?i)^.*_TUID$", "HASH", "TB Unit ID", 1),
    (r"(?i)^.*_DMCID$", "HASH", "DMC ID", 1),
    (r"(?i)^PHCID$", "HASH", "PHC ID", 1),
    (r"(?i)^.*_INIT$", "HASH", "Initials", 1),
    (r"(?i)^.*_SIGN$", "HASH", "Signature", 1),
    (r"(?i)^ICTC$", "HASH", "ICTC Code", 1),
    (r"(?i)^.*NAME.*$", "HASH", "Name field", 1),
    (r"(?i)^.*PHONE.*$", "HASH", "Phone number", 1),
    (r"(?i)^.*EMAIL.*$", "HASH", "Email address", 1),
    (r"(?i)^.*AADHAAR.*$", "HASH", "Aadhaar number", 1),
    (r"(?i)^.*PAN.*$", "HASH", "PAN number", 1),
    
    # === Dates → MASK to year only (priority 2) ===
    (r"(?i)^.*BIRTHDAT.*$", "MASK_DATE", "Date of Birth", 2),
    (r"(?i)^.*DOB.*$", "MASK_DATE", "Date of Birth", 2),
    (r"(?i)^.*_VISDAT$", "MASK_DATE", "Visit Date", 2),
    (r"(?i)^.*_ICFDT$", "MASK_DATE", "Consent Date", 2),
    (r"(?i)^.*_DT$", "MASK_DATE", "Date field", 2),
    (r"(?i)^.*DAT$", "MASK_DATE", "Date field", 2),
    (r"(?i)^Time_Stamp$", "MASK_DATE", "Timestamp", 2),
    (r"(?i)^.*DATE.*$", "MASK_DATE", "Date field", 2),
    
    # === Location → MASK (priority 3) ===
    (r"(?i)^.*_MUNIC$", "MASK_LOC", "Municipality", 3),
    (r"(?i)^.*CITY.*$", "MASK_LOC", "City", 3),
    (r"(?i)^.*STATE.*$", "MASK_LOC", "State", 3),
    (r"(?i)^.*DISTRICT.*$", "MASK_LOC", "District", 3),
    (r"(?i)^.*VILLAGE.*$", "MASK_LOC", "Village", 3),
    (r"(?i)^.*PINCODE.*$", "MASK_LOC", "Pincode", 3),
    (r"(?i)^.*ZIP.*$", "MASK_LOC", "Zipcode", 3),
    
    # === Address → REDACT (priority 3) ===
    (r"(?i)^.*_ADDR.*$", "REDACT", "Address", 3),
    (r"(?i)^.*ADDRESS.*$", "REDACT", "Address", 3),
    
    # === Free text → SCAN then REDACT if PHI found (priority 4) ===
    (r"(?i)^.*_SP$", "SCAN", "Specify text", 4),
    (r"(?i)^.*_OTH$", "SCAN", "Other text", 4),
    (r"(?i)^.*_COM$", "SCAN", "Comments", 4),
    (r"(?i)^.*COMMENT.*$", "SCAN", "Comments", 4),
    (r"(?i)^.*NOTES.*$", "SCAN", "Notes", 4),
    (r"(?i)^.*REMARKS.*$", "SCAN", "Remarks", 4),
    
    # === Quasi-identifiers → GENERALIZE (priority 5) ===
    (r"(?i)^.*_AGE$", "GENERALIZE_AGE", "Age", 5),
    (r"(?i)^AGE.*$", "GENERALIZE_AGE", "Age", 5),
]


# =============================================================================
# Value-Level PHI Patterns (for scanning free text)
# =============================================================================
VALUE_PHI_PATTERNS: list[tuple[str, str]] = [
    # Indian phone numbers (10 digits, with/without +91/0)
    (r"(?:\+91[\s-]?|0)?[6-9]\d{9}", "PHONE"),
    # Email addresses
    (r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "EMAIL"),
    # Aadhaar number (12 digits in groups of 4)
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "AADHAAR"),
    # PAN number (ABCDE1234F format)
    (r"\b[A-Z]{5}\d{4}[A-Z]\b", "PAN"),
    # Indian pincode (6 digits)
    (r"\b[1-9]\d{5}\b", "PINCODE"),
    # Dates in common formats (but NOT time stamps like HH:MM)
    (r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "DATE"),
    (r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b", "DATE"),
    # Names pattern (Title + Capitalized words) - conservative match
    (r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Shri|Smt)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", "NAME"),
]


# =============================================================================
# Privacy Transformation Functions
# =============================================================================
class PrivacyEngine:
    """Stateful privacy engine with consistent pseudonymization."""
    
    def __init__(self, salt: str = DEFAULT_SALT):
        self.salt = salt
        self._hash_cache: dict[str, str] = {}  # Consistent hashing across dataset
        self.audit_log: list[dict] = []
    
    def hash_value(self, val: Any) -> str:
        """SHA-256 pseudonymization (consistent across dataset)."""
        if pd.isna(val) or str(val).strip() == "":
            return ""
        key = str(val).strip()
        if key not in self._hash_cache:
            self._hash_cache[key] = hashlib.sha256(
                f"{self.salt}:{key}".encode()
            ).hexdigest()[:16]
        return self._hash_cache[key]
    
    def mask_date(self, val: Any) -> str:
        """Mask to year only: 2023-05-14 → 2023-**-**"""
        if pd.isna(val) or str(val).strip() == "":
            return ""
        s = str(val).strip()
        
        # Try to extract year from various formats
        patterns = [
            (r"(\d{4})-\d{2}-\d{2}", 1),      # 2023-05-14
            (r"(\d{4})/\d{2}/\d{2}", 1),      # 2023/05/14
            (r"\d{2}/\d{2}/(\d{4})", 1),      # 14/05/2023
            (r"\d{2}-\d{2}-(\d{4})", 1),      # 14-05-2023
            (r"^(\d{4})$", 1),                # Just year
        ]
        for pattern, group in patterns:
            if m := re.search(pattern, s):
                return f"{m.group(group)}-**-**"
        
        # If it looks like a timestamp, try to extract date part
        if "T" in s or " " in s:
            date_part = s.split("T")[0].split(" ")[0]
            return self.mask_date(date_part)
        
        return "[DATE]"
    
    def mask_location(self, val: Any) -> str:
        """Mask location: Mumbai → Mu***"""
        if pd.isna(val) or str(val).strip() == "":
            return ""
        s = str(val).strip()
        if len(s) <= 2:
            return s
        return f"{s[:2]}***"
    
    def generalize_age(self, val: Any) -> str:
        """5-year age bands: 27 → 25-29"""
        if pd.isna(val) or str(val).strip() == "":
            return ""
        try:
            age = int(float(val))
            if age < 0:
                return ""
            if age < 18:
                return "<18"
            if age >= 90:
                return "90+"
            band_start = (age // 5) * 5
            return f"{band_start}-{band_start + 4}"
        except (ValueError, TypeError):
            return str(val)
    
    def scan_and_redact(self, val: Any) -> tuple[str, list[str]]:
        """Scan value for embedded PHI patterns and redact them."""
        if pd.isna(val) or str(val).strip() == "":
            return "", []
        
        s = str(val).strip()
        found_patterns = []
        
        for pattern, phi_type in VALUE_PHI_PATTERNS:
            matches = re.findall(pattern, s)
            if matches:
                found_patterns.append(phi_type)
                s = re.sub(pattern, f"[{phi_type}]", s)
        
        return s, found_patterns
    
    def get_column_action(self, col_name: str) -> tuple[str, str]:
        """Determine action for column based on name patterns."""
        col_str = str(col_name)
        sorted_rules = sorted(COLUMN_PII_RULES, key=lambda x: x[3])
        for pattern, action, desc, _ in sorted_rules:
            if re.match(pattern, col_str):
                return action, desc
        return "PASS", "Non-PII"
    
    def transform_dataframe(self, df: pd.DataFrame, source: str = "") -> tuple[pd.DataFrame, list[dict]]:
        """Apply privacy transformations to entire DataFrame."""
        df = df.copy()
        column_audit = []
        df = df.fillna("")
        
        for col in df.columns:
            action, desc = self.get_column_action(col)
            scan_findings = []
            
            if action == "HASH":
                df[col] = df[col].apply(self.hash_value)
            elif action == "MASK_DATE":
                df[col] = df[col].apply(self.mask_date)
            elif action == "MASK_LOC":
                df[col] = df[col].apply(self.mask_location)
            elif action == "GENERALIZE_AGE":
                df[col] = df[col].apply(self.generalize_age)
            elif action == "REDACT":
                df[col] = "[REDACTED]"
            elif action == "SCAN":
                results = df[col].apply(self.scan_and_redact)
                df[col] = results.apply(lambda x: x[0])
                for r in results:
                    scan_findings.extend(r[1])
                if scan_findings:
                    action = "SCAN_REDACT"
                    desc = f"{desc} (found: {', '.join(set(scan_findings))})"
            
            if action != "PASS":
                column_audit.append({
                    "column": str(col),
                    "action": action,
                    "description": desc,
                    "sample_masked": "***" if action in ("HASH", "REDACT") else None,
                })
        
        # Final cleanup: ensure all values are clean strings (no 'nan' artifacts)
        df = df.apply(lambda col: col.apply(_val_to_str))
        return df, column_audit


# =============================================================================
# Output Formatting
# =============================================================================
def format_markdown(df: pd.DataFrame, dataset: str, sheet: str) -> str:
    """Generate clean Markdown table with header."""
    header = f"# {dataset}\n\n## Sheet: {sheet}\n\n"
    if df.empty:
        return header + "_No data_\n"
    clean_df = df.apply(lambda col: col.apply(lambda v: _val_to_str(v, escape_md=True)))
    table = clean_df.to_markdown(index=False)
    footer = f"\n\n---\n_Rows: {len(df)} | Columns: {len(df.columns)}_\n"
    return header + table + footer


def format_jsonl(df: pd.DataFrame) -> str:
    """Generate JSONL (one JSON object per line) for each record."""
    if df.empty:
        return ""
    clean_df = df.apply(lambda col: col.apply(_val_to_str))
    records = clean_df.to_dict(orient="records")
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in records)


# =============================================================================
# Core Agent
# =============================================================================
class Redactor:
    """Privacy-first Excel → Markdown/JSON converter with per-folder audit logs."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        fmt: str = "jsonl",
        dry_run: bool = False,
        apply_privacy: bool = True,
        audit_only: bool = False,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.fmt = fmt
        self.dry_run = dry_run
        self.apply_privacy = apply_privacy
        self.audit_only = audit_only
        self.privacy_engine = PrivacyEngine()
        self.global_stats = {
            "start_time": datetime.now().isoformat(),
            "files_processed": 0,
            "files_failed": 0,
            "sheets_processed": 0,
            "total_rows": 0,
            "total_pii_columns": 0,
            "errors": [],
        }

    def run(self) -> dict:
        """Process all Excel files in input directory."""
        if not self.input_dir.exists():
            return {"success": False, "error": f"Directory not found: {self.input_dir}"}

        files = sorted([
            f for f in self.input_dir.iterdir()
            if f.suffix.lower() in (".xlsx", ".xls")
            and not f.name.startswith("~")
            and not f.name.startswith(".")
        ])
        
        if not files:
            return {"success": False, "error": f"No Excel files in {self.input_dir}"}

        fmt_label = {"jsonl": "JSONL", "markdown": "Markdown", "both": "JSONL + Markdown"}[self.fmt]
        print(f"✂️  {AGENT_NAME}")
        print(f"    Input:  {self.input_dir}")
        print(f"    Output: {self.output_dir}")
        print(f"    Files:  {len(files)}")
        print(f"    Format: {fmt_label}")
        print(f"    Mode:   {'🔍 Audit Only' if self.audit_only else '🔓 Raw' if not self.apply_privacy else '🔒 DPDP-2023'}")
        if self.dry_run:
            print(f"    ⚠️  DRY RUN - No files will be written")
        print()

        for xlsx in files:
            try:
                self._process_workbook(xlsx)
            except Exception as e:
                self.global_stats["files_failed"] += 1
                self.global_stats["errors"].append({"file": xlsx.name, "error": str(e)})
                print(f"  ❌ {xlsx.name}: {e}")

        if not self.dry_run and not self.audit_only:
            self._write_summary()

        return {
            "success": True,
            "files": self.global_stats["files_processed"],
            "sheets": self.global_stats["sheets_processed"],
            "rows": self.global_stats["total_rows"],
            "pii_columns": self.global_stats["total_pii_columns"],
            "output_dir": str(self.output_dir),
        }

    def _process_workbook(self, xlsx_path: Path) -> None:
        """Process single Excel file → folder per sheet."""
        dataset_name = xlsx_path.stem
        print(f"📁 {dataset_name}")

        try:
            # Read with string dtype and handle NA values properly
            sheets = pd.read_excel(
                xlsx_path, 
                sheet_name=None, 
                dtype=str,
                keep_default_na=False,
                na_values=[""]
            )
        except Exception as e:
            raise RuntimeError(f"Failed to read Excel: {e}")

        if not sheets:
            print(f"    ⚠️  No sheets found")
            return

        self.global_stats["files_processed"] += 1

        for sheet_name, df in sheets.items():
            if df.empty:
                print(f"    ⏭️  {sheet_name} (empty)")
                continue

            safe_sheet = re.sub(r"[^\w\-]", "_", str(sheet_name))[:50]
            target_dir = self.output_dir / dataset_name / safe_sheet

            pii_audit = []
            if self.apply_privacy:
                df, pii_audit = self.privacy_engine.transform_dataframe(df, xlsx_path.name)
            else:
                df = df.fillna("").apply(lambda col: col.apply(_val_to_str))

            self.global_stats["sheets_processed"] += 1
            self.global_stats["total_rows"] += len(df)
            self.global_stats["total_pii_columns"] += len(pii_audit)

            if self.audit_only:
                print(f"    📊 {sheet_name}: {len(df)} rows, {len(pii_audit)} PII cols")
                if pii_audit:
                    for entry in pii_audit:
                        print(f"        → {entry['column']}: {entry['action']}")
                continue

            md_content = format_markdown(df, dataset_name, sheet_name)
            jsonl_content = format_jsonl(df)
            content_hash = hashlib.sha256((md_content + jsonl_content).encode()).hexdigest()

            if not self.dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
                if self.fmt in ("markdown", "both"):
                    (target_dir / "Table_1.md").write_text(md_content, encoding="utf-8")
                if self.fmt in ("jsonl", "both"):
                    (target_dir / "Table_1.jsonl").write_text(jsonl_content, encoding="utf-8")
                self._write_folder_audit(target_dir, xlsx_path.name, sheet_name, len(df), content_hash, pii_audit)

            pii_indicator = f", 🔒{len(pii_audit)} PII" if pii_audit else ""
            print(f"    ✅ {safe_sheet}/ ({len(df)} rows{pii_indicator})")

    def _write_folder_audit(self, folder: Path, source: str, sheet: str, rows: int, hash_: str, pii: list) -> None:
        """Write/append to per-folder _privacy_audit.json."""
        log_path = folder / "_privacy_audit.json"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source_file": source,
            "sheet_name": sheet,
            "rows_processed": rows,
            "integrity_hash": hash_,
            "compliance": "DPDP_2023",
            "agent": AGENT_NAME,
            "pii_transformations": pii,
        }
        log = []
        if log_path.exists():
            try:
                log = json.loads(log_path.read_text(encoding="utf-8"))
                if not isinstance(log, list):
                    log = [log]
            except json.JSONDecodeError:
                log = []
        log.append(entry)
        log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    def _write_summary(self) -> None:
        """Write global processing summary."""
        self.global_stats["end_time"] = datetime.now().isoformat()
        summary_path = self.output_dir / "processing_summary.json"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(self.global_stats, indent=2, ensure_ascii=False), encoding="utf-8")


# =============================================================================
# CLI
# =============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"✂️ {AGENT_NAME}: Privacy-First Excel → Markdown/JSONL Extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
    python redactor.py                         # Process with defaults (JSONL)
    python redactor.py -i data/raw -o out      # Custom paths
    python redactor.py --format markdown       # Output Markdown only
    python redactor.py --format both           # Output both formats
    python redactor.py --dry-run               # Preview without writing
    python redactor.py --audit-only            # Show PII report only
    python redactor.py --no-privacy            # Skip PII protection
        """,
    )
    parser.add_argument("-i", "--input", type=Path, default=DEFAULT_INPUT, help=f"Input directory (default: {DEFAULT_INPUT})")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT, help=f"Output directory (default: {DEFAULT_OUTPUT})")
    parser.add_argument("-f", "--format", choices=["jsonl", "markdown", "both"], default="jsonl", help="Output format (default: jsonl)")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Preview only, don't write files")
    parser.add_argument("--no-privacy", action="store_true", help="Skip PII protection (raw extraction)")
    parser.add_argument("--audit-only", action="store_true", help="Show PII audit report only, don't extract")

    args = parser.parse_args()

    agent = Redactor(
        input_dir=args.input,
        output_dir=args.output,
        fmt=args.format,
        dry_run=args.dry_run,
        apply_privacy=not args.no_privacy,
        audit_only=args.audit_only,
    )
    
    result = agent.run()

    if not result["success"]:
        print(f"\n❌ {result.get('error', 'Failed')}", file=sys.stderr)
        return 1

    print(f"\n{'─' * 50}")
    print(f"✅ Complete: {result['files']} files → {result['sheets']} sheets ({result['rows']:,} rows)")
    if result["pii_columns"]:
        print(f"🔒 PII protected: {result['pii_columns']} column transformations")
    if not args.audit_only and not args.dry_run:
        print(f"📁 Output: {result['output_dir']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
