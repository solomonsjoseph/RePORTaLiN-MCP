# RePORTaLiN-Agent

> Privacy-First Clinical Data Extraction Multi-Agent System

## 🎯 Mission

Extract clinical research data with **100% accuracy** while applying **zero-tolerance privacy protection** compliant with India's Digital Personal Data Protection Act 2023.

## 🤖 Agents

### 📖 Lexicographer
Converts Excel data dictionaries to clean, readable Markdown.

```bash
python agents/lexicographer.py                           # Default paths
python agents/lexicographer.py --xlsx path/to/dict.xlsx  # Custom input
python agents/lexicographer.py --output docs/            # Custom output
python agents/lexicographer.py --dry-run                 # Preview only
```

**Features:**
- Island detection (splits sheets into tables at empty rows)
- 100% data preservation (no truncation)
- Duplicate header handling (`Date` → `Date_1`)
- "Ignore below" markers respected
- Clean GitHub Markdown output

### ✂️ Redactor
Privacy-first Excel → Markdown/JSONL extractor with full audit trail.

```bash
python agents/redactor.py                                # Default paths
python agents/redactor.py -i data/raw/study -o archive   # Custom paths
python agents/redactor.py --dry-run                      # Preview only
python agents/redactor.py --no-privacy                   # Skip PII protection
python agents/redactor.py --audit-only                   # Show PII report
```

**Features:**
- Pattern-based PHI/PII detection (column names + cell values)
- Consistent pseudonymization (same ID → same hash across dataset)
- Smart masking (dates → year only, locations → abbreviated)
- Age generalization (5-year bands)
- Value scanning for embedded PII (emails, phones, Aadhaar, PAN)
- Per-folder privacy audit logs
- JSONL output (one record per line) + Markdown tables

## 📂 Project Structure

```
RePORTaLiN-Agent/
├── agents/
│   ├── redactor.py       # Privacy-first data extractor
│   └── lexicographer.py  # Data dictionary converter
├── data/
│   └── raw/              # Source Excel files
├── archive/              # Redactor output (privacy-safe)
│   └── {Dataset}/
│       └── {Sheet}/
│           ├── Table_1.md
│           ├── Table_1.jsonl
│           └── _privacy_audit.json
├── dictionary/           # Lexicographer output
│   └── {SheetName}.md
└── README.md
```

## 🔒 Privacy Compliance

**India DPDP Act 2023 + IT Act 2000 Section 43A**

| Data Type | Action | Example |
|-----------|--------|---------|
| Subject IDs | HASH | `10200001A` → `dd2017301cab9670` |
| Names, Initials | HASH | `Dr. Sharma` → `a1b2c3d4e5f6g7h8` |
| Dates | MASK | `2023-05-14` → `2023-**-**` |
| Locations | MASK | `Mumbai` → `Mu***` |
| Ages | GENERALIZE | `27` → `25-29` |
| Addresses | REDACT | `123 Main St` → `[REDACTED]` |
| Free text with PHI | SCAN+REDACT | `Call 9876543210` → `Call [PHONE]` |

**Value-level PHI detection:**
- Indian phone numbers (+91/0 prefix, 10 digits)
- Email addresses
- Aadhaar numbers (12 digits)
- PAN numbers (ABCDE1234F format)
- Pincodes (6 digits)
- Names with titles (Mr./Mrs./Dr./Shri/Smt)

## 🚀 Quick Start

```bash
# Install dependencies
pip install pandas openpyxl tabulate

# Run Lexicographer on data dictionary
python agents/lexicographer.py

# Run Redactor with privacy protection
python agents/redactor.py

# Run Redactor in audit-only mode (see what would be redacted)
python agents/redactor.py --audit-only
```

## 📋 Requirements

- Python 3.13+
- pandas
- openpyxl
- tabulate

## 📜 License

MIT License - See LICENSE file for details.

---
*Built for the RePORT International consortium*
