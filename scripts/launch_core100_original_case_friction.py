"""Continue T11's original friction component without changing frozen inputs.

This is a conditional component direction, not recovery of the joint G path.
"""
import hashlib
import json
from pathlib import Path

from scripts.boundary_ssh import remote_text

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_continue_20261031'

REMOTE=r'''
import copy,datetime,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
home=Path('/home/wangzijun_p25/core100_reference_storage_20261101')
helper=home/'original_case_friction_component_20261101.py'
helper_text=HELPER_TEXT
if helper.exists():assert helper.read_text()==helper_text
else:helper.write_text(helper_text)
spec=importlib.util.spec_from_file_location('original_component',helper)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
parent=home/'T11_ORIGINAL_GLOBAL_PATH_CONTRACT.json'
global_contract=json.loads(parent.read_text())
contract=dict(schema='core100-original-case-friction-component-v1',
 component='case_friction_coefficient',original_range=[.04,.22],
 original_joint_path_recovered=False,forces_modified=False,
 helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),helper_source=helper_text,
 parent_contract_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),cases=[])
prepared=[]
for cid in ['T11_C01','T11_C02']:
 donor=Path('/data2/liyuhan/core100_continue_families_20261031')/(cid+'__G_global_original')
 job=copy.deepcopy(json.loads((donor/'jobs.json').read_text())[0])
 vector=copy.deepcopy(job['joint_source_nominal_parameters']);source=job['base_config']
 assert source['experiment']['formal_design']['design_id']=='G_global_06'
 assert module.t11_case_friction_intervention(source,vector,.08)==source
 tested=module.t11_case_friction_intervention(source,vector,1.2)
 assert tested['runtime_forces']==source['runtime_forces']
 assert all(tested['experiment']['parameter']['parameter_value'][k]==v
  for k,v in vector.items()if k!='case_friction_coefficient')
 contract['cases'].append(dict(clip_id=cid,source_vector=vector,
  source_config_sha256=job['config_sha256'],source_no_op_exact=True))
 prepared.append((cid,donor,job))
contract_file=home/'T11_ORIGINAL_CASE_FRICTION_CONTRACT_20261101.json'
raw=json.dumps(contract,indent=2)
if contract_file.exists():assert contract_file.read_text()==raw
else:contract_file.write_text(raw)
contract_sha=hashlib.sha256(contract_file.read_bytes()).hexdigest();launches=[]
for cid,donor,job in prepared:
 public=donor.parent/(cid+'__case_friction_original')
 storage=home/public.name
 if (storage/'LAUNCH.json').exists():
  launches.append(dict(clip_id=cid,existing=True,root=str(public)));continue
 storage.mkdir(exist_ok=True)
 if public.exists():assert public.is_symlink()and public.resolve()==storage
 else:public.symlink_to(storage,target_is_directory=True)
 original_coordinate=job['theta']
 job.update(family='case_friction_coefficient',theta=.08,domain=[.04,.22],
  grid=[.04,.08,.14,.22,.4,.8,1.2,2.],tolerance=.002,
  original_family_axes_not_collapsed=True,
  original_component_contract_sha256=contract_sha,
  original_component_provenance='An original G_global source input; conditional direction, not the original joint path.',
  normalization_domain_preserved=True,extended_grid_values_not_used_to_expand_normalization=True)
 (storage/'jobs.json').write_text(json.dumps([job],indent=2))
 worker=(donor/'worker.py').read_text()
 anchor='def intervention(job, theta):\n'
 branch="    if job['family']=='case_friction_coefficient':\n        import sys\n        sys.path.insert(0,"+repr(str(home))+ ")\n        from original_case_friction_component_20261101 import t11_case_friction_intervention\n        return t11_case_friction_intervention(job['base_config'],job['joint_source_nominal_parameters'],theta)\n"
 assert worker.count(anchor)==1;worker=worker.replace(anchor,anchor+branch)
 (storage/'worker.py').write_text(worker)
 (storage/'native_bootstrap.py').write_bytes((donor/'native_bootstrap.py').read_bytes())
 deployment=json.loads((donor/'deployment.json').read_text())
 for name in list(deployment['sources']):
  if name.startswith(str(donor)+'/'):deployment['sources'].pop(name)
 for path in [public/'worker.py',public/'native_bootstrap.py',helper,contract_file]:
  deployment['sources'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
 (storage/'deployment.json').write_text(json.dumps(deployment,indent=2))
 for repeat in [False,True]:
  src=donor/cid/'profile_0'/('source_repeat'if repeat else format(original_coordinate,'.12g'))
  target=storage/cid/'profile_0'/('source_repeat'if repeat else'.08')
  # Worker folder naming uses 0.08, not .08.
  if not repeat:target=target.with_name('0.08')
  target.mkdir(parents=True,exist_ok=True)
  receipt=json.loads((src/'receipt.json').read_text());receipt['theta']=.08
  (target/'config.json').write_bytes((src/'config.json').read_bytes())
  (target/'physics.json.gz').write_bytes(Path(receipt['state_path']).read_bytes())
  receipt['state_path']=str(public/cid/'profile_0'/target.name/'physics.json.gz')
  assert hashlib.sha256((target/'config.json').read_bytes()).hexdigest()==receipt['config_sha256']
  (target/'receipt.json').write_text(json.dumps(receipt,indent=2))
 with(storage/'original_case_friction.log').open('ab')as log:
  process=subprocess.Popen([deployment['python'],str(public/'worker.py'),'--root',str(public),'--clip',cid],
   cwd=deployment['cwd'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 receipt=dict(clip_id=cid,pid=process.pid,root=str(public),source_and_repeat_reused=True,
  original_five_input_vector=job['joint_source_nominal_parameters'],
  family=job['family'],normalization_domain=job['domain'],grid=job['grid'],
  joint_path_completion_claimed=False,frozen_inputs_modified=False,runtime_forces_modified=False)
 (storage/'LAUNCH.json').write_text(json.dumps(receipt,indent=2));launches.append(receipt)
print(json.dumps(dict(contract_raw=raw,launches=launches)))
'''


def main():
    helper=(ROOT/'physedit/original_joint_path.py').read_text(encoding='utf8')
    data=json.loads(remote_text('p25',REMOTE.replace('HELPER_TEXT',repr(helper)),timeout=120))
    proof=WORK/'t11_original_case_friction_contract_20261101.json'
    raw=data.pop('contract_raw').encode()
    if proof.exists():assert proof.read_bytes()==raw
    else:proof.write_bytes(raw)
    data['contract_sha256']=hashlib.sha256(raw).hexdigest()
    (WORK/'t11_original_case_friction_launch_20261101.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    print(json.dumps(data))


if __name__=='__main__':main()
