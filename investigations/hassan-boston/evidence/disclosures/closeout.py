from pathlib import Path
import json,sqlite3,shutil,datetime
from tools.lead_tracker import log_search,check_searched
w=Path('/tmp/osint-disclosures-C2sHVOQq');dest=Path('investigations/hassan-boston/evidence/disclosures')
coverage={}
for source in ['irs990','faa','opensanctions','fara','lobbying','gleif','littlesis','fec']:
 rows=[]
 for p in sorted(w.glob(source+'-*.json')):
  if p.name.endswith('manifest.json') or p.name=='fara-shortforms.json':continue
  d=json.loads(p.read_text())
  if isinstance(d,list):count=len(d)
  elif 'data' in d:count=len(d['data'])
  elif 'registrants' in d:count=len(d['registrants'])+len(d['foreign_principals'])
  else:continue
  rows.append({'artifact':p.name,'result_rows':count})
 coverage[source]=rows
for p in w.glob('edgar-exact-*.json'):
 if p.name.endswith('-read.json'):continue
 d=json.loads(p.read_text());coverage.setdefault('edgar_exact',[]).append({'artifact':p.name,'result_rows':d['hits']['total']['value']})
for source,rows in coverage.items():
 for row in rows:
  key=json.dumps({'profile':'hassan-boston','artifact':row['artifact'],'scope':'2026-09-04 bounded Track F screen'},sort_keys=True)
  if not check_searched(key,source):log_search(key,source,row['result_rows'])
metadata={'queried_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'profile':'hassan-boston','record_dates':'OCPF event 2022-07-18 filed 2022-08-02; FEC returned rows 1992-2002','local_snapshot_files':{},'coverage':coverage,'limitations':['Bounded searches; absence only within specified name forms, filters and local snapshot.','FEC screened state MA; not lifetime/global coverage. Raw duplicate API rows not summed.','IRS 990 officer search uses substring LIKE, yielding Sam within Hossam and Tarek Hassan within Hassanein.','Initial EDGAR files without exact/lookup/company in filename were double-quoted query experiments and match separate words. Superseded by edgar-exact-*; not interpreted as person counts.','GLEIF fulltext can match address words and is not a beneficial-ownership search.','OCPF only identified report 841345; no systematic state donor search completed.','No individual-name-only SEC, IRS990, GLEIF or OpenSanctions candidate was attributed.']}
for f in ['datasets/irs990_grants.db','datasets/faa_registry.db','datasets/opensanctions.db','datasets/fara/short_forms.csv.zip']:
 p=Path(f);metadata['local_snapshot_files'][f]={'mtime_utc':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat(),'bytes':p.stat().st_size}
(w/'coverage.json').write_text(json.dumps(metadata,indent=2))
for p in w.iterdir():
 if p.suffix in ('.json','.pdf','.txt','.png','.py') and p.is_file():shutil.copy2(p,dest/p.name)
# Check persisted summaries and evidence linkage without reprinting incidental addresses.
db=sqlite3.connect('file:investigation.db?mode=ro',uri=True);db.row_factory=sqlite3.Row
print([dict(r) for r in db.execute('select id,profile_id,target_name,summary,confidence,claim_type from findings where id in (15501,15502)')])
print('evidence counts',db.execute('select finding_id,count(*) from finding_evidence where finding_id in (15501,15502) group by finding_id').fetchall())
print('Coverage archived',dest/'coverage.json')
