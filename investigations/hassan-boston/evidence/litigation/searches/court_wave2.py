import subprocess,pathlib
from tools.lead_tracker import check_searched
from tools.search_log_util import canonical_search_key
w=pathlib.Path('/tmp/osint-CurvpbBq')
queries=[('party','Sam Hassan'),('cases','"Hassan" court:mad'),('cases','"Alana" court:mab'),('cases','"Nader" court:mab'),('cases','"Tannery"'),('opinions','"Hassan" "Sugar Heaven"')]
for i,n in enumerate(['Hicham Ali Hassan','Zouhair Ali Hassan','Abdul Rahman Ali Hassan','Houssam Ali Hassan','Talal Ali Hassan','Tarek Ali Hassan']):
 queries.extend([('opinions','"'+n+'"'),('recap-search','"'+n+'"')])
for i,(mode,q) in enumerate(queries):
 print('CHECK',mode,q,check_searched(canonical_search_key(mode,q),'courtlistener'),flush=True)
 r=subprocess.run(['uv','run','python','tools/query_courtlistener.py',mode,q,'--limit','100','--output',str(w/f'q2-{i}-{mode}.json')],capture_output=True,text=True)
 print(i,mode,r.returncode,r.stdout,r.stderr,flush=True)
for ident in ['7589042','63519436']:
 r=subprocess.run(['uv','run','python','tools/query_courtlistener.py','docket',ident,'--output',str(w/f'docket-{ident}.json')],capture_output=True,text=True)
 print(ident,r.stdout,r.stderr,flush=True)
