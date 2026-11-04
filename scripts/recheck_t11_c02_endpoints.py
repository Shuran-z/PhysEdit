"""Repeat the four local friction endpoints; never replace original inputs."""
import argparse
import json
from pathlib import Path

from scripts.boundary_ssh import remote_text

WORK = Path(__file__).resolve().parents[1] / 'review/core100_continue_20261031'
REMOTE = r'''
import copy,fcntl,hashlib,json,os,subprocess
from pathlib import Path
cid='T11_C02'
donor=Path('/data2/liyuhan/core100_continue_families_20261031/T11_C02__case_friction_original')
parent=Path('/home/wangzijun_p25/core100_endpoint_rechecks_20261101')
parent.mkdir(exist_ok=True)
guard=(parent/'launch.lock').open('a');fcntl.flock(guard,fcntl.LOCK_EX)
job0=json.loads((donor/'jobs.json').read_text())[0]
result=json.loads((donor/cid/'result.json').read_text())
assert job0['family']=='case_friction_coefficient' and job0['end_frame_index']==154
endpoints=sorted(set(v for row in result['intervals'] for v in row['bracket']))
assert len(endpoints)==4,endpoints
same_device=SAME_DEVICE
coarse=COARSE
device=None
if same_device:
 endpoints=endpoints[:1]
 first=donor/cid/'profile_0'/format(endpoints[0],'.12g')/'actual_gpu_selection.json'
 device=json.loads(first.read_text())
out=[]
for repeat in ([4,5]if coarse else[3]if same_device else[1,2]):
 if coarse:
  endpoints=[1.2 if repeat==4 else 2.]
  first=donor/cid/'profile_0'/format(endpoints[0],'.12g')/'actual_gpu_selection.json'
  device=json.loads(first.read_text())
 root=parent/('T11_C02_r%02d'%repeat+('_coarse'if coarse else'_same_device'if same_device else''))
 if(root/'LAUNCH.json').exists():
  out.append(dict(json.loads((root/'LAUNCH.json').read_text()),existing=True));continue
 root.mkdir(exist_ok=True)
 job=copy.deepcopy(job0)
 job.update(grid=endpoints,tolerance=2.,validation_only=True,
  validation_purpose='Independent executions of existing local opposite-label endpoints; not a new scan or family.',
  endpoint_repeat_index=repeat,donor_root=str(donor))
 (root/'jobs.json').write_text(json.dumps([job],indent=2))
 for name in ['worker.py','native_bootstrap.py']:(root/name).write_bytes((donor/name).read_bytes())
 deployment=json.loads((donor/'deployment.json').read_text())
 for name in list(deployment['sources']):
  if name.startswith(str(donor)+'/'):deployment['sources'].pop(name)
 for name in ['worker.py','native_bootstrap.py']:
  deployment['sources'][str(root/name)]=hashlib.sha256((root/name).read_bytes()).hexdigest()
 assert set(map(str,deployment['cards'])).issubset({'0','1'})
 if same_device or coarse:deployment['cards']=[device['selected_gpu_index']]
 (root/'deployment.json').write_text(json.dumps(deployment,indent=2))
 for name in [format(job['theta'],'.12g'),'source_repeat']:
  src=donor/cid/'profile_0'/name;dest=root/cid/'profile_0'/name
  dest.mkdir(parents=True,exist_ok=True)
  receipt=json.loads((src/'receipt.json').read_text())
  assert hashlib.sha256((src/'config.json').read_bytes()).hexdigest()==receipt['config_sha256']
  (dest/'config.json').write_bytes((src/'config.json').read_bytes())
  # Only the source baseline is reused. Each requested endpoint runs afresh.
  state=Path(receipt['state_path'])
  if not(dest/'physics.json.gz').exists():os.link(state,dest/'physics.json.gz')
  receipt['state_path']=str(dest/'physics.json.gz')
  (dest/'receipt.json').write_text(json.dumps(receipt,indent=2))
 with(root/'endpoint_recheck.log').open('ab')as log:
  process=subprocess.Popen([deployment['python'],str(root/'worker.py'),'--root',str(root),'--clip',cid],
   cwd=deployment['cwd'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 launch=dict(root=str(root),pid=process.pid,clip_id=cid,endpoints=endpoints,
  repeat_index=repeat,validation_only=True,frozen_inputs_modified=False,
  original_solver_clock_seed_event_window_preserved=True,
  fixed_numeric_seed_claimed=False,original_seed=job['base_config'].get('random_seed',job['base_config'].get('seed')),
  requested_original_device=device,
  source_config_sha256=job['config_sha256'],donor_result_sha256=hashlib.sha256((donor/cid/'result.json').read_bytes()).hexdigest())
 (root/'LAUNCH.json').write_text(json.dumps(launch,indent=2));out.append(launch)
print(json.dumps(out))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--same-device-suspect',action='store_true')
    parser.add_argument('--coarse-endpoints',action='store_true')
    args=parser.parse_args()
    if args.same_device_suspect and args.coarse_endpoints:parser.error('Choose one comparison.')
    code=REMOTE.replace('SAME_DEVICE',repr(args.same_device_suspect)).replace('COARSE',repr(args.coarse_endpoints))
    data = json.loads(remote_text('p25',code, timeout=90))
    name=('t11_c02_coarse_endpoint_recheck_launch_20261101.json'if args.coarse_endpoints else
          't11_c02_same_device_recheck_launch_20261101.json'if args.same_device_suspect else
          't11_c02_endpoint_recheck_launch_20261101.json')
    (WORK/name).write_text(json.dumps(data,indent=2),encoding='utf8')
    print(json.dumps(data))


if __name__ == '__main__':
    main()
