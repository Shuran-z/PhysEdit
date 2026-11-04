"""Recover T02 C-family boundaries in the already-registered full window.

Read original published states only. Never modify old 5-second reports or run
a simulator. Output is a new immutable evidence file for the revised roster.
"""
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
BASE=ROOT/'review/scene_family_completion_20261018'

def sha(raw):return hashlib.sha256(raw).hexdigest()

def observe(state,end):
    frames=state['frames'];assert len(frames)==210
    baseline=state['render']['pre_static_frames']
    start=next(o['position'][0]for o in frames[baseline]['objects']if o['name']=='t02v2_signal_brass_ball')
    hits=[f['frame_index']for f in frames[baseline:end+1]
        if next(o['position'][0]for o in f['objects']if o['name']=='t02v2_signal_brass_ball')-start>=.05]
    return int(bool(hits)),min(hits,default=None)

def main():
    helper=ROOT/'review/core100_binding_20261028/recover_t02_existing_windows.py'
    spec=importlib.util.spec_from_file_location('original_t02_context',helper);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    records=json.loads((BASE/'t02_published_scoring_registry.json').read_text())
    retained=json.loads((ROOT/'benchmarks/core100_critical_pairs_v2_20261101/retained_distance_references.json').read_text())['cases']
    wanted={r['sample_id']:r for r in retained if r['clip_id'].startswith('T02')}
    points=[]
    for row in records:
        if row['family_id']!='C'or '__bg01_home_ase__'not in row['sample_id']:continue
        path=BASE/'t02_published_states'/(row['sample_id']+'.json.gz')
        if not path.exists():continue
        packed=path.read_bytes();assert sha(packed)==row['reference_state_sha256']
        raw=gzip.decompress(packed);state=json.loads(raw)
        assert state['render']['fps']==30
        observations={str(end):dict(zip(['label','event_frame'],observe(state,end)))for end in [154,209]}
        ctx=sha(json.dumps(module.context(state),sort_keys=True).encode())
        points.append(dict(sample_id=row['sample_id'],theta=row['theta'],observations=observations,
            original_displacement_baseline_frame=state['render']['pre_static_frames'],
            fixed_recorded_context_sha256=ctx,state_path=str(path.relative_to(ROOT)),
            stored_state_sha256=sha(packed),decoded_state_sha256=sha(raw)))
    cases=[]
    for sid,ref in wanted.items():
        scoped=[dict(p,**p['observations'][str(ref['end_frame_index'])])for p in points]
        source=next(p for p in scoped if p['sample_id']==sid)
        assert ref['source_state_sha256']in [source['stored_state_sha256'],source['decoded_state_sha256']]
        assert source['label']==ref['reference_events']['C2_signal_displaced_0p05m']
        group=[p for p in scoped if p['fixed_recorded_context_sha256']==source['fixed_recorded_context_sha256']]
        grouped={}
        for p in group:grouped.setdefault(p['theta'],[]).append(p)
        unique=[dict(theta=t,label=next(iter(labels))if len(labels)==1 else None,witnesses=values)
            for t,values in sorted(grouped.items())for labels in [{p['label']for p in values}]]
        intervals=[dict(event='C2_signal_displaced_0p05m',bracket=[a['theta'],b['theta']],
            endpoint_labels=[a['label'],b['label']],endpoints=[a['witnesses'],b['witnesses']])
            for a,b in zip(unique,unique[1:])if a['label']in [0,1]and b['label']==1-a['label']]
        cases.append(dict(clip_id=ref['clip_id'],sample_id=sid,reference_video_sha256=ref['reference_video_sha256'],
            parameter=ref['parameter'],theta=ref['theta'],source=source,
            normalization_domain=ref['normalization_domain'],normalization_span=ref['normalization_span'],
            target_event='C2_signal_displaced_0p05m',reference_label=source['label'],
            condition_frame_index=4,end_frame_index=ref['end_frame_index'],horizon_s=ref['horizon_s'],
            matched_points=len(group),unique_points=len(unique),conflicting_points=[p['theta']for p in unique if p['label']is None],
            intervals=intervals,all_points=unique,status='observed_original_full_window_interval_recovered'if intervals else'no_observed_full_window_interval',
            original_calibration_reference=copy.deepcopy(ref.get('original_calibration_reference')),
            new_simulations=0,claim='Observed published local interval only; no unique physical root or new RGB admission claimed.'))
    result=dict(schema='core100-v2-t02-full-window-recovery-v1',cases=cases,
        original_context_extractor_sha256=sha(helper.read_bytes()),generator_inputs_modified=False)
    raw=json.dumps(result,indent=2).encode();digest=sha(raw);WORK.mkdir(exist_ok=True)
    path=WORK/('t02_full_window_'+digest[:12]+'.json')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    pointer=dict(path=path.relative_to(ROOT).as_posix(),sha256=digest)
    (WORK/'T02_FULL_WINDOW.json').write_text(json.dumps(pointer,indent=2),encoding='utf8')
    print(json.dumps([dict(clip_id=r['clip_id'],status=r['status'],matched_points=r['matched_points'],
        conflicting=r['conflicting_points'],intervals=[v['bracket']for v in r['intervals']])for r in cases]))

if __name__=='__main__':main()
