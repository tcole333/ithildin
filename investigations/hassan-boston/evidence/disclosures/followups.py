import json,subprocess,time
from pathlib import Path
from tools.lead_tracker import check_searched,log_search
w=Path('/tmp/osint-disclosures-C2sHVOQq')
queries=[]
for p,names in {'hicham':['Hicham Ali Hassan','Hicham Hassan','Sam Hassan'],'zouhair':['Zouhair Ali Hassan','Zouhair Hassan'],'abdul':['Abdul Rahman Ali Hassan','Abdul Rahman Hassan','Abdulrahman Hassan'],'houssam':['Houssam Ali Hassan','Houssam Hassan'],'talal':['Talal Ali Hassan','Talal Hassan'],'tarek':['Tarek Ali Hassan','Tarek Hassan']}.items():
 for i,n in enumerate(names):queries.append(('query_edgar.py','search',n,['--size','10'],'edgar-exact-'+p+'-'+str(i)))
 queries.append(('query_edgar.py','lookup',names[0],[],'edgar-lookup-'+p))
for n in ['Concepts International','The Tannery','Silverstone Development']:
 queries.append(('query_edgar.py','search',n,['--size','10'],'edgar-company-'+n.lower().replace(' ','-')))
queries += [('query_fec.py','donor','Sam Hassan',['--state','MA','--limit','30'],'fec-sam'),('query_fec.py','donor','Tarek Ali Hassan',['--state','MA','--limit','30'],'fec-tarek-full'),('query_fec.py','donor','Hassan',['--employer','Tannery','--limit','50'],'fec-tannery')]
results=[]
for tool,mode,q,opts,slug in queries:
 key=json.dumps({'profile':'hassan-boston','mode':mode,'query':q,'filters':opts},sort_keys=True);source='edgar' if 'edgar' in tool else 'fec';check_searched(key,source)
 out=w/(slug+'.json');cmd=['uv','run','python','tools/'+tool,mode,q,*opts,'--output',str(out)]
 try:pr=subprocess.run(cmd,capture_output=True,text=True,timeout=35);code=pr.returncode;log=pr.stdout+'\n'+pr.stderr
 except subprocess.TimeoutExpired:code=-1;log='bounded timeout 35s'
 out.with_suffix('.log').write_text(log);row={'source':source,'mode':mode,'name':q,'command':cmd,'exit_code':code,'artifact':str(out),'output_exists':out.exists()}
 if out.exists():
  d=json.loads(out.read_text());cnt=len(d) if isinstance(d,list) else d.get('hits',{}).get('total',{}).get('value');row['count']=cnt
  if cnt is not None:log_search(key,source,cnt)
 print(json.dumps(row),flush=True);results.append(row);(w/'followups-manifest.json').write_text(json.dumps(results,indent=2));time.sleep(.4)
