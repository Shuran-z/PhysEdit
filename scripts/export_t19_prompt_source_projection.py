from pathlib import Path
import sys,base64,json,gzip
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.boundary_ssh import remote_text
code='''from pathlib import Path
import json,zipfile,hashlib,gzip,base64
r=Path('/data_cached/wangzijun_p25/t19_final_release_20261030/stage/releases/physedit/provenance/t19_gen_new_20261030')
z=zipfile.ZipFile(r/'source_metadata.zip');out={};cache={}
for line in (r/'SOURCE_BINDINGS.jsonl').read_text().splitlines():
 b=json.loads(line);key=b['group']+'/'+b['sample_id']
 tk='physics/'+key+'/trajectory.json';ck='physics/'+key+'/config.json';mk='metadata/'+b['scene']+'/'+key+'.json'
 for p,h in [(tk,b['trajectory_sha256']),(ck,b['source_config_sha256']),(mk,b['metadata_sha256'])]:
  raw=z.read(p);assert hashlib.sha256(raw).hexdigest()==h
  cache[p]=json.loads(raw)
 t=cache[tk];c=cache[ck];m=cache[mk];assert m['trajectory_sha256']==b['trajectory_sha256']
 projection={k:t[k] for k in ['specifications','actual_masses_kg','table_friction','body_friction'] if k in t}
 for v in b['videos']:out[v['sha256']]={'trajectory':projection,'config':c,'trajectory_sha256':b['trajectory_sha256'],'metadata_sha256':b['metadata_sha256']}
print(base64.b64encode(gzip.compress(json.dumps(out).encode(),compresslevel=1)).decode())
'''
b=base64.b64decode(remote_text('p25',code,timeout=90));data=json.loads(gzip.decompress(b));assert len(data)==2640
(ROOT/'review/full_prompt_audit_20261102/T19_SOURCE_PROJECTION.json.gz').write_bytes(b)
print(json.dumps({'t19_source_projections':len(data)}))
