"""Use original event definitions to compute missing T04/T05 local brackets."""
import collections
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path

from scripts.audit_t04_completion_states import fixed_context
from scripts.export_original_boundary_distances import distances

ROOT=Path('review/scene_family_completion_20261018')


def support_release_record(row):
    path=Path(row['local_path']);raw=path.read_bytes();data=json.loads(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw)
    if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('published state identity changed')
    name='t04v3_removable_support_bar';track=[next(o['position'][1] for o in f['objects'] if o['name']==name) for f in data['frames']]
    maximum=max(abs(x-track[0]) for x in track)
    threshold=data['experiment']['parameter']['estimated_support_release_threshold_m']
    if not math.isfinite(threshold):raise ValueError('missing original clearance threshold')
    clone=copy.deepcopy({k:v for k,v in data.items() if k!='frames'})
    for entry in clone['dynamic_objects']:
        if entry['spec']['name']==name:entry['spec']['motion']['initial_velocity'][1]='<intervention>'
    return {**row,'target_event':'support_bar_displacement_reaches_original_release_clearance','reference_label':int(maximum>=threshold),
        'fixed_context_sha256':fixed_context(clone,None),'original_release_threshold_m':threshold,'max_support_displacement_m':maximum}


def main():
    rows=[]
    for r in json.loads((ROOT/'t04_measured_published_events.json').read_text(encoding='utf-8')):
        family=r['family_id']
        if family=='support_release':rows.append(support_release_record(r))
        elif family=='stack_sliding':rows.append({**r,'target_event':'stack_motion','reference_label':r['events']['stack_motion']})
        elif family=='terminal_transfer' and r['events']['can2_mug_contact'] is not None:
            rows.append({**r,'target_event':'can2_mug_contact_and_rotation_ge_18deg','reference_label':int(r['events']['can2_mug_contact'] and r['metrics']['t04v3_chain_mug']['rotation']>=18.)})
    for r in json.loads((ROOT/'t05_measured_published_events.json').read_text(encoding='utf-8')):
        event={'gate_passage':'gate_passage','terminal_transfer':'terminal_contact'}.get(r['family_id'])
        if event and r['events'][event] is not None:rows.append({**r,'target_event':event,'reference_label':r['events'][event]})
    groups=collections.defaultdict(list)
    for r in rows:
        groups[(r['sample_id'][:3],r['family_id'],r['fixed_context_sha256'],r['repeat'])].append(r)
    bindings=[];windows=[];pending=[]
    for key,items in groups.items():
        values=collections.defaultdict(list)
        for r in items:values[r['theta']].append(r)
        usable={theta:rr for theta,rr in values.items() if len({r['reference_label'] for r in rr})==1}
        local=[]
        for a,b in zip(sorted(values),sorted(values)[1:]):
            if a not in usable or b not in usable:continue
            left,right=usable[a][0],usable[b][0]
            if left['reference_label']==right['reference_label']:continue
            window=dict(scene_id=key[0],family_id=key[1],fixed_context_sha256=key[2],repeat=key[3],target_event=left['target_event'],bracket=[a,b],labels=[left['reference_label'],right['reference_label']],endpoint_sample_ids=[left['sample_id'],right['sample_id']],endpoint_state_sha256=[left['sha256'],right['sha256']])
            windows.append(window);local.append(window)
        if not local:pending.append(dict(context=key,sample_ids=[r['sample_id'] for r in items],reason='no_published_opposite_event_endpoints'));continue
        for r in items:
            for window in local:
                bindings.append(dict(scene_id=key[0],engine='genesis',sample_id=r['sample_id'],family_id=key[1],theta=r['theta'],target_event=r['target_event'],reference_label=r['reference_label'],
                    revision=r['revision'],repo_id=r['repo_id'],published_state_path=r['sidecar'],reference_state_sha256=r['sha256'],original_boundary_interval=window['bracket'],
                    **distances(r['theta'],bracket=window['bracket']),endpoint_sample_ids=window['endpoint_sample_ids'],endpoint_state_sha256=window['endpoint_state_sha256'],
                    original_reference_kind='supplemental_interval_from_original_published_states',extra_validation_separate=True))
    out=ROOT/'original_value_distance_ledger';out.mkdir(exist_ok=True)
    (out/'t04_t05_supplemental_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bindings),encoding='utf-8')
    (ROOT/'t04_t05_supplemental_windows.json').write_text(json.dumps(windows,indent=2))
    (ROOT/'t04_t05_slices_without_flip.json').write_text(json.dumps(pending,indent=2))
    summary=dict(event_rows=len(rows),local_intervals=len(windows),by_scene=dict(collections.Counter(r['scene_id'] for r in windows)),sample_interval_records=len(bindings),unique_samples=len({r['sample_id'] for r in bindings}),remaining_contexts=len(pending))
    (out/'t04_t05_supplemental_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
