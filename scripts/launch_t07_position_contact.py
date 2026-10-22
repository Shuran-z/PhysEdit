"""Refine original T07-B E4 contact brackets on the original p25 renderer."""
import json
from pathlib import Path
import subprocess
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    receipt=ROOT/'t07_B_E4_search_launch_20261022.json'
    if receipt.exists():raise RuntimeError('T07-B contact search already launched')
    plan=ROOT/'t07_B_E4_search_plan_20261022.json';jobs=json.loads(plan.read_text())
    if not jobs:raise RuntimeError('no observed opposite-outcome interval to refine')
    directory='/data_cached/wangzijun_p25/liyuhan/t07_B_E4_search_20261022'
    remote_text('p25',"import pathlib\npathlib.Path("+repr(directory)+").mkdir(exist_ok=False)")
    for p,n in [(plan,'plan.json'),(Path('scripts/t07_original_boundary_worker.py'),'worker.py')]:subprocess.run(['scp','-q',str(p.resolve()),'p25:'+directory+'/'+n],check=True,timeout=120)
    code=r'''
import pathlib,json,subprocess
r=pathlib.Path(DIRECTORY)
with (r/'worker.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'worker.py'),'--plan',str(r/'plan.json'),'--root',str(r/'run'),'--gpu','1'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(host='p25',root=str(r/'run'),pipeline_root=str(r),pid=p.pid,gpu=1,planned_intervals=COUNT,target_event='phone_table_contact_after_release')))
'''.replace('DIRECTORY',repr(directory)).replace('COUNT',str(len(jobs)))
    launch=json.loads(remote_text('p25',code));receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
