import concurrent.futures,json,subprocess,sys,time
from pathlib import Path
from tools.lead_tracker import check_searched,log_search
work=Path('/tmp/osint-disclosures-C2sHVOQq')
people={'hicham':['Hicham Ali Hassan','Hicham Hassan','Sam Hassan'],'zouhair':['Zouhair Ali Hassan','Zouhair Hassan'],'abdul':['Abdul Rahman Ali Hassan','Abdul Rahman Hassan','Abdulrahman Hassan'],'houssam':['Houssam Ali Hassan','Houssam Hassan'],'talal':['Talal Ali Hassan','Talal Hassan'],'tarek':['Tarek Ali Hassan','Tarek Hassan']}
groups={
'irs990': ('query_990.py','officer-search',['--limit','30']),
'faa': ('ingest_faa.py','search',['--limit','30']),
'opensanctions': ('query_opensanctions.py','search',['--limit','20']),
'fara': ('query_fara.py','search',['--limit','20']),
'edgar': ('query_edgar.py','search',['--size','10']),
'fec': ('query_fec.py','donor',['--limit','30','--state','MA']),
'lobbying': ('query_lobbying.py','lobbyist',['--limit','10']),
'gleif': ('query_gleif.py','search',['--limit','10']),
'littlesis': ('query_littlesis.py','search',[]),
}
def group(source):
    tool,mode,opts=groups[source]; outcomes=[]
    # Probe each source once; stop its group on an access failure.
    for person,aliases in people.items():
      chosen=aliases if source in ('irs990','opensanctions','fara','faa') else [aliases[1]]
      for name in chosen:
        key=json.dumps({'profile':'hassan-boston','mode':mode,'query':name,'filters':opts},sort_keys=True)
        prior=check_searched(key,source)
        out=work/(source+'-'+person+'-'+str(aliases.index(name))+'.json')
        if prior and out.exists(): continue
        cmd=['uv','run','python','tools/'+tool,mode,('"'+name+'"' if source=='edgar' else name),*opts,'--output',str(out)]
        t=time.time()
        try:
          proc=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
          output=(proc.stdout+'\n'+proc.stderr).strip(); code=proc.returncode
        except subprocess.TimeoutExpired as exc:
          output='Bounded timeout after 60s';code=-1
        (out.with_suffix('.log')).write_text(output)
        row={'source':source,'person':person,'name':name,'command':cmd,'exit_code':code,'seconds':round(time.time()-t,2),'artifact':str(out),'output_exists':out.exists(),'log':output[-2000:]}
        if out.exists():
          data=json.loads(out.read_text());row['shape']=type(data).__name__;row['count']=len(data) if isinstance(data,list) else None
          if isinstance(data,dict): row['keys']=list(data)
          if isinstance(data,list): log_search(key,source,len(data))
        outcomes.append(row)
        with (work/(source+'-manifest.json')).open('w') as f:json.dump(outcomes,f,indent=2)
        print(json.dumps({k:row.get(k) for k in ['source','name','exit_code','output_exists','count','keys']}),flush=True)
        if code!=0 or not out.exists(): return outcomes
        time.sleep(0.5 if source in ('edgar','fec','lobbying','gleif','littlesis') else 0)
    return outcomes
selected=sys.argv[1:]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(group,selected))
