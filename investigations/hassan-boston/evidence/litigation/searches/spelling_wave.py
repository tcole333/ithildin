import subprocess,pathlib,json
from tools.lead_tracker import check_searched
from tools.search_log_util import canonical_search_key
w=pathlib.Path('/tmp/osint-CurvpbBq')
groups={
'hicham':['Hicham Ali Hassan','Hicham Hassan','Hicham Ali-Hassan','Hicham Aly Hassan','Hachim Ali Hassan','Hisham Ali Hassan','Hesham Ali Hassan'],
'zouhair':['Zouhair Ali Hassan','Zouhair Hassan','Zouheir Ali Hassan','Zuhair Ali Hassan','Zuhayr Ali Hassan','Zouhair Ali-Hassan'],
'abdul':['Abdul Rahman Ali Hassan','Abdulrahman Ali Hassan','Abdelrahman Ali Hassan','Abdel Rahman Ali Hassan','Abdur Rahman Ali Hassan','Abdul-Rahman Ali Hassan','Abdul Rahman Hassan'],
'houssam':['Houssam Ali Hassan','Houssam Hassan','Hossam Ali Hassan','Hussam Ali Hassan','Husam Ali Hassan','Houssam Ali-Hassan'],
'talal':['Talal Ali Hassan','Talal Hassan','Talal Ali-Hassan','Talal Aly Hassan'],
'tarek':['Tarek Ali Hassan','Tarek Hassan','Tarek Ali-Hassan','Tarik Ali Hassan','Tariq Ali Hassan','Tarek Aly Hassan']}
(w/'spelling-groups.json').write_text(json.dumps(groups,indent=2))
for slug,names in groups.items():
 q=' OR '.join('"'+n+'"' for n in names)
 for typ in ['r','o']:
  print('CHECK',slug,typ,check_searched(canonical_search_key('search',q,type=typ),'courtlistener'),flush=True)
  r=subprocess.run(['uv','run','python','tools/query_courtlistener.py','search',q,'--type',typ,'--limit','100','--output',str(w/f'spelling-{slug}-{typ}.json')],capture_output=True,text=True)
  print(slug,typ,r.stdout,r.stderr,flush=True)
