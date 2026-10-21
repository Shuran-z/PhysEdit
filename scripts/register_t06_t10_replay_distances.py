"""Bind replay scan events as they finish, retaining original annotations separately."""
import collections
import copy
import hashlib
import inspect
import json
import math
import subprocess
from scripts.export_original_boundary_distances import ROOT, distances
from scripts.supplement_t06_published_boundaries import context as t06_context
from scripts.state_integrity_cache import state_identity


def replay_events(experiment, frames, tracked_metrics):
    if experiment['template_id']=='T06':
        if not any('contacts' in f for f in frames):raise ValueError('contact telemetry absent')
        contacts={tuple(sorted((c['entity_a'],c['entity_b']))) for f in frames for c in f.get('contacts',[])}
        pairs=experiment['required_contact_pairs']
        if not pairs:raise ValueError('required contact chain absent')
        labels={'adjacent_contact_'+str(i):int(tuple(sorted(pair)) in contacts) for i,pair in enumerate(pairs)}
        labels['complete_required_contact_chain']=int(all(labels.values()))
        return dict(labels=labels,required_contact_pairs=pairs)
    if experiment['template_id']=='T10':
        threshold=experiment['support_ejection_threshold_m']
        if not math.isfinite(threshold) or threshold<=0:raise ValueError('invalid source movement threshold')
        displacement=tracked_metrics['t10_support_pen']['max_displacement_m']
        if not math.isfinite(displacement):raise ValueError('nonfinite measured movement')
        return dict(labels={'support_pen_displacement_reaches_source_threshold':int(displacement>=threshold)},
                    threshold_m=threshold,measured_displacement_m=displacement)
    raise ValueError('unsupported scene')


