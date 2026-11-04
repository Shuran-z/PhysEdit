"""Recover original T07 friction contrasts from saved published states only."""
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path

from physedit.core100_critical import load
from scripts.recover_core100_released_scans import intervals, normalized

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
PHYSICS=['gravity','dt','substeps','physics_steps_per_render_frame','solver_iterations',
    'settle_steps','record_contacts','static_scene_collision','layout_collision',
    'add_ground_plane','room_wall_colliders','room_boundary_safety','use_gjk_collision',
    'enable_multi_contact','box_box_detection','constraint_timeconst']


def point(path):
    raw=path.read_bytes();decoded=gzip.decompress(raw);state=json.loads(decoded)
    specs={o['name']:copy.deepcopy(o.get('spec',o))for o in state['dynamic_objects']}
    theta=specs['t07_smartphone'].pop('friction')
    context=normalized(dict(objects=specs,physics={k:state['scene_overrides'].get(k)for k in PHYSICS},
        pre_static_frames=state['render']['pre_static_frames']))
    key=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
    frames=state['frames'];assert len(frames)==210
    period=state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame']
    assert abs(period*150-5)<1e-12
    def position(f):return next(o['position']for o in f['objects']if o['name']=='t07_smartphone')
    initial=position(frames[4]);distances=[math.dist(initial,position(f))for f in frames[5:155]]
    return dict(sample_id=path.name[:-8],theta=theta,
        labels=dict(motion_ge_1cm=int(max(distances)>=.01)),maximum_displacement_m=max(distances),
        fixed_context_sha256=key,state_path=path.relative_to(ROOT).as_posix(),
        stored_state_sha256=hashlib.sha256(raw).hexdigest(),state_sha256=hashlib.sha256(decoded).hexdigest(),
        baseline_frame=4,end_frame_index=154,horizon_s=5.0,
        source_video=state['render'].get('save_video'))


def main():
    registry,_=load();wanted=[r for r in registry['cases']if r['scene_id']=='T07']
    points=[]
    for path in (ROOT/'review/scene_family_completion_20261018/completion_states/T07').glob('*.gz'):
        points.append(point(path))
    by_id={p['sample_id']:p for p in points};cases=[]
    for ref in wanted:
        source=by_id[ref['sample_id']]
        assert ref['source_state_sha256']in[source['stored_state_sha256'],source['state_sha256']]
        assert source['theta']==ref['theta']and source['labels']['motion_ge_1cm']==ref['reference_events']['motion_ge_1cm']
        own=[p for p in points if p['fixed_context_sha256']==source['fixed_context_sha256']]
        boundaries,unique=intervals(own,'motion_ge_1cm')
        cases.append(dict(clip_id=ref['clip_id'],reference_video_sha256=ref['reference_video_sha256'],
            source=source,matched_points=len(own),ambiguous_points=sum(p['label']is None for p in unique),
            original_family=ref['parameter'],normalization_domain=ref['normalization_domain'],
            intervals=boundaries,horizon_s=5.0,condition_frame_index=4,end_frame_index=154,
            fixed_context_fields='All original object specifications except the phone friction; original solver and clock.',
            scope='Observed original published contrasts; no same-random-seed, unique-root or numerical-convergence claim.'))
    report=dict(schema='core100-t07-original-published-friction-readback-v1',cases=cases,
        saved_points_read=len(points),simulations_started=0,original_files_modified=False)
    raw=json.dumps(report,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('t07_published_'+digest[:12]+'.json')
    if not path.exists():path.write_bytes(raw)
    else:assert path.read_bytes()==raw
    (WORK/'T07_PUBLISHED.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps([dict(clip_id=c['clip_id'],matched=c['matched_points'],ambiguous=c['ambiguous_points'],
        intervals=[b['bracket']for b in c['intervals']])for c in cases]))


if __name__=='__main__':main()
