import concurrent.futures,subprocess,json,sqlite3,time,sys,csv,datetime
from pathlib import Path
from tools.lead_tracker import check_searched,log_search
w=Path('/tmp/osint-disclosure-variants-g9oazPgY')
variants={'Hicham Ali Hassan':['Hachim Hassan','Hisham Hassan','Hesham Hassan'],'Zouhair Ali Hassan':['Zuhair Hassan','Zouheir Hassan'],'Abdul Rahman Ali Hassan':['Abdulrahman Hassan','Abdelrahman Hassan','Abdel Rahman Hassan','Abdur Rahman Hassan'],'Houssam Ali Hassan':['Hossam Hassan','Hussam Hassan','Husam Hassan'],'Tarek Ali Hassan':['Tarik Hassan','Tariq Hassan']}
entries=[(subject,name) for subject,names in variants.items() for name in names]
rows=[]
def write_manifest():
 with (w/'variant-query-manifest.json').open('w') as f:json.dump(rows,f,indent=2)
def record(source,subject,name,count,artifact,scope,note=''):
 key=json.dumps({'profile':'hassan-boston','pass':'variant-supplement','query':name,'scope':scope},sort_keys=True)
 log_search(key,source,count)
 row={'subject':subject,'candidate_spelling':name,'source':source,'actual_query':name,'scope':scope,'result_rows':count,'artifact':artifact,'note':note};rows.append(row);print(json.dumps(row),flush=True)
def local_sql():
 db=sqlite3.connect('file:datasets/irs990_grants.db?mode=ro',uri=True);db.row_factory=sqlite3.Row
 patterns=[f'%{n}%' for _,n in entries]
 # One deliberate bounded batch across the same officers corpus used by query_990.
 where=' OR '.join(['o.person_name LIKE ?']*len(patterns))
 sql='SELECT o.ein,o.person_name,o.title,o.tax_year,o.total_comp,f.filer_name FROM officers o JOIN filings f ON o.object_id=f.object_id WHERE ('+where+') ORDER BY o.total_comp DESC,o.tax_year DESC LIMIT 500'
 for subject,n in entries:check_searched(n,'irs990')
 data=[dict(r) for r in db.execute(sql,patterns)];db.close();(w/'irs990-batch.json').write_text(json.dumps({'sql':sql,'parameters':patterns,'rows':data},indent=2))
 for subject,n in entries:
  hits=[r for r in data if n.casefold() in r['person_name'].casefold()];artifact='irs990-'+n.lower().replace(' ','-')+'.json';(w/artifact).write_text(json.dumps(hits,indent=2));record('irs990',subject,n,len(hits),artifact,'officer person_name LIKE %candidate%; local IRS990 snapshot; batch result cap500, no truncation if below500')
 db=sqlite3.connect('file:investigation.db?mode=ro',uri=True);db.row_factory=sqlite3.Row
 for subject,n in entries:
  parts=n.rsplit(' ',1);pattern='%'+parts[0]+'%';sql="SELECT registration_number,registrant_name,short_form_name,short_form_date,city,state FROM fara_short_forms WHERE short_form_name LIKE ? AND short_form_name LIKE '%Hassan%' LIMIT 50";hits=[dict(r) for r in db.execute(sql,(pattern,))];artifact='fara-shortform-'+n.lower().replace(' ','-')+'.json';(w/artifact).write_text(json.dumps(hits,indent=2));record('fara-short-forms',subject,n,len(hits),artifact,"short_form_name LIKE %given variant% AND LIKE %Hassan%; cap50; local 2026-09-02")
 db.close()
def cli_group(source):
 tool,mode,opts={'faa':('ingest_faa.py','search',['--limit','30']),'opensanctions':('query_opensanctions.py','search',['--limit','20']),'fara':('query_fara.py','search',['--limit','20']),'fec':('query_fec.py','donor',['--state','MA','--limit','30'])}[source]
 for subject,n in entries:
  check_searched(n,source);artifact=source+'-'+n.lower().replace(' ','-')+'.json';out=w/artifact;cmd=['uv','run','python','tools/'+tool,mode,n,*opts,'--output',str(out)]
  try:p=subprocess.run(cmd,capture_output=True,text=True,timeout=35);log=p.stdout+'\n'+p.stderr;code=p.returncode
  except subprocess.TimeoutExpired:log='bounded35s timeout';code=-1
  out.with_suffix('.log').write_text(log)
  if code or not out.exists():
   record(source,subject,n,None,artifact,str(cmd),'access/tool failure; remaining queries not run');break
  d=json.loads(out.read_text());count=len(d) if isinstance(d,list) else sum(len(d[k]) for k in ['registrants','foreign_principals'])
  record(source,subject,n,count,artifact,' '.join([mode,*opts]),'raw candidates only; no identity attribution')
  if source=='fec':time.sleep(.4)
if sys.argv[1:] == ['fec']:cli_group('fec')
else:
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  futures=[pool.submit(local_sql)]+[pool.submit(cli_group,s) for s in ['faa','opensanctions','fara']]
  for f in futures:f.result()
write_manifest()
