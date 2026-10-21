"""Locate replay divergence without changing reference labels or declaring a cause."""
import collections
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    plan=json.loads((ROOT/'five_scene_prepared_plan_20261020.json').read_text())
    states={r['sample_id']:r for r in json.loads((ROOT/'t11_published_final_states.json').read_text())}
    jobs=[j for j in plan if j['scene_id']=='T11']
    originals={e['sample_id']:states[e['sample_id']] for j in jobs for e in j['endpoints']}
    code=r'''
import json,pathlib,gzip,hashlib,math
jobs=JOBS;originals=ORIGINALS;out=[]
base=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/five_scene_boundary_20261020')
cache={}
def load(p):
 raw=p.read_bytes();return raw,json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
for root,mode in [(base/'run_seedfixed','fixed_source_seed'),(base/'published_seed_diagnostic/run','own_published_seed')]:
 for job in jobs:
  for endpoint in job['endpoints']:
   folder=root/job['job_id']/format(endpoint['theta'],'.12g');sp=folder/'physics.json.gz'
   if not (folder/'receipt.json').exists():continue
   receipt=json.loads((folder/'receipt.json').read_text());raw,replay=load(sp)
   if hashlib.sha256(raw).hexdigest()!=receipt['stored_state_sha256'] or hashlib.sha256(gzip.decompress(raw)).hexdigest()!=receipt['state_sha256']:raise ValueError('replay state changed')
   if hashlib.sha256((folder/'config.json').read_bytes()).hexdigest()!=receipt['config_sha256']:raise ValueError('replay config changed')
   original=originals[endpoint['sample_id']]
   if endpoint['sample_id'] not in cache:cache[endpoint['sample_id']]=load(pathlib.Path(original['source_state']))
   source_raw,source=cache[endpoint['sample_id']]
   if hashlib.sha256(source_raw).hexdigest()!=endpoint['state_sha256']:raise ValueError('original state identity changed')
   actors=['t11_driver_eraser','t11_relay_pencil_case','t11_eyeglasses_case']
   def poses(frame):return {o['name']:o['position'] for o in frame['objects'] if o['name'] in actors}
   errors=[max(math.dist(poses(a)[n],poses(b)[n]) for n in actors) for a,b in zip(source['frames'],replay['frames'])]
   first=min([f['frame_index'] for f in source['frames'] if any(c.get('entity_a') in actors and c.get('entity_b') in actors for c in f.get('contacts',[]))],default=60)
   cfg=json.loads((folder/'config.json').read_text())
   out.append(dict(job_id=job['job_id'],family_id=job['family_id'],target_event=job['target_event'],sample_id=endpoint['sample_id'],mode=mode,theta=endpoint['theta'],
    expected_label=endpoint['label'],actual_label=receipt['label'],label_matches=receipt['label']==endpoint['label'],original_seed=endpoint['config'].get('random_seed'),replay_seed=cfg.get('random_seed'),
    dynamic_specs_match={o['name']:o['spec'] for o in source['dynamic_objects']}=={o['name']:o['spec'] for o in replay['dynamic_objects']},
    effective_properties_match=source.get('physics_debug',{}).get('effective_entity_properties')==replay.get('physics_debug',{}).get('effective_entity_properties'),
    first_original_dynamic_contact_frame=first,initial_position_error_m=errors[0],precontact_max_error_m=max(errors[:first],default=0),max_position_error_m=max(errors),
    first_error_over_1mm_frame=next((i for i,v in enumerate(errors) if v>.001),None),
    original_force_summary=source.get('runtime_force_summary'),replay_force_summary=replay.get('runtime_force_summary'),
    original_state_sha256=endpoint['state_sha256'],replay_state_sha256=receipt['state_sha256']))
print(json.dumps(out))
'''.replace('JOBS',repr(jobs)).replace('ORIGINALS',repr(originals))
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True,timeout=180)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    rows=json.loads(p.stdout);(ROOT/'t11_numeric_replay_diagnostics_20261020.json').write_text(json.dumps(rows,indent=2))
    summary=dict(examined_endpoint_replays=len(rows),by_mode={mode:dict(total=sum(r['mode']==mode for r in rows),outcome_mismatches=sum(r['mode']==mode and not r['label_matches'] for r in rows)) for mode in ['fixed_source_seed','own_published_seed']},
        planned_pairs_with_different_seed=sum(j['endpoints'][0]['config'].get('random_seed')!=j['endpoints'][1]['config'].get('random_seed') for j in jobs),
        dynamic_spec_mismatches=sum(not r['dynamic_specs_match'] for r in rows),effective_property_mismatches=sum(not r['effective_properties_match'] for r in rows),
        explicit_scope='Replay divergence measurements; do not infer a unique solver, renderer, seed or hardware cause from these alone.',original_reference_labels_unchanged=True)
    (ROOT/'t11_numeric_replay_diagnostic_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
