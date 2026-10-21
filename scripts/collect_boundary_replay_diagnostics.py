"""Collect diagnostics separately; never convert a failed replay into a score."""
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    output={}
    for name in ['t13_unreproduced_control_launch_20261020.json','five_scene_source_replay_launch_20261020.json','t11_production_contract_control_launch_20261020.json']:
        if not (ROOT/name).exists():continue
        launch=json.loads((ROOT/name).read_text())
        code=r'''
import pathlib,json
l=LAUNCH;r=pathlib.Path(l['root']);out={}
for name in ['status.json','comparison.json','resource_status.json','source_contract.json']:
 p=r/name
 if p.exists():out[name]=json.loads(p.read_text())
checks=[]
for p in r.glob('*/endpoint_checks.json'):checks.append(dict(job_id=p.parent.name,checks=json.loads(p.read_text())))
out['endpoint_checks']=checks
q=pathlib.Path(l.get('pipeline_root',l['root']))/'queue_status.json'
if q.exists():out['queue']=json.loads(q.read_text())
print(json.dumps(out))
'''.replace('LAUNCH',repr(launch))
        p=subprocess.run(['ssh','-o','BatchMode=yes',launch['host'],'python3 -'],input=code.encode(),capture_output=True,timeout=40)
        if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
        output[name]=dict(launch=launch,results=json.loads(p.stdout),diagnostic_only=True)
    (ROOT/'boundary_replay_diagnostics_20261020.json').write_text(json.dumps(output,indent=2));print(json.dumps({name:list(data['results']) for name,data in output.items()}))


if __name__=='__main__':main()
