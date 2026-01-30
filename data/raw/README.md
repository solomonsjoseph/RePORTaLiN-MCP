# Raw Data Directory

This directory contains Excel workbooks with patient data.

**⚠️ RESTRICTED ACCESS**
- Only the Gatekeeper agent can read from this directory
- Files are GitIgnored for privacy
- Never commit patient data

## Usage

Place Excel (.xlsx) files here for ingestion:
```bash
# From project root
cp /path/to/datasets/*.xlsx data/raw/
```

Then run ingestion:
```python
from reportalin.server.app import admin_ingest_data
result = admin_ingest_data()
```
