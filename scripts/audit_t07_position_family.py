"""Check what original T07-B samples actually distinguish; do not invent a root."""
import collections
import gzip
import hashlib
import json
from scripts.export_original_boundary_distances import ROOT


def main():
    source=ROOT/'t07_measured_published_events.json';items=[r for r in json.loads(source.read_text()) if r['family_id']=='B_initial_longitudinal_position_m'];rows=[]
    for r in items:
        path=ROOT/'completion_states/T07'/(r['sample_id']+'.json.gz');raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('selected published T07 state changed')
        state=json.loads(gzip.decompress(raw));final=state['frames'][-1]
        if 'contacts' not in final:raise ValueError('T07 final contact telemetry missing')
        pairs={frozenset([c['entity_a'],c['entity_b']]) for c in final['contacts']}
        rows.append(dict(sample_id=r['sample_id'],theta=r['theta'],background=r['background'],gravity=r['gravity'],
            motion_ge_1cm=r['events']['motion_ge_1cm'],max_displacement_m=r['max_displacement_m'],state_sha256=r['sha256'],
            phone_ramp_contact_at_end=int(frozenset(['t07_smartphone','t07_document_folder_ramp']) in pairs),
            phone_table_contact_at_end=int(frozenset(['t07_smartphone','frozen_tabletop_collision_slab']) in pairs)))
    summary=dict(samples=len(rows),motion_labels=dict(collections.Counter(r['motion_ge_1cm'] for r in rows)),
        ramp_contact_labels=dict(collections.Counter(r['phone_ramp_contact_at_end'] for r in rows)),
        table_contact_labels=dict(collections.Counter(r['phone_table_contact_at_end'] for r in rows)),
        parameter_values=sorted({r['theta'] for r in rows}),observed_motion_boundary=False if len({r['motion_ge_1cm'] for r in rows})==1 else None,
        interpretation='Original B samples do not show a motion/no-motion flip. Retain them; do not reuse A/C roots or silently change the B target to manufacture a boundary.',formal_new_admissions=0)
    (ROOT/'t07_B_original_state_event_audit_20261020.json').write_text(json.dumps(dict(summary=summary,states=rows),indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
