"""Original T06 scan transitions for the declared adjacent-contact chain.

Seeds remain recorded. These are observed scan intervals, not same-seed exact
thresholds. Only original recipe-controlled geometry/force fields are removed
from the fixed physical-context fingerprint.
"""
import collections
import copy
import hashlib
import json

from scripts.export_original_boundary_distances import ROOT, distances


def context(config,family):
    objects=copy.deepcopy(config['dynamic_objects']);forces=copy.deepcopy(config['runtime_forces'])
    if family=='gap':
        for o in objects:
            if o['name'].startswith('t06_book_'):o['pose']['position'][0]='<gap-controlled-placement>'
    elif family=='impact_force':
        for f in forces:
            if f['target']=='t06_book_00':
                x,y,z=f['force_world']
                if abs(y)>1e-9 or abs(z-.08*x)>2e-7:raise ValueError('T06 force direction differs from original amplitude recipe')
                f['force_world']='<original-impact-amplitude-recipe>'
    else:raise ValueError('unknown original T06 scan axis')
    return hashlib.sha256(json.dumps(dict(objects=objects,forces=forces,scene=config['scene_overrides'],manifest=config.get('manifest'),
        room_boundary=config.get('room_boundary'),timing={k:config['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']}),sort_keys=True).encode()).hexdigest()


def main():
    evidence={r['sample_id']:r for r in json.loads((ROOT/'t06_t09_surviving_original_state_evidence.json').read_text(encoding='utf-8')) if r['scene_id']=='T06' and r['status']=='original_annotation_recovered'}
    groups=collections.defaultdict(list)
    for path in ROOT.glob('published_batch_*.json'):
        for r in json.loads(path.read_text(encoding='utf-8')):
            if r['sample_id'] not in evidence:continue
            e=evidence[r['sample_id']];c=r['config'];p=c['experiment']['parameter'];family=p['parameter_name']
            if e['dynamic_spec_mismatches'] or not e.get('runtime_force_core_matches') or not e.get('scene_consumed_physics_matches'):continue
            contacts={tuple(pair) for pair in e['observed_contact_pairs']}
            labels={'adjacent_contact_'+str(i):int(tuple(sorted(pair)) in contacts) for i,pair in enumerate(c['experiment']['required_contact_pairs'])}
            labels['complete_required_contact_chain']=int(all(labels.values()))
            row=dict(scene_id='T06',engine='genesis',sample_id=r['sample_id'],family_id=family,theta=p['parameter_value'],revision=r['revision'],
                source_config_sha256=r['sha256'],reference_state_sha256=e['source_sha256'],source_state_path=e['source_path'],simulation_seed=c.get('seed'),labels=labels)
            groups[(family,context(c,family))].append(row)
    windows=[];rows=[]
    for (family,key),items in groups.items():
        ordered=sorted(items,key=lambda r:r['theta'])
        for event in ordered[0]['labels']:
            for a,b in zip(ordered,ordered[1:]):
                if a['theta']==b['theta'] or a['labels'][event]==b['labels'][event]:continue
                w=dict(family_id=family,fixed_context_sha256=key,target_event=event,bracket=[a['theta'],b['theta']],endpoint_sample_ids=[a['sample_id'],b['sample_id']],endpoint_simulation_seeds=[a['simulation_seed'],b['simulation_seed']]);windows.append(w)
                for r in items:rows.append({**{k:v for k,v in r.items() if k!='labels'},**w,'original_boundary_interval':w['bracket'],**distances(r['theta'],bracket=w['bracket']),
                    'reference_label':r['labels'][event],'original_reference_kind':'supplemental_interval_from_original_published_seed_varied_scan',
                    'seed_scope':'Original released parameter scan with recorded initialization seeds; no same-seed threshold claim.',
                    'target_definition':'Recorded contact between original required adjacent books; chain completion requires every adjacent pair, without adding a tilt threshold.'})
    out=ROOT/'original_value_distance_ledger'
    (out/'t06_supplemental_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    (ROOT/'t06_supplemental_windows.json').write_text(json.dumps(windows,indent=2),encoding='utf-8')
    summary=dict(recovered_original_states=len(evidence),physical_contexts=len(groups),local_event_intervals=len(windows),sample_event_interval_records=len(rows),unique_samples=len({r['sample_id'] for r in rows}),families=dict(collections.Counter(w['family_id'] for w in windows)))
    (out/'t06_supplemental_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':main()
