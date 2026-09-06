import subprocess,pathlib
from tools.lead_tracker import check_searched
from tools.search_log_util import canonical_search_key
w=pathlib.Path('/tmp/osint-CurvpbBq')
for i,n in enumerate(['Hicham','Zouhair','Abdul Rahman Hassan','Houssam','Talal','Tarek Hassan']):
 print(n,check_searched(canonical_search_key('party',n,court='mad'),'courtlistener'),flush=True)
 r=subprocess.run(['uv','run','python','tools/query_courtlistener.py','party',n,'--court','mad','--limit','50','--output',str(w/f'variant-{i}.json')],capture_output=True,text=True);print(r.stdout,r.stderr,flush=True)
for i,n in enumerate(['Zouhair Ali Hassan','Abdul Rahman Ali Hassan','Houssam Ali Hassan','Talal Ali Hassan','Tarek Ali Hassan']):
 r=subprocess.run(['uv','run','python','tools/query_state_courts.py','search',n,'--jurisdiction','25','--output',str(w/f'state-{i}.json')],capture_output=True,text=True);print(r.stdout,r.stderr,flush=True)
