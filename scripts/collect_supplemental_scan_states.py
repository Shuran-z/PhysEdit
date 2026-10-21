"""Collect verified replay receipts; preserve original/replayed state provenance."""
import collections
import hashlib
import json
import inspect
import subprocess
from scripts.export_original_boundary_distances import ROOT,distances
from scripts.supplement_t09_published_support_boundaries import context
from scripts.state_integrity_cache import state_identity


def main():
    published={r['sample_id']:r for f in ROOT.glob('published_batch_*.json') for r in json.loads(f.read_text())}
    receipts=[];queues=[]
    t09='t09_missing_state_replay_v2_launch_20261020.json' if (ROOT/'t09_missing_state_replay_v2_launch_20261020.json').exists() else 't09_missing_state_replay_launch_20261020.json'
    for name in [t09,'t06_t10_missing_state_replay_launch_20261020.json']:
        path=ROOT/name
        if not path.exists():continue
        launch=json.loads(path.read_text(encoding='utf-8-sig'))
        code=r'''
import pathlib,json,gzip,hashlib,os
IDENTITY_FUNCTION
root=pathlib.Path(ROOT_DIRECTORY)
rows=json.loads((root/'status.json').read_text()) if (root/'status.json').exists() else []
cp=root/'collector_verified_state_cache.json';cache=json.loads(cp.read_text()) if cp.exists() else {}
for row in rows:
 if row['status']!='supplemental_original_backend_state':continue
 path=pathlib.Path(row['state_path']);key=state_identity(path,row)
 if cache.get(str(path))!=key:
  raw=path.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=row['stored_state_sha256']:raise ValueError('compressed state changed')
  if hashlib.sha256(gzip.decompress(raw)).hexdigest()!=row['state_sha256']:raise ValueError('numeric state changed')
  if state_identity(path,row)!=key:raise ValueError('state changed during verification')
  cache[str(path)]=key
 row['state_integrity_verification']='full digest checked, then cached against expected digests and unchanged filesystem identity'
temp=cp.with_name(cp.name+'.'+str(os.getpid())+'.tmp');temp.write_text(json.dumps(cache));temp.replace(cp)
print(json.dumps(dict(rows=rows,resource=json.loads((root/'resource_status.json').read_text()) if (root/'resource_status.json').exists() else {})))
'''.replace('ROOT_DIRECTORY',repr(launch['root'])).replace('IDENTITY_FUNCTION',inspect.getsource(state_identity))
        p=subprocess.run(['ssh','-o','BatchMode=yes',launch['host'],'python3 -'],input=code.encode(),capture_output=True,timeout=180)
        if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
        data=json.loads(p.stdout);queues.append(dict(root=launch['root'],resource=data['resource']))
        for r in data['rows']:
            if r['status']=='supplemental_original_backend_state' and r['source_config_sha256']!=published[r['sample_id']]['sha256']:raise ValueError('replay not bound to selected published config')
            receipts.append(dict(r,replay_root=launch['root']))
    (ROOT/'supplemental_original_scan_state_receipts_20261020.json').write_text(json.dumps(receipts,indent=2))
    # Preserve the previous 12 friction-event intervals; these new pull results
    # have their own source and cannot silently replace original annotations.
    originals=json.loads((ROOT/'t09_table_contact_events_20261020.json').read_text())
    measured={r['sample_id']:dict(r,reference_origin='original_annotation',published_video_event_confirmed=True) for r in originals if r['family_id']=='pull_force'}
    for r in receipts:
        if r.get('scene_id')!='T09' or r['status']!='supplemental_original_backend_state':continue
        source=published[r['sample_id']];c=source['config'];axis=c['experiment']['parameter']['parameter_name']
        measured[r['sample_id']]=dict(scene_id='T09',engine='genesis',sample_id=r['sample_id'],revision=source['revision'],family_id=axis,
            theta=c['experiment']['parameter']['parameter_value'],target_event=r['target_event'],reference_label=r['label'],
            reference_state_sha256=r['state_sha256'],source_config_sha256=r['source_config_sha256'],simulation_seed=r['seed'],
            fixed_context_sha256=context(c,axis),reference_origin=r['reference_origin'],published_video_event_confirmed=False)
    domains=collections.defaultdict(list)
    for r in published.values():
        if r['scene_id']=='T09' and r['config']['experiment']['parameter']['parameter_name']=='pull_force':
            c=r['config'];domains[context(c,'pull_force')].append(c['experiment']['parameter']['parameter_value'])
    groups=collections.defaultdict(list)
    for r in measured.values():groups[r['fixed_context_sha256']].append(r)
    bindings=[];plans=[];no_flip=[]
    for key,items in groups.items():
        items.sort(key=lambda r:r['theta']);domain=[min(domains[key]),max(domains[key])];span=domain[1]-domain[0];flips=[]
        for a,b in zip(items,items[1:]):
            if a['reference_label']==b['reference_label'] or a['theta']==b['theta']:continue
            bracket=[a['theta'],b['theta']];identity=dict(context=key,event=a['target_event'],bracket=bracket,hashes=[a['reference_state_sha256'],b['reference_state_sha256']])
            job_id=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24];flips.append(bracket)
            plans.append(dict(job_id=job_id,family_id='pull_force',fixed_context_sha256=key,target_event=a['target_event'],bracket=bracket,endpoint_labels=[a['reference_label'],b['reference_label']],endpoint_sample_ids=[a['sample_id'],b['sample_id']],base_config=published[a['sample_id']]['config']))
            for row in items:
                d=distances(row['theta'],bracket=bracket)
                bindings.append(dict(row,original_boundary_interval=bracket,**d,normalization_domain=domain,normalization_span=span,
                    normalized_distance_lower=d['distance_lower']/span,normalized_distance_upper=d['distance_upper']/span,
                    original_reference_kind='supplemental_original_backend_pull_scan_interval',refinement_job_id=job_id,
                    formal_nearacc_eligible=False,seed_scope='Seed-varied selected-source scan; fixed-seed refinement separate; replay labels are not silently treated as original video annotations.'))
        if not flips:no_flip.append(dict(context=key,observed_points=len(items),expected_points=len(set(domains[key])),status='no_flip_in_complete_scan' if len(items)==len(set(domains[key])) else 'partial_scan_no_flip_observed'))
    (ROOT/'t09_pull_supplemental_measured_events_20261020.json').write_text(json.dumps(list(measured.values()),indent=2))
    (ROOT/'t09_pull_supplemental_search_plan_20261020.json').write_text(json.dumps(plans,indent=2))
    (ROOT/'original_value_distance_ledger/t09_pull_supplemental_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bindings))
    summary=dict(queues=queues,completed_states=dict(collections.Counter(r.get('scene_id') for r in receipts if r['status']=='supplemental_original_backend_state')),
        failed_states=sum(r['status']=='failed' for r in receipts),pull_observed_points=len(measured),pull_local_intervals=len(plans),
        pull_bound_distinct_samples=len({r['sample_id'] for r in bindings}),contexts_without_observed_flip=no_flip,formal_new_admissions=0)
    (ROOT/'supplemental_scan_state_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
    from scripts.register_t06_t10_replay_distances import main as register_other_scenes
    register_other_scenes()


if __name__=='__main__':main()
