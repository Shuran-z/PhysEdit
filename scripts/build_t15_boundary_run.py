"""Build a two-point T15 development pilot; no assumption of an exact threshold."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from physedit.boundary import digest, write_rows, write_json


def build(audit_root, out, condition_root=None):
    audit_root, out=Path(audit_root), Path(out)
    out.mkdir(parents=True,exist_ok=False)
    old=[json.loads(s) for s in (audit_root/'generation_inputs.jsonl').read_text(encoding='utf-8').splitlines()]
    answers={r['sample_id']:r for r in map(json.loads,(audit_root/'answer_key.jsonl').read_text(encoding='utf-8').splitlines())}
    audit=json.loads((audit_root/'reference_audit.json').read_text(encoding='utf-8'))
    source={r['sample_id']:r for r in audit['rows']}
    event_names=['book_contacts_laptop','laptop_crosses_support_boundary','laptop_falls_to_floor',
                 'laptop_contacts_phone','phone_slides']
    rows, keys=[],[]
    for i,slot in enumerate(('A1','A2')):
        sid=f'g03_earth_{slot}_correct_parameter_s0'
        r=next(x for x in old if x['sample_id']==sid)
        key=answers[sid]; reference=source[key['reference_sample_id']]
        image=audit_root/'conditioning'/'g03_earth.png'
        condition=condition_root.rstrip('/')+'/'+image.name if condition_root else str(image.resolve())
        # Distinct seed streams across points; results are an independent-pair pilot (K=1).
        prompt=(f'Fixed camera. A book slides toward a closed laptop on a table; a phone rests on the floor. '
                f'The book starts at {key["target_speed_mps"]} m/s toward the laptop. Gravity is 9.81 m/s^2. '
                'Masses: book 0.58 kg, laptop 1.35 kg, phone 0.19 kg. '
                'No further actuation. Preserve objects and geometry; show six seconds of physical motion.')
        rows.append(dict(sample_id=f't15_earth_{slot}_s0',condition_image=condition,
             condition_sha256=digest(image),prompt=prompt,seed=39100+100*i,
             num_frames=161,fps=25,evaluation_duration_s=6.0,source_width=854,source_height=480,
             width=704,height=480,condition_frame_index=29,condition_time_s=29/30,
             trigger_time_s=1.,observation_end_s=209/30))
        keys.append(dict(sample_id=rows[-1]['sample_id'],scene_id='T15',source_group_id=r['group_id'],
             family_id='T15_Genesis_V11_home_earth_A',point_id=slot,theta=key['target_speed_mps'],
             target_event='laptop_falls_to_floor',events=dict(zip(event_names,key['reference_events'])),
             required_order=[['book_contacts_laptop','laptop_crosses_support_boundary'],
                             ['laptop_crosses_support_boundary','laptop_falls_to_floor']],
             inversion=dict(status='not_applicable' if not key['reference_events'][2] else 'pending_reference_validation',
               reason='reference_has_no_laptop_fall' if not key['reference_events'][2] else 'T15_has_no_frozen_reference_inversion_registration'),
             gravity=9.81,boundary=dict(status='unavailable',reason='full_search_record_not_yet_bound'),
             pair_ids=['earth_A_sparse_opposite_outcomes'],reference_sample_id=key['reference_sample_id'],
             reference_config_sha256=reference['config_sha256'],reference_state_sha256=reference['state_sha256'],
             reference_output=reference['output'],reference_event_frames=reference['event_frames'],
             split='development',metric_development_seen=True))
    write_rows(out/'inputs.jsonl',rows);write_rows(out/'answers.jsonl',keys)
    write_json(out/'provenance.json',dict(source_audit_sha256=digest(audit_root/'reference_audit.json'),
       source_inputs_sha256=digest(audit_root/'generation_inputs.jsonl'),
       status='sparse_branch_pilot_not_certified_distance_benchmark',registered=2,
       inversion_not_applicable=1,inversion_pending_reference=1,new_reference_rendering=False))
    return rows,keys


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit-root',default='review/t15_boundary_pilot_20261014')
    p.add_argument('--out',required=True)
    p.add_argument('--condition-root')
    a=p.parse_args();build(a.audit_root,a.out,a.condition_root)
