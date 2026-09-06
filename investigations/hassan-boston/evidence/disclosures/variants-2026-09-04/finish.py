import json,csv,shutil,datetime
from pathlib import Path
w=Path('/tmp/osint-disclosure-variants-g9oazPgY');dest=Path('investigations/hassan-boston/evidence/disclosures/variants-2026-09-04');dest.mkdir(parents=True,exist_ok=True)
rows=[]
for name in ['local-progress.log','fec-progress.log']:
 for line in (w/name).read_text().splitlines():
  if line.startswith('{'):rows.append(json.loads(line))
for r in rows:
 r['candidate_status']='search_only_not_alias'
 r['match_disposition']='zero within scope' if r['result_rows']==0 else 'unlinked candidate; no business-context match'
 r['query_date_utc']='2026-09-04'
 r['snapshot']='Live FEC query; no cycle restriction; state MA; first30' if r['source']=='fec' else 'local snapshot: IRS990 DB March2026; FAA February2026; OpenSanctions February2026; FARA September2,2026'
 r['artifact']=str(dest/r['artifact'])
 if r['source']=='irs990':r['actual_query']=f"officers.person_name LIKE '%{r['candidate_spelling']}%'"
 elif r['source']=='fara-short-forms':r['actual_query']=f"short_form_name LIKE '%{r['candidate_spelling'].rsplit(' ',1)[0]}%' AND short_form_name LIKE '%Hassan%'"
(w/'variant-query-manifest.json').write_text(json.dumps(rows,indent=2))
with (w/'variant-query-manifest.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
for p in w.iterdir():
 if p.is_file():shutil.copy2(p,dest/p.name)
report='''# Track F supplementary spelling-variant screen — 2026-09-04

A bounded supplement completed **84 source/query combinations** for **14 search-only spellings** across six scopes: local IRS 990 officers, local FAA, local OpenSanctions, local FARA registrants/principals, separate local FARA short forms, and official FEC donor search filtered to Massachusetts. No spelling was promoted to an alias; no new subject finding, entity, or connection was created.

Queries: **Hachim Hassan; Hisham Hassan; Hesham Hassan; Zuhair Hassan; Zouheir Hassan; Abdulrahman Hassan; Abdelrahman Hassan; Abdel Rahman Hassan; Abdur Rahman Hassan; Hossam Hassan; Hussam Hassan; Husam Hassan; Tarik Hassan; Tariq Hassan.** Talal had no requested additional variant in this supplement and retains original Track F coverage.

| Scope | Result |
|---|---|
| FAA active/deregistered local | Zero returned for all 14 spellings |
| FARA registrants/foreign principals | Zero returned for all 14 spellings |
| FARA short-form names | Zero returned for all 14 first-name-variant + Hassan filters |
| IRS990 officer names | Hossam Hassan: one 2023 Masjid Al-Shuhada vice-president row; Tariq Hassan: four 2023/2024 rows at Education for Employment and Petco Love. Other 12 spellings zero. None has a Boston/Tannery/Concepts/Silverstone identity bridge. |
| FEC Schedule A, state MA, no cycle restriction, first30 | Tariq Hassan:30 returned candidate rows (query cap reached), with Elevate Services Inc / VP Procurement Services or Vice President and retired employment fields in New Bedford/Randolph. Other13 spellings zero. No retail/development context; unlinked. The 30 rows are not a lifetime count and are not summed. |
| OpenSanctions, local phrase search, cap20 | Abdulrahman3; Abdelrahman2; Abdel Rahman2; Tariq1; other10 variants zero. These are raw matching rows, with overlap across spelling queries. Inspected contexts concern different full names, an Egyptian actor born1992, Sudanese banker, Palestinian politician, earlier Iraqi/Nigerian namesakes and an Iraqi full-name mismatch. No attribution to an investigation subject; presence in the multi-topic corpus is not itself sanctions status. |

Local snapshot limits remain: FAA and OpenSanctions February2026; IRS990 DB March2026, with the returned tax years2023/2024; FARA bulk September2,2026. FEC was queried live on2026-09-04. All searches succeeded; no access failure was recorded as zero. Local IRS was executed as one bounded batch of the same substring conditions used by officer-search, returning five rows below the500-row batch cap. This avoids rescanning the large officers table14 times. FARA short forms were checked directly because the CLI excludes that table (existing papercut2670).

These are scoped negatives and unlinked candidates, not certifications that the subjects lack registrations, giving or affiliations. No religious affiliation, political identity, income or wealth claim is inferred from name matches. Any later candidate needs an independent business-context bridge.

**Evidence and query ledger:** `investigations/hassan-boston/evidence/disclosures/variants-2026-09-04/`. `variant-query-manifest.csv` contains subject, candidate spelling, actual query, source, filters, snapshot, result-row count, disposition and durable artifact. Raw per-query JSONs and the IRS SQL/parameters are preserved. Scoped `search_log` entries were written for every query. This manifest was sent to the identities agent for incorporation into `name-variants.csv`.
'''
(w/'report-variant-disclosures.md').write_text(report);(dest/'report-variant-disclosures.md').write_text(report)
Path('/tmp/osint-ysMoSW8V/report-variant-disclosures.md').write_text(report)
append='\n\n## Supplement — spelling variants (2026-09-04)\n\nCompleted84 additional scoped searches of14 candidate spellings across IRS990, FAA, OpenSanctions, FARA registrants/principals, FARA short forms and MA-filtered FEC. No additional subject identity link or substantive finding; all nonzero candidates remain unlinked. Full methods, counts, exclusions and snapshot limitations: `evidence/disclosures/variants-2026-09-04/report-variant-disclosures.md`; actual-query CSV: `variant-query-manifest.csv` in the same directory. These spellings are search-only, not accepted aliases.\n'
for p in [Path('/tmp/osint-ysMoSW8V/report-agent-f.md'),Path('investigations/hassan-boston/evidence/disclosures/report-agent-f.md')]:
 with p.open('a') as f:f.write(append)
print('queries',len(rows),'artifacts',dest)
