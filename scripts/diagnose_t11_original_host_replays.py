"""Compare completed T11 replays on both original hosts, including force phases."""
import collections
import inspect
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT


def compare_states(source,replay,target):
    import math
    name=target.removesuffix('_final_center_below_minus_20cm')
    if len(source['frames'])!=210 or len(replay['frames'])!=210:raise ValueError('incomplete source or replay')
    def poses(frame):return {o['name']:o['position'] for o in frame['objects'] if o['name'].startswith('t11_')}
    errors=[]
    for a,b in zip(source['frames'],replay['frames']):
        pa,pb=poses(a),poses(b)
        if set(pa)!=set(pb):raise ValueError('tracked object identities differ')
        error=max(math.sqrt(sum((x-y)**2 for x,y in zip(pa[n],pb[n]))) for n in pa)
        if not math.isfinite(error):raise ValueError('nonfinite state difference')
        errors.append(error)
    sf=source.get('runtime_force_summary',[]);rf=replay.get('runtime_force_summary',[])
    first=min([f['first_contact_frame'] for f in sf if f.get('first_contact_frame') is not None],default=210)
    def final_z(state):return poses(state['frames'][-1])[name][2]
    def physics_scene(state):
        return {k:v for k,v in state.get('scene_overrides',{}).items() if not k.startswith('raytracing')}
    return dict(original_label=int(final_z(source)<-.20),replay_label=int(final_z(replay)<-.20),
        original_final_z_m=final_z(source),replay_final_z_m=final_z(replay),
        max_position_difference_m=max(errors),pre_first_contact_max_difference_m=max(errors[:first],default=0),
        first_original_contact_frame=first if first<210 else None,
        first_difference_frames={str(t):next((i for i,e in enumerate(errors) if e>t),None) for t in [1e-8,1e-6,.001]},
        dynamic_specs_match=source['dynamic_objects']==replay['dynamic_objects'],
        scene_overrides_match=source.get('scene_overrides')==replay.get('scene_overrides'),
        physical_scene_overrides_match=physics_scene(source)==physics_scene(replay),
        timing_match=source.get('time_diagnostic')==replay.get('time_diagnostic'),
        effective_properties_match=source.get('physics_debug')==replay.get('physics_debug'),
        force_config_match=source.get('runtime_forces')==replay.get('runtime_forces'),
        original_force_phases=sf,replay_force_phases=rf)


def main():
    sources={r['sample_id']:r for r in json.loads((ROOT/'t11_published_final_states.json').read_text())}
    plans={
      'p25':[j for j in json.loads((ROOT/'five_scene_prepared_plan_20261020.json').read_text()) if j['scene_id']=='T11'],
      'p29':json.loads((ROOT/'t11_original_p29_boundary_plan_20261020.json').read_text()),
    }
    launches={host:json.loads((ROOT/file).read_text()) for host,file in [('p25','five_scene_boundary_launch_20261020.json'),('p29','t11_original_p29_boundary_launch_20261020.json')]}
    rows=[]
    for host,jobs in plans.items():
        # p29's default python is 3.6; use the original 3.10 simulation runtime.
        runtime=launches[host].get('python','/home/wangzijun_p25/miniconda3/envs/genesis/bin/python')
        code=r'''
import pathlib,json,gzip,hashlib
COMPARE
jobs=JOBS;sources=SOURCES;root=pathlib.Path(DIRECTORY);out=[]
def load(path):
 raw=path.read_bytes();return raw,json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)
for job in jobs:
 for endpoint in job['endpoints']:
  folder=root/job['job_id']/format(endpoint['theta'],'.12g');rp=folder/'receipt.json'
  if not rp.exists():continue
  receipt=json.loads(rp.read_text());raw,replay=load(pathlib.Path(receipt['state_path']))
  if hashlib.sha256(raw).hexdigest()!=receipt['stored_state_sha256'] or hashlib.sha256(gzip.decompress(raw)).hexdigest()!=receipt['state_sha256']:raise ValueError('replay identity mismatch')
  if hashlib.sha256((folder/'config.json').read_bytes()).hexdigest()!=receipt['config_sha256']:raise ValueError('replay config changed')
  source_raw,source=load(pathlib.Path(sources[endpoint['sample_id']]['source_state']))
  if hashlib.sha256(source_raw).hexdigest()!=endpoint['state_sha256']:raise ValueError('original identity mismatch')
  comparison=compare_states(source,replay,job['target_event'])
  if comparison['original_label']!=endpoint['label'] or comparison['replay_label']!=receipt['label']:raise ValueError('event rule differs from original or worker rule')
  out.append(dict(job_id=job['job_id'],family_id=job['family_id'],sample_id=endpoint['sample_id'],theta=endpoint['theta'],source_state_sha256=endpoint['state_sha256'],replay_state_sha256=receipt['state_sha256'],**comparison))
print(json.dumps(out))
'''.replace('COMPARE',inspect.getsource(compare_states)).replace('JOBS',repr(jobs)).replace('SOURCES',repr(sources)).replace('DIRECTORY',repr(launches[host]['root']))
        result=subprocess.run(['ssh','-o','BatchMode=yes',host,runtime+' -'],input=code.encode(),capture_output=True,timeout=240)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
        rows.extend(dict(host=host,**row) for row in json.loads(result.stdout))
    summary=dict(examined=len(rows),by_host={host:dict(examined=sum(r['host']==host for r in rows),outcome_mismatches=sum(r['host']==host and r['original_label']!=r['replay_label'] for r in rows)) for host in plans},
        mismatched_fields={k:sum(not r[k] for r in rows) for k in ['dynamic_specs_match','physical_scene_overrides_match','timing_match','effective_properties_match','force_config_match']},
        scope='Observed divergence location and force phases; no claim that graphics, seed, solver internals or hardware uniquely caused the outcome difference.')
    (ROOT/'t11_original_host_divergence_20261020.json').write_text(json.dumps(rows,indent=2))
    (ROOT/'t11_original_host_divergence_summary_20261020.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary))


if __name__=='__main__':main()
