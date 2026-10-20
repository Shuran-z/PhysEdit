"""Compute T12 conditional boundary brackets from exact published simulations.

User selected target max tissue-box displacement >=1cm on 2026-10-19.
Each one-dimensional slice fixes the remaining physical inputs. These are
supplemental adjacent simulation brackets, not recovered original point values.
No extra visual/inversion/repeat validation gates distance computation.
"""
import collections
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path

from scripts.export_original_boundary_distances import distances

ROOT=Path('review/scene_family_completion_20261018')
AXES={'speed':('t12_stapler','motion','initial_velocity',0),'friction':('t12_stapler','friction'),'target_mass':('t12_tissue_box','mass')}


def fixed_context(config,axis):
    objects={o['name']:copy.deepcopy(o) for o in config['dynamic_objects']}
    path=AXES[axis];value=objects
    for k in path[:-1]:value=value[k]
    value[path[-1]]='<intervention>'
    scene={k:v for k,v in config['scene_overrides'].items() if not k.startswith('raytracing') and k!='use_raytracing'}
    payload=dict(objects=objects,scene=scene,manifest=config.get('manifest'),background_anchor=config.get('background_anchor'),runtime_forces=config.get('runtime_forces',[]),
        timing={k:config['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']},
        consumed_genesis_seed=None)
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def measure(frames):
    positions=[next(o['position'] for o in f['objects'] if o['name']=='t12_tissue_box') for f in frames]
    if not positions or any(not math.isfinite(x) for p in positions for x in p):raise ValueError('missing/nonfinite target trajectory')
    return max(math.dist(positions[0],p) for p in positions)


def main():
    source=ROOT/'t12_latest_verified_records_20261019.jsonl.gz';configs={};states={}
    with gzip.open(source,'rt',encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line);data=r['data']
            if '/configs/' in r['path']:configs[data['sample_id']]=r
            elif '/metadata_shared/' in r['path']:
                sid=Path(r['path']).name.removesuffix('.json').removesuffix('.gz')
                states[sid]=dict(path=r['path'],sha256=r['sha256'],max_displacement_m=measure(data['frames']))
    # Shared filenames are trajectory IDs, independent of camera labels.
    if configs.keys()!=states.keys():raise ValueError('T12 state/config identity mismatch')
    parameter_source={r['sample_id']:r for r in map(json.loads,(ROOT/'current_release_parameter_bindings_20261019.jsonl').read_text(encoding='utf-8').splitlines()) if r['scene']=='T12'}
    rows=[];groups=collections.defaultdict(list)
    for sid,record in configs.items():
        c=record['data'];p=parameter_source[sid];state=states[sid]
        for axis in AXES:
            row=dict(scene_id='T12',engine='genesis',sample_id=sid,axis=axis,family_id=axis,theta=p['values'][axis],fixed_context_sha256=fixed_context(c,axis),
                config_sha256=record['sha256'],state_sha256=state['sha256'],published_config_path=record['path'],published_state_path=state['path'],
                reference_label=int(state['max_displacement_m']>=.01),max_displacement_m=state['max_displacement_m'],target_event='tissue_box_max_displacement_ge_1cm',
                threshold_m=.01,parameter_unit={'speed':'m/s','friction':'dimensionless','target_mass':'kg'}[axis],revision=p['revision'])
            rows.append(row);groups[(axis,row['fixed_context_sha256'])].append(row)
    bindings=[];pending=[];plans=[]
    for (axis,context),items in groups.items():
        items.sort(key=lambda r:r['theta']);values=[r['theta'] for r in items]
        if len(values)!=len(set(values)):raise ValueError('duplicate T12 parameter in fixed slice')
        windows=[]
        for left,right in zip(items,items[1:]):
            if left['reference_label']==right['reference_label']:continue
            window=dict(bracket=[left['theta'],right['theta']],labels=[left['reference_label'],right['reference_label']],endpoint_sample_ids=[left['sample_id'],right['sample_id']],endpoint_state_sha256=[left['state_sha256'],right['state_sha256']])
            windows.append(window)
            plans.append(dict(job_id=hashlib.sha256(json.dumps(dict(axis=axis,context=context,window=window),sort_keys=True).encode()).hexdigest()[:24],axis=axis,fixed_context_sha256=context,
                window=window,endpoints=[dict(sample_id=x['sample_id'],theta=x['theta'],config=configs[x['sample_id']]['data'],config_sha256=x['config_sha256'],state_sha256=x['state_sha256'],label=x['reference_label']) for x in [left,right]],
                target_event='tissue_box_max_displacement_ge_1cm',threshold_m=.01))
        if not windows:
            pending.append(dict(axis=axis,fixed_context_sha256=context,samples=[r['sample_id'] for r in items],values=values,reason='fewer_than_two_parameter_values' if len(items)<2 else 'published_slice_has_no_observed_flip'));continue
        span=values[-1]-values[0]
        for row in items:
            for window in windows:
                bindings.append({**row,'original_boundary_interval':window['bracket'],**distances(row['theta'],bracket=window['bracket']),
                    'original_reference_kind':'supplemental_bracket_from_published_original_backend_states',
                    'normalization_domain':[values[0],values[-1]],'normalization_span':span,'normalized_distance_lower':distances(row['theta'],bracket=window['bracket'])['distance_lower']/span,
                    'normalized_distance_upper':distances(row['theta'],bracket=window['bracket'])['distance_upper']/span,
                    'source_file':str(source.resolve()),'endpoint_sample_ids':window['endpoint_sample_ids'],'endpoint_state_sha256':window['endpoint_state_sha256'],
                    'extra_validation_separate':True,'refinement_status':'adjacent_published_solver_samples; finer solver search queued separately'})
    target=ROOT/'original_value_distance_ledger';target.mkdir(exist_ok=True)
    (target/'t12_supplemental_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bindings),encoding='utf-8')
    (ROOT/'t12_supplemental_refinement_plan.json').write_text(json.dumps(plans),encoding='utf-8')
    (ROOT/'t12_conditional_slices_without_flip.json').write_text(json.dumps(pending,indent=2),encoding='utf-8')
    summary=dict(user_target='max tissue-box displacement >= 0.01 m',states=len(states),fixed_axis_slices=len(groups),local_brackets=len(plans),sample_interval_records=len(bindings),
        unique_samples_with_distance=len({r['sample_id'] for r in bindings}),by_axis=dict(collections.Counter(r['axis'] for r in plans)),remaining_slices=len(pending),
        scope='conditional supplemental intervals from existing published simulations, not original pre-render search records')
    (target/'t12_supplemental_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
