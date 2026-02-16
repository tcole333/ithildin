# Research Methodology

## Entity Name Resolution

### Normalization Rules
1. Convert to UPPERCASE (NARA data is uppercase)
2. Strip common suffixes: INC, CORP, CO, LTD, LLC, LP, NA
3. Strip qualifiers: ET AL, /NY/, /DE/, /CA/, /NV/
4. Normalize spacing: collapse multiple spaces, trim
5. Handle ampersand variants: & vs AND
6. Remove punctuation: strip commas, periods, hyphens from names
7. Handle name suffixes: normalize JR/SR/III/IV (e.g., "SMITH JR" = "SMITH, JR." = "SMITH JR.")

### Name Variants to Track
Document all discovered variants in entity profiles:
```
Primary: DREXEL BURNHAM LAMBERT INC
Variants:
- DREXEL BURNHAM LAMBERT
- DREXEL BURNHAM
- DBL
- DREXEL
```

## Source Citation Format

Always cite sources using this format:

```
[Source: ORS record {sequence_id}, {date}]
[Source: SEC Digest dig{MMDDYY}.pdf, filing #{n}]
[Source: Neo4j node_id={id}, type={label}]
[Source: Offshore Leaks {leak_name}, entity_id={id}]
```

Examples:
- `[Source: ORS record 121066110, 1987-02-05]`
- `[Source: SEC Digest dig031087.pdf, filing #6]`
- `[Source: Offshore Leaks "Panama Papers", entity_id=12345678]`

## Confidence Levels

### High Confidence
- Direct exact match across multiple sources
- Corroborated by SEC filings and NARA records
- Clear documentary evidence

### Medium Confidence
- Single source match
- Partial name match (2+ words)
- Circumstantial but reasonable inference

### Low Confidence
- Inferred connection only
- Name similarity without corroboration
- Speculative link requiring further investigation

## Sub-5% Detection Criteria

### Indicators of Coordination
1. **Timing**: Multiple filers in same company within 30-day window
2. **Threshold**: Combined ownership 4-4.9% (just under 5% trigger)
3. **Association**: Filers share broker, address, or known business relationship
4. **Pattern**: Rapid buy-sell patterns that reset 13D filing clock

### Scoring Matrix
| Factor | Points |
|--------|--------|
| Same 30-day window | +5 |
| Combined 4-4.9% | +10 |
| Shared broker/dealer | +5 |
| Same city/address | +3 |
| Known business association | +5 |
| Prior transactions together | +3 |

- Score >= 15: Flag for investigation
- Score 10-14: Note for monitoring
- Score < 10: Document but likely coincidental

## Offshore Match Scoring

### Match Factors
| Factor | Points |
|--------|--------|
| Exact name match | 10 |
| Partial name (2+ words) | 5 |
| Same jurisdiction as known connections | 3 |
| Common intermediary/agent | 5 |
| Address similarity | 3 |
| Incorporation date aligns with events | 2 |

### Confidence Thresholds
- Score >= 15: High confidence - pursue actively
- Score 8-14: Medium confidence - note for follow-up
- Score < 8: Low confidence - document but deprioritize

## Documentation Standards

### Entity Profiles
- Use templates from `entities/{type}/_template.md`
- Include all name variants discovered
- List all source references
- Track investigation status

### Findings
- State conclusion clearly
- Provide supporting evidence with citations
- Note confidence level
- List any caveats or uncertainties

### Leads
- One lead per file
- Include priority (high/medium/low)
- Track status: active -> resolved | abandoned
- Document resolution or reason for abandonment

## Data Quality Notes

### NARA ORS
- Records are 177-char fixed-width
- Dates in YYMMDD format
- Transaction codes: P=Purchase, S=Sale, T=Transfer, B=Beneficial, U=Unknown
- Relationship codes: D=Director, O=Officer, B=Beneficial Owner

### SEC Digests
- Scanned PDFs from 1987-1989
- OCR quality varies
- Company names may be truncated
- Share amounts in thousands (noted as "(000)")

### Offshore Leaks
- Multiple leaks: Panama Papers, Paradise Papers, Offshore Leaks, Bahamas Leaks
- Name matching is fuzzy - offshore entities often use variants
- Jurisdiction codes vary by leak source
