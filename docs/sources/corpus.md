# Investigation Corpus Tools

Corpus tools are investigation-specific local databases. The active investigation profile's `corpus_tools` field lists which tools to search. Load the profile first:

```bash
uv run python tools/investigation_context.py show
```

## Protocol

For each tool listed in `corpus_tools`, run searches with the target name and known variants:

```bash
# Search each corpus tool
uv run python tools/<corpus_tool>.py search "TARGET" --limit 20 --output $WORKDIR/corpus-<tool>.json

# Entity co-occurrence (which tools support it)
uv run python tools/<corpus_tool>.py cooccurrence "TARGET" --top 30 --output $WORKDIR/corpus-coocc.json

# Entities
uv run python tools/<corpus_tool>.py entities "TARGET" --output $WORKDIR/corpus-entities.json

# RDF triples (relationship extraction)
uv run python tools/<corpus_tool>.py triples --actor "TARGET" --limit 30 --output $WORKDIR/corpus-triples.json
```

### Common Corpus Tools

| Tool | Description | Subcommands |
|------|-------------|-------------|
| `query_doj.py` | DOJ document corpus (FTS5) | `search`, `efta ID --text` |
| `duggan_search.py` | DugganUSA API (329K docs) | `"QUERY" -n 20` |
| `query_lmsband.py` | LMSBAND files/entities | `search`, `entities`, `cooccurrence` |
| `query_unified.py` | Unified emails/docs/triples | `emails`, `docs`, `entities`, `triples`, `cooccurrence` |

## What To Look For

- **Direct mentions**: Target name in documents, emails, filings
- **Co-occurrence patterns**: Who appears alongside the target? (network mapping)
- **Email patterns**: Frequency, recipients, tone, subject lines
- **Document types**: What kinds of documents mention the target?
- **Timeline clusters**: When do mentions concentrate? What was happening then?
- **Name variants**: Try alternate spellings, transliterations, maiden names

## Email Analysis (Parquet)

If the investigation has email datasets in parquet format (check `datasets/` or investigation profile):
```bash
# Direct parquet query for email patterns
uv run python -c "
import pandas as pd
df = pd.read_parquet('datasets/<email_file>.parquet')
matches = df[df['body'].str.contains('TARGET', case=False, na=False)]
print(f'{len(matches)} emails mentioning TARGET')
print(matches[['date','from','to','subject']].head(20).to_string())
"
```

## Reading Documents

For EVERY document found, read the full text to extract exact quotes:
```bash
uv run python tools/query_doj.py efta EFTA_ID --text
```

Extract: dates, names, financial amounts, relationships, exact quotes for findings.

## Findings

- Direct quotes from documents: `claim_type=direct_quote`, evidence=`EFTA_ID`
- Paraphrased summaries: `claim_type=paraphrase`
- `--sources` = the specific corpus tool name (e.g., `doj_vol11`, `lmsband`, `unified`)
