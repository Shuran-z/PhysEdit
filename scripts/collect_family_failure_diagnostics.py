"""Refresh T18 failure evidence and full-render controls, separate from scoring."""
import base64
import gzip
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    code=r'''
import pathlib,json,subprocess,gzip,base64,hashlib
b=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t18_table_contact_search_20261020')
current=b/'failure_audit_20261026'
if (current/'summary.json').exists():results=current
else:
 a=b/'failure_audit_20261023';script=a/'audit_t18_source_failures.py'
 if not script.exists():script=b/'audit_t18_source_failures.py'
 if not script.exists():raise ValueError('original audit script not found')
 subprocess.run(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(script),'--base',str(b),'--out',str(a/'results')],check=True,stdout=subprocess.DEVNULL)
 results=a/'results'
summary=json.loads((results/'summary.json').read_text())
cases=[json.loads(p.read_text()) for p in results.glob('*.json') if p.name not in ['summary.json','progress.json']]
controls=[]
for p in (b/'original_render_control_20261023/results').glob('*/comparison.json'):
 row=json.loads(p.read_text())
 if row['status']=='original_render_control_completed':
  raw=gzip.decompress((p.parent/'physics.json.gz').read_bytes())
  if hashlib.sha256(raw).hexdigest()!=row['control_state_sha256']:raise ValueError('control trajectory changed')
 controls.append(row)
print(base64.b64encode(gzip.compress(json.dumps(dict(summary=summary,cases=cases,controls=controls)).encode())).decode())
'''
    data=json.loads(gzip.decompress(base64.b64decode(remote_text('p25',code,timeout=600))))
    (ROOT/'t18_failure_diagnostics_20261023.json').write_text(json.dumps(data,indent=2))
    print(json.dumps(dict(summary=data['summary'],full_render_controls=len(data['controls']),
        full_render_source_mismatches=sum(r.get('category')=='different_contact_history' for r in data['controls']))))


if __name__=='__main__':main()
