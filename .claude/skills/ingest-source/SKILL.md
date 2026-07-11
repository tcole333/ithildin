---
name: ingest-source
description: Add a new data source to the investigation infrastructure
user_invocable: true
---

# /ingest-source

Onboard a new data source into the investigation platform.

## Arguments

- Required: source identifier or URL (e.g., `/ingest-source tensonaut/EPSTEIN_FILES_20K`)

## Process

### 1. Characterize the Source
- What format? (Parquet, CSV, SQLite, JSON, API, .eml, HTML)
- How large? (file count, record count, size)
- What does it contain? (emails, documents, entities, financial records, flight logs)
- What's the provenance? (DOJ release, court filing, FOIA, leaked, community-compiled)
- Overlap with existing sources? (Check against unified DB, LMSBAND, etc.)

### 2. Download/Access
For downloadable datasets:
```bash
# HuggingFace datasets
pip install datasets  # if needed
python -c "from datasets import load_dataset; ds = load_dataset('<ID>'); ds.save_to_disk('datasets/<name>')"

# Or direct download
curl -L <URL> -o datasets/<filename>
```

For APIs:
- Document the API endpoint, auth requirements, rate limits
- Test with a sample query

**If the API is undocumented or endpoints are uncertain, you MUST run live discovery before writing the tool.** Do not guess at endpoint URLs, parameter names, or response formats and write code around assumptions. Instead:

1. **Fetch the web interface** (`WebFetch` the portal's search page) and extract API endpoints from JavaScript, form actions, and XHR patterns in the page source
2. **Probe candidate endpoints** with a script that systematically tries likely URL patterns and reports which return valid responses vs 404/403/500
3. **Document the discovered API** — exact endpoint URL, required parameters, response schema, rate limits, auth requirements
4. **Only then write the tool** targeting the confirmed, working endpoint

This applies equally to FTP/SFTP servers — connect and list the actual directory structure before writing parsers for files you haven't seen.

Speculative code that "tries multiple endpoints and hopes one works" is not acceptable as a final implementation. It's fine as a discovery script, but the resulting tool must target a specific, verified endpoint.

### 3. Schema Analysis
Examine the data structure:
```python
import pandas as pd
df = pd.read_parquet('datasets/<file>.parquet')
print(df.columns.tolist())
print(df.dtypes)
print(f"Rows: {len(df)}")
print(df.head())
```

### 4. Write Query Wrapper
Create `tools/query_<source>.py` following the standard pattern:
- CLI with argparse subcommands
- `search` command for text/keyword search
- `--json` flag for structured output
- `--limit` flag for result count
- Consistent output formatting

See existing wrappers for reference:
- `tools/ingest_kabasshouse.py` (parquet download + SQLite FTS5)
- `tools/query_doj.py` (SQLite + FTS5)
- `tools/query_lmsband.py` (SQLite)
- `tools/query_icij.py` (Neo4j)

### 5. Run Initial Investigation Search
Test the new source against core targets. Pull the top entities dynamically from the database rather than using a hardcoded list:
```bash
# Get the most-investigated targets from existing findings
python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
rows = db.execute('''
    SELECT target_name, COUNT(*) as cnt FROM findings
    GROUP BY target_name ORDER BY cnt DESC LIMIT 15
''').fetchall()
for name, cnt in rows:
    print(f'{name} ({cnt} findings)')
"
```
Also always include the primary subject and core inner circle members as search terms.

### 6. Create Leads from Findings
For any significant new results, create leads:
```bash
python tools/lead_tracker.py add \
    --title "New data in <source>: <description>" \
    --category document \
    --priority medium \
    --source "ingest:<source_name>"
```

### 7. Update Source Report
Add the new source to `tools/source_report.py`:
- Add a check function call in `generate_report()`
- Include query tool reference

### 8. Update CLAUDE.md
Add the new source to the Data Source Inventory section in CLAUDE.md.

### 9. Log the Ingestion
Document what was ingested, record counts, any issues found.
