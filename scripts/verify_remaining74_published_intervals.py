"""Recheck existing published endpoints; no bisection, midpoint or new threshold."""
import gzip
import hashlib
import json
from pathlib import Path
from scripts.recover_core100_released_scans import read_point

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_remaining74_admission_20261101'
registry=json.loads((ROOT/'annotation_site/resources/core100_distance_bindings.json').read_text(encoding='utf8'))
decisions={d['clip_id']:d for d in json.loads((WORK/'ADMISSION_DECISIONS.json').read_text())}
readback={r['clip_id']:r for r in json.loads((WORK/'native_readback/READBACK.json').read_text())}
out=[]
for ref in registry['cases']:
    cid=ref['clip_id'];scene=cid[:3]
    if cid not in decisions or scene not in ('T01','T04','T08') or ref['binding_kind']!='released_state_scan':continue
    event=decisions[cid]['target_event'];boundary=next((b for b in ref['boundary_records']if b['event']==event),None)
    if not boundary:continue
    row=dict(clip_id=cid,target_event=event,reference_video_sha256=ref['reference_video_sha256'],
             condition_frame_index=ref['condition_frame_index'],end_frame_index=ref['end_frame_index'],horizon_s=ref['horizon_s'],
             original_boundary_interval=boundary['bracket'],original_labels=boundary['endpoint_labels'],points=[])
    try:
        source=ROOT/'review/scene_family_completion_20261018/completion_states'/scene/(ref['sample_id']+'.json.gz')
        fresh=read_point(source,scene);native=readback[cid]['points'][0]
        assert fresh['state_sha256']==native['decoded_state_sha256'],'source state differs from exact active sidecar'
        assert fresh['labels'][event]==ref['reference_events'][event]
        row['verified_intervals']=[]
        for candidate in [b for b in ref['boundary_records']if b['event']==event]:
            for endpoint,label in zip(candidate['endpoints'],candidate['endpoint_labels']):
                assert endpoint
                for point in endpoint:
                    p=read_point(Path(point['state_path']),scene)
                    assert p['state_sha256']==point['state_sha256'] and p['labels'][event]==label,'endpoint bytes/label differs'
                    assert p['fixed_context_sha256']==fresh['fixed_context_sha256'],'fixed original context differs'
                    raw=gzip.decompress(Path(point['state_path']).read_bytes());s=json.loads(raw)
                    period=s['scene_overrides']['dt']*s['render']['physics_steps_per_render_frame']
                    assert (ref['end_frame_index']-ref['condition_frame_index'])*period==ref['horizon_s']==5
                    assert any(abs(p['theta']-t)<1e-8 for t in candidate['bracket'])
                    row['points'].append(p)
            assert candidate['endpoint_labels'][0]!=candidate['endpoint_labels'][1]
            row['verified_intervals'].append(dict(bracket=candidate['bracket'],labels=candidate['endpoint_labels']))
        row.update(status='verified_original_published_interval',source=fresh,
                   claim='Existing observed local interval only; no global nearest or unique physical root claim')
    except Exception as error:row.update(status='pending',error=str(error),error_type=type(error).__name__)
    out.append(row)
path=WORK/'PUBLISHED_INTERVAL_READBACK.json';path.write_text(json.dumps(out,indent=2))
print(json.dumps([dict(clip_id=r['clip_id'],status=r['status'],error=r.get('error'))for r in out]))
