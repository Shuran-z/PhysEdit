"""Original T09 support-graph events from surviving native contact telemetry.

Each event means loss of a specific original adjacent support contact by the
final frame, relative to pre-pull frame 9. It is not renamed global collapse.
Diagnostic only: user retained the original collapse predicate, which this
contact-graph calculation must not replace in the official distance catalog.
"""
import collections
import copy
import hashlib
import json
import subprocess

from scripts.export_original_boundary_distances import ROOT, distances

REMOTE=r'''
import concurrent.futures,hashlib,json,pathlib,re
def read(r):
 raw=pathlib.Path(r['source_path']).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=r['source_sha256']:raise ValueError('original state changed')
 text=raw.decode();decoder=json.JSONDecoder()
 def frame(index):
  m=re.search(r'(?m)^      "frame_index": '+str(index)+r',',text)
  if m is None:raise ValueError('missing original frame')
  start=text.rfind('{',0,m.start());return decoder.raw_decode(text,start)[0]
 def pairs(f):return {tuple(sorted([v['entity_a'],v['entity_b']])) for v in f.get('contacts',[])}
 initial,final=pairs(frame(9)),pairs(frame(209));events={}
 for i in range(3,7):
  pair=('t09_book_%02d'%i,'t09_book_%02d'%(i+1))
  if pair in initial:events['original_support_contact_%02d_%02d_lost_at_end'%(i,i+1)]=int(pair not in final)
 return dict(sample_id=r['sample_id'],events=events,reference_state_sha256=r['source_sha256'],initial_pairs=sorted(initial),final_pairs=sorted(final))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(read,INPUT))
print(json.dumps(result))
'''


def context(config,axis):
    objects=copy.deepcopy(config['dynamic_objects']);forces=copy.deepcopy(config['runtime_forces'])
    if axis=='layer_friction':
        for o in objects:
            if o['name'].startswith('t09_book_'):
                o['friction']='<layer-friction>'
                if 'friction' in o.get('material_preset',{}):o['material_preset']['friction']='<layer-friction>'
    elif axis=='pull_force':
        for force in forces:
            if force['target']=='t09_book_03':
                if force['force_world'][1:]!=[0.,0.]:raise ValueError('T09 force direction differs from original pull recipe')
                force['force_world']='<original-pull-amplitude-recipe>'
    else:raise ValueError('unknown original T09 parameter')
    return hashlib.sha256(json.dumps(dict(objects=objects,forces=forces,scene=config['scene_overrides'],manifest=config.get('manifest'),room=config.get('room_boundary'),
        timing={k:config['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']}),sort_keys=True).encode()).hexdigest()


def main():
    evidence=[r for r in json.loads((ROOT/'t06_t09_surviving_original_state_evidence.json').read_text(encoding='utf-8')) if r['scene_id']=='T09' and r['status']=='original_annotation_recovered'
        and not r['dynamic_spec_mismatches'] and r.get('runtime_force_core_matches') and r.get('scene_consumed_physics_matches')]
    cache=ROOT/'t09_original_support_contact_events.json'
    telemetry=json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else []
    expected={(r['sample_id'],r['source_sha256']) for r in evidence}
    if {(r['sample_id'],r['reference_state_sha256']) for r in telemetry}!=expected:
        p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=REMOTE.replace('INPUT',repr(evidence)).encode(),capture_output=True,timeout=300)
        p.check_returncode();telemetry=json.loads(p.stdout)
        cache.write_text(json.dumps(telemetry),encoding='utf-8')
    states={r['sample_id']:r for r in telemetry}
    groups=collections.defaultdict(list)
    for path in ROOT.glob('published_batch_*.json'):
        for r in json.loads(path.read_text(encoding='utf-8')):
            if r['sample_id'] not in states:continue
            c=r['config'];param=c['experiment']['parameter'];axis=param['parameter_name'];state=states[r['sample_id']]
            row=dict(scene_id='T09',engine='genesis',sample_id=r['sample_id'],family_id=axis,theta=param['parameter_value'],revision=r['revision'],simulation_seed=c.get('seed'),
                source_config_sha256=r['sha256'],reference_state_sha256=state['reference_state_sha256'],events=state['events'])
            groups[(axis,context(c,axis))].append(row)
    windows=[];rows=[]
    for (axis,key),items in groups.items():
        ordered=sorted(items,key=lambda r:r['theta'])
        for event in set.intersection(*(set(r['events']) for r in items)):
            for a,b in zip(ordered,ordered[1:]):
                if a['theta']==b['theta'] or a['events'][event]==b['events'][event]:continue
                w=dict(family_id=axis,fixed_context_sha256=key,target_event=event,bracket=[a['theta'],b['theta']],endpoint_sample_ids=[a['sample_id'],b['sample_id']],endpoint_simulation_seeds=[a['simulation_seed'],b['simulation_seed']]);windows.append(w)
                for r in items:rows.append({**{k:v for k,v in r.items() if k!='events'},**w,'original_boundary_interval':w['bracket'],**distances(r['theta'],bracket=w['bracket']),
                    'reference_label':r['events'][event],'original_reference_kind':'supplemental_interval_from_original_published_seed_varied_scan',
                    'seed_scope':'Original released seed-varied parameter scan; no same-seed exact threshold claim.',
                    'target_definition':'Specific original adjacent contact present before pull (frame 9) and absent at final frame 209; not a global-collapse label.'})
    out=ROOT/'original_value_distance_ledger'
    (ROOT/'t09_support_contact_diagnostic_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    (ROOT/'t09_support_contact_diagnostic_windows.json').write_text(json.dumps(windows,indent=2),encoding='utf-8')
    summary=dict(original_states=len(states),conditional_physical_contexts=len(groups),local_event_intervals=len(windows),sample_event_interval_records=len(rows),unique_samples=len({r['sample_id'] for r in rows}))
    summary['official_collapse_reference']=False
    (ROOT/'t09_support_contact_diagnostic_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':main()
