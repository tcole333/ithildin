import subprocess,json,pathlib
from tools.lead_tracker import check_searched
w=pathlib.Path('/tmp/osint-CurvpbBq')
names=['Hicham Ali Hassan','Zouhair Ali Hassan','Abdul Rahman Ali Hassan','Houssam Ali Hassan','Talal Ali Hassan','Tarek Ali Hassan']
for i,name in enumerate(names):
 for mode in ['party','opinions','recap-search']:
  print('CHECK',name,mode,check_searched(name,'courtlistener'),flush=True)
  r=subprocess.run(['uv','run','python','tools/query_courtlistener.py',mode,name,'--limit','30','--output',str(w/f'{i}-{mode}.json')],capture_output=True,text=True)
  print(name,mode,r.returncode,r.stdout,r.stderr,flush=True)