def context(config, family):
    if config['experiment']['template_id']=='T06':return t06_context(config,family)
    c=copy.deepcopy(config);objects=c['dynamic_objects']
    for obj in objects:
        name=obj['name']
        if family=='v_roll' and name=='t10_tape_roll':
            obj['motion']['initial_velocity'][1]='<speed-controlled>'
            obj['motion']['initial_angular_velocity'][0]='<speed-controlled>'
        elif family=='support_x':
            if name in ['t10_tape_roll','t10_support_pen']:obj['pose']['position'][0]='<support-placement>'
            elif name=='t10_supported_folder':
                for axis in [0,2]:obj['pose']['position'][axis]='<support-dependent-folder-placement>'
                obj['pose']['euler_xyz'][1]='<support-dependent-folder-pitch>'
    if family not in ['v_roll','support_x']:raise ValueError('unknown T10 family')
    payload=dict(objects=objects,forces=c['runtime_forces'],scene=c['scene_overrides'],manifest=c.get('manifest'),
                 timing={k:c['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']},
                 threshold=c['experiment']['support_ejection_threshold_m'])
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def main():
    launch_path=ROOT/'t06_t10_missing_state_replay_launch_20261020.json'
    if not launch_path.exists():return
    launch=json.loads(launch_path.read_text());rule=inspect.getsource(replay_events)
    code=r'''
import pathlib,json,gzip,hashlib,math,os
RULE
IDENTITY_FUNCTION
root=pathlib.Path(ROOT_DIRECTORY);p=root/'status.json';rows=json.loads(p.read_text()) if p.exists() else [];out=[]
cp=root/'measured_scan_event_cache.json';cache=json.loads(cp.read_text()) if cp.exists() else {};rule_sha=hashlib.sha256(RULE_TEXT.encode()).hexdigest()
for row in rows:
 if row['status']!='supplemental_original_backend_state':continue
 path=pathlib.Path(row['state_path']);metrics_sha=hashlib.sha256(json.dumps(row['tracked_metrics'],sort_keys=True).encode()).hexdigest();key=state_identity(path,row)+[rule_sha,metrics_sha]
 if cache.get(str(path),{}).get('key')==key:
  out.append(cache[str(path)]['event']);continue
 stored=path.read_bytes();raw=gzip.decompress(stored)
 if hashlib.sha256(stored).hexdigest()!=row['stored_state_sha256'] or hashlib.sha256(raw).hexdigest()!=row['state_sha256']:raise ValueError('replay state changed')
 data=json.loads(raw);events=replay_events(data['experiment'],data['frames'],row['tracked_metrics'])
 event=dict(sample_id=row['sample_id'],scene_id=row['scene_id'],state_sha256=row['state_sha256'],source_config_sha256=row['source_config_sha256'],seed=row['seed'],**events)
 if state_identity(path,row)+[rule_sha,metrics_sha]!=key:raise ValueError('state changed during event measurement')
 cache[str(path)]=dict(key=key,event=event);out.append(event)
temp=cp.with_name(cp.name+'.'+str(os.getpid())+'.tmp');temp.write_text(json.dumps(cache));temp.replace(cp)
print(json.dumps(out))
'''.replace('RULE_TEXT',repr(rule)).replace('RULE',rule).replace('ROOT_DIRECTORY',repr(launch['root'])).replace('IDENTITY_FUNCTION',inspect.getsource(state_identity))
    p=subprocess.run(['ssh','-o','BatchMode=yes',launch['host'],'python3 -'],input=code.encode(),capture_output=True,timeout=180)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    evidence=json.loads(p.stdout);published={r['sample_id']:r for f in ROOT.glob('published_batch_*.json') for r in json.loads(f.read_text()) if r['scene_id'] in ['T06','T10']}
    domains=collections.defaultdict(list)
    for source in published.values():
        c=source['config'];family=c['experiment']['parameter']['parameter_name'];domains[(source['scene_id'],family,context(c,family))].append(c['experiment']['parameter']['parameter_value'])
    measured=[]
    for ev in evidence:
        source=published[ev['sample_id']];c=source['config'];axis=c['experiment']['parameter']
        if ev['source_config_sha256']!=source['sha256']:raise ValueError('selected release configuration mismatch')
        if ev['scene_id']=='T06' and ev['required_contact_pairs']!=c['experiment']['required_contact_pairs']:raise ValueError('event contract changed')
        if ev['scene_id']=='T10' and ev['threshold_m']!=c['experiment']['support_ejection_threshold_m']:raise ValueError('source threshold changed')
        measured.append(dict(scene_id=ev['scene_id'],engine='genesis',sample_id=ev['sample_id'],revision=source['revision'],family_id=axis['parameter_name'],theta=axis['parameter_value'],
            fixed_context_sha256=context(c,axis['parameter_name']),reference_state_sha256=ev['state_sha256'],source_config_sha256=source['sha256'],simulation_seed=ev['seed'],labels=ev['labels'],
            reference_origin='supplemental_replay_not_original_annotation',published_video_event_confirmed=False,event_rule_sha256=hashlib.sha256(rule.encode()).hexdigest()))
    # Merge original T06 observations; never overwrite their identity with a replay.
    originals={r['sample_id']:r for r in json.loads((ROOT/'t06_t09_surviving_original_state_evidence.json').read_text()) if r['scene_id']=='T06' and r['status']=='original_annotation_recovered'}
    for sid,ev in originals.items():
        if ev['dynamic_spec_mismatches'] or not ev.get('runtime_force_core_matches') or not ev.get('scene_consumed_physics_matches'):continue
        source=published[sid];c=source['config'];axis=c['experiment']['parameter'];contacts={tuple(p) for p in ev['observed_contact_pairs']}
        labels={'adjacent_contact_'+str(i):int(tuple(sorted(p)) in contacts) for i,p in enumerate(c['experiment']['required_contact_pairs'])};labels['complete_required_contact_chain']=int(all(labels.values()))
        measured.append(dict(scene_id='T06',engine='genesis',sample_id=sid,revision=source['revision'],family_id=axis['parameter_name'],theta=axis['parameter_value'],
            fixed_context_sha256=context(c,axis['parameter_name']),reference_state_sha256=ev['source_sha256'],source_config_sha256=source['sha256'],simulation_seed=c['seed'],labels=labels,
            reference_origin='original_annotation',published_video_event_confirmed=True))
    groups=collections.defaultdict(list)
    for row in measured:groups[(row['scene_id'],row['family_id'],row['fixed_context_sha256'])].append(row)
    output=[];windows=[]
    for key,items in groups.items():
        items.sort(key=lambda x:x['theta']);domain=[min(domains[key]),max(domains[key])];span=domain[1]-domain[0]
        for event in items[0]['labels']:
            for a,b in zip(items,items[1:]):
                if a['theta']==b['theta'] or a['labels'][event]==b['labels'][event]:continue
                window=dict(scene_id=key[0],family_id=key[1],fixed_context_sha256=key[2],target_event=event,bracket=[a['theta'],b['theta']],endpoint_sample_ids=[a['sample_id'],b['sample_id']]);windows.append(window)
                for row in items:
                    d=distances(row['theta'],bracket=window['bracket'])
                    output.append(dict({k:v for k,v in row.items() if k!='labels'},target_event=event,reference_label=row['labels'][event],original_boundary_interval=window['bracket'],**d,
                        normalization_domain=domain,normalization_span=span,normalized_distance_lower=d['distance_lower']/span,normalized_distance_upper=d['distance_upper']/span,
                        endpoint_sample_ids=window['endpoint_sample_ids'],original_reference_kind='seed_varied_original_backend_scan_interval',formal_nearacc_eligible=False,
                        scope='observed event scan; replay labels do not replace released-video labels; T10 movement is not automatically support loss'))
    out=ROOT/'original_value_distance_ledger'
    (out/'t06_t10_replay_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in output))
    (ROOT/'t06_t10_replay_measured_events_20261020.json').write_text(json.dumps(measured,indent=2))
    (ROOT/'t06_t10_replay_windows_20261020.json').write_text(json.dumps(windows,indent=2))
    summary=dict(completed_replay_states=dict(collections.Counter(r['scene_id'] for r in evidence)),
        event_intervals=dict(collections.Counter(w['scene_id'] for w in windows)),bound_distinct_samples={s:len({r['sample_id'] for r in output if r['scene_id']==s}) for s in ['T06','T10']})
    (ROOT/'t06_t10_replay_distance_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
