import json,subprocess,time
from pathlib import Path
w=Path('/tmp/osint-disclosures-C2sHVOQq')
for key,term in [('edgar-exact-hicham-2','Sam Hassan'),('edgar-exact-tarek-1','Hassan'),('edgar-exact-abdul-1','Abdul Rahman'),('edgar-exact-abdul-2','Abdulrahman')]:
 d=json.loads((w/(key+'.json')).read_text());hit=d['hits']['hits'][0];acc,fn=hit['_id'].split(':');cik=str(int(hit['_source']['ciks'][0]));url='https://www.sec.gov/Archives/edgar/data/'+cik+'/'+acc.replace('-','')+'/'+fn
 out=w/(key+'-read.json');pr=subprocess.run(['uv','run','python','tools/query_edgar.py','read',url,'--find',term,'--context','3','--output',str(out)],capture_output=True,text=True,timeout=45)
 out.with_suffix('.log').write_text(pr.stdout+'\n'+pr.stderr);print(key,pr.returncode,url,flush=True);time.sleep(.5)
