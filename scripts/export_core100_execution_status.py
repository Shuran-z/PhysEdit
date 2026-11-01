"""Read the authenticated deployed calculation without exposing a session token."""
import base64,csv,gzip,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'review/core100_execution_20261030'
CODE='''import sys,json,urllib.request,base64,gzip
sys.path.insert(0,'/srv/phylabel/current');from store import Store
s=Store('/srv/phylabel/data/annotations.sqlite3');token=s.session('admin')
try:
 req=urllib.request.Request('http://127.0.0.1:13081/api/critical-results',headers={'Cookie':'phylabel_session='+token})
 with urllib.request.urlopen(req,timeout=60)as response:result=json.load(response)
 with s.connect()as db:result['supplemental_review_states']=[dict(r)for r in db.execute("select state,count(*)n from tasks where batch_id='t17_window5_review_20261030' group by state")]
finally:s.logout(token)
print(base64.b64encode(gzip.compress(json.dumps(result).encode())).decode())
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ProxyCommand=ssh -o BatchMode=yes p25 python3 /home/wangzijun_p25/.ssh/phylabel_proxy.py','tx173','sudo','-n','python3','-'],input=CODE.encode(),capture_output=True,timeout=120,check=True)
raw=base64.b64decode(p.stdout.strip());(OUT/'production_final.json.gz').write_bytes(raw);result=json.loads(gzip.decompress(raw))
def export(name,rows):
 with(OUT/name).open('w',encoding='utf-8-sig',newline='')as f:
  fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False)if isinstance(v,(list,dict))else v for k,v in r.items()})
export('cases100_gaps.csv',result['execution_readiness']['cases'])
export('physical_windows540.csv',result['execution_readiness']['physical_window_outputs'])
export('scenes20.csv',result['execution_readiness']['scenes'])
export('formal_scores12.csv',result['per_model'])
export('contact_diagnostic_scores12.csv',result['contact_amendment']['per_model'])
assert result['summary']['final_input_matches']==3600
assert len(result['execution_readiness']['cases'])==100
print(json.dumps({'summary':result['summary'],'execution':result['execution_readiness']['summary'],
 'formal_scores':[{k:r.get(k)for k in ['model','NearAcc','PairAcc','formal_scope']}for r in result['per_model']if r['NearAcc']is not None or r['PairAcc']is not None],
 'supplemental_review':result['supplemental_review_states']},ensure_ascii=False,indent=2))
