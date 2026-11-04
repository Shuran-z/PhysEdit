"""Native original-state readback at original 24fps; no replay or new threshold."""
import hashlib
import json
from pathlib import Path

ROOT=Path('/data2/liyuhan/core100_reference_admission_continue_20261101')
rows=[]
for job in json.loads((ROOT/'JOBS.json').read_text()):
    if not job['clip_id'].startswith('T13'):continue
    path=Path(job['header']['path']);raw=path.read_bytes();state=json.loads(raw)
    assert hashlib.sha256(raw).hexdigest()==job['reference_state_sha256']
    fps=state['render']['fps'];period=state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame']
    assert fps==24 and abs(period-1/fps)<1e-12
    start=job['condition_frame_index'];end=start+int(job['horizon_s']*fps)
    assert end==124 and len(state['frames'])==168
    frames=state['frames'][start:end+1]
    pairs=[{'t13_driver_book','t13_falling_book'},{'t13_falling_book','t13_drink_box'}]
    first=[]
    for pair in pairs:
        hits=[(f['frame_index'],c.get('physics_step_index',-1))for f in frames for c in f.get('contacts',[])
              if {c.get('entity_a'),c.get('entity_b')}==pair]
        first.append(min(hits)if hits else None)
    assert all(first) and first[0]<first[1]
    rows.append(dict(clip_id=job['clip_id'],reference_state_sha256=job['reference_state_sha256'],
        reference_video_sha256=job['sha256'],native_fps=fps,physical_frame_period_s=period,
        condition_frame_index=start,end_frame_index=end,horizon_s=job['horizon_s'],
        reference_events=dict(driver_to_falling_book_contact=1,falling_book_to_drink_contact=1,registered_two_contact_conjunction_and_order=1),
        first_native_contacts=first,old_generic_end_frame_index=job['end_frame_index'],
        metadata_endpoint_correction_only=True,old_labels_or_scores_changed=False))
(ROOT/'T13_ORIGINAL_WINDOW.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
