"""Compare completed control trajectories; never rewrite reference labels."""
import inspect
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT
from scripts.diagnose_t11_original_host_replays import compare_states


def trajectory_difference(a,b):
    import math
    if len(a)!=len(b) or not a:raise ValueError('incomplete matched trajectories')
    errors=[]
    for x,y in zip(a,b):
        px={o['name']:o['position'] for o in x['objects']};py={o['name']:o['position'] for o in y['objects']}
        if not px or px.keys()!=py.keys():raise ValueError('object identities differ')
        values=[math.sqrt(sum((u-v)**2 for u,v in zip(px[n],py[n]))) for n in px]
        if any(not math.isfinite(v) for v in values):raise ValueError('nonfinite trajectory difference')
        error=max(values)
        errors.append(error)
    return dict(max_position_difference_m=max(errors),first_difference_over_1mm_frame=next((i for i,v in enumerate(errors) if v>.001),None))


def remote(host,code):
    p=subprocess.run(['ssh','-o','BatchMode=yes',host,'/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],input=code.encode(),capture_output=True,timeout=120)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    return json.loads(p.stdout)


def main():
    catalog=json.loads((ROOT/'boundary_replay_diagnostics_20261020.json').read_text());output={}
    name='t11_p26_full_contract_control_launch_20261021.json'
    if name in catalog and catalog[name]['results'].get('status.json',{}).get('status')=='completed_full_producer_control':
        launch=catalog[name]['launch'];sid=launch['sample_id']
        jobs=json.loads((ROOT/'t11_verified_p26_producer_plan_20261020.json').read_text())
        job=next(j for j in jobs if any(e['sample_id']==sid for e in j['endpoints']));endpoint=next(e for e in job['endpoints'] if e['sample_id']==sid)
        source=next(p for p in job['production_completion_receipts'] if p['sample_id']==sid)
        numeric=json.loads((ROOT/'t11_verified_p26_producer_launch_20261020.json').read_text())
        code=r'''
import pathlib,json,gzip,hashlib
COMPARE
root=pathlib.Path(DIRECTORY);source=SOURCE;endpoint=ENDPOINT;target=TARGET
raw=pathlib.Path(source['source_state']).read_bytes()
if hashlib.sha256(raw).hexdigest()!=endpoint['state_sha256']:raise ValueError('original state changed')
original=json.loads(gzip.decompress(raw));status=json.loads((root/'status.json').read_text());sp=root/'cam01/physics.json'
if hashlib.sha256(sp.read_bytes()).hexdigest()!=status['state_sha256']:raise ValueError('control state changed')
full=json.loads(sp.read_text());out=dict(target_event=target,target_object=target[:-len('_final_center_below_minus_20cm')],full_production=compare_states(original,full,target),production=source)
folder=pathlib.Path(NUMERIC)/JOB/format(endpoint['theta'],'.12g');rp=folder/'receipt.json'
if rp.exists():
 receipt=json.loads(rp.read_text());raw=pathlib.Path(receipt['state_path']).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=receipt['stored_state_sha256'] or hashlib.sha256(gzip.decompress(raw)).hexdigest()!=receipt['state_sha256']:raise ValueError('numeric state changed')
 state=json.loads(gzip.decompress(raw));out['numeric_mode']=compare_states(original,state,target);out['full_versus_numeric']=compare_states(full,state,target)
print(json.dumps(out))
'''.replace('COMPARE',inspect.getsource(compare_states)).replace('DIRECTORY',repr(launch['root'])).replace('SOURCE',repr(source)).replace('ENDPOINT',repr(endpoint)).replace('TARGET',repr(job['target_event'])).replace('NUMERIC',repr(numeric['root'])).replace('JOB',repr(job['job_id']))
        output['T11']=remote(launch['host'],code)
        repeat_name='t11_p26_full_contract_control_repeat2_launch_20261021.json'
        repeat=catalog.get(repeat_name,{})
        if repeat.get('results',{}).get('status.json',{}).get('status')=='completed_full_producer_control':
            code=r'''
import pathlib,json,hashlib
COMPARE
roots=ROOTS;states=[]
for directory in roots:
 root=pathlib.Path(directory);status=json.loads((root/'status.json').read_text());p=root/'cam01/physics.json'
 if hashlib.sha256(p.read_bytes()).hexdigest()!=status['state_sha256']:raise ValueError('repeat state changed')
 states.append(json.loads(p.read_text()))
print(json.dumps(compare_states(states[0],states[1],TARGET)))
'''.replace('COMPARE',inspect.getsource(compare_states)).replace('ROOTS',repr([launch['root'],repeat['launch']['root']])).replace('TARGET',repr(job['target_event']))
            output['T11']['identical_full_contract_repeat']=remote(launch['host'],code)
    name='t13_fixed_seed_control_launch_20261021.json'
    if name in catalog and catalog[name]['results'].get('comparison.json',{}).get('status')=='completed_fixed_seed_control':
        launch=catalog[name]['launch']
        code=r'''
import pathlib,json,hashlib
DIFFERENCE
root=pathlib.Path(DIRECTORY);rows=json.loads((root/'status.json').read_text());states={}
for row in rows:
 folder=root/('repeat_'+str(row['repeat']))/format(row['theta'],'.12g');p=folder/'physics.json'
 if hashlib.sha256(p.read_bytes()).hexdigest()!=row['state_sha256'] or hashlib.sha256((folder/'config.json').read_bytes()).hexdigest()!=row['config_sha256']:raise ValueError('seed-control state or config changed')
 if row['seed']!=0 or not row['actual_genesis_seed_verified']:raise ValueError('actual seed unconfirmed')
 states[(row['repeat'],row['theta'])]=json.loads(p.read_text())
out=[]
for theta in sorted({r['theta'] for r in rows}):
 a,b=[next(r for r in rows if r['repeat']==i and r['theta']==theta) for i in range(2)]
 out.append(dict(theta=theta,seed=0,repeat_labels=[a['events'],b['events']],labels_agree=a['events']==b['events'],**trajectory_difference(states[(0,theta)]['frames'],states[(1,theta)]['frames'])))
print(json.dumps(dict(comparison=json.loads((root/'comparison.json').read_text()),repeated_trajectory_comparisons=out,seed_origin='new supplementary seed, not recovered original seed',unique_cause_claim=False)))
'''.replace('DIFFERENCE',inspect.getsource(trajectory_difference)).replace('DIRECTORY',repr(launch['root']))
        output['T13']=remote(launch['host'],code)
    (ROOT/'boundary_control_trajectory_comparisons_20261021.json').write_text(json.dumps(output,indent=2))
    print(json.dumps(dict(completed_control_analyses=list(output),reference_labels_unchanged=True)))


if __name__=='__main__':main()
