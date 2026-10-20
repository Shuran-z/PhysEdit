"""T09 visible collapse outcome: a non-pulled upper book rests on the table.

This event is narrower than all possible collapse outcomes. It does not label
coherent one-layer settling as collapse, nor equate event absence with absence
of every kind of collapse. Native contact supplies truth at the final frame.
"""
import collections
import hashlib
import json
from scripts.export_original_boundary_distances import ROOT, distances
from scripts.supplement_t09_published_support_boundaries import context

EVENT='upper_nonpulled_book_on_table_at_end'
TABLE='frozen_tabletop_collision_slab'


def final_event(config, initial_pairs, final_pairs):
    names=config['experiment']['supported_book_names']
    initial={frozenset(p) for p in initial_pairs}; final={frozenset(p) for p in final_pairs}
    if any(frozenset([TABLE,n]) in initial for n in names):
        raise ValueError('upper book already touches table before intervention')
    affected=[n for n in names if frozenset([TABLE,n]) in final]
    return dict(reference_label=int(bool(affected)),upper_books_on_table=affected)


def main():
    telemetry={r['sample_id']:r for r in json.loads((ROOT/'t09_original_support_contact_events.json').read_text())}
    published={r['sample_id']:r for p in ROOT.glob('published_batch_*.json') for r in json.loads(p.read_text()) if r['scene_id']=='T09'}
    groups=collections.defaultdict(list); measurements=[]
    for sid,state in telemetry.items():
        source=published[sid];c=source['config'];p=c['experiment']['parameter'];axis=p['parameter_name']
        measured=final_event(c,state['initial_pairs'],state['final_pairs'])
        row=dict(scene_id='T09',engine='genesis',sample_id=sid,revision=source['revision'],family_id=axis,
                 theta=p['parameter_value'],target_event=EVENT,reference_state_sha256=state['reference_state_sha256'],
                 fixed_context_sha256=context(c,axis),simulation_seed=c.get('seed'),**measured)
        groups[(axis,row['fixed_context_sha256'])].append(row);measurements.append(row)
    bindings=[];plans=[]
    for (axis,key),items in groups.items():
        items.sort(key=lambda r:r['theta']);domain=[items[0]['theta'],items[-1]['theta']];span=domain[1]-domain[0]
        for a,b in zip(items,items[1:]):
            if a['theta']==b['theta'] or a['reference_label']==b['reference_label']:continue
            bracket=[a['theta'],b['theta']]
            identity=dict(context=key,event=EVENT,bracket=bracket,source_state_sha256=[a['reference_state_sha256'],b['reference_state_sha256']])
            job=dict(job_id=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24],
                     family_id=axis,fixed_context_sha256=key,target_event=EVENT,bracket=bracket,
                     endpoint_labels=[a['reference_label'],b['reference_label']],endpoint_sample_ids=[a['sample_id'],b['sample_id']],
                     base_config=published[a['sample_id']]['config'])
            plans.append(job)
            for row in items:
                d=distances(row['theta'],bracket=bracket)
                bindings.append({**row,'original_boundary_interval':bracket,**d,'normalization_domain':domain,
                    'normalization_span':span,'normalized_distance_lower':d['distance_lower']/span,
                    'normalized_distance_upper':d['distance_upper']/span,'refinement_job_id':job['job_id'],
                    'original_reference_kind':'published_seed_varied_scan_interval_for_final_table_contact',
                    'target_definition':'At final frame, at least one originally supported non-pulled upper book contacts the tabletop; not a universal collapse label.',
                    'seed_scope':'Original seed-varied release scan; fixed-seed refinement separate.'})
    (ROOT/'t09_table_contact_events_20261020.json').write_text(json.dumps(measurements))
    (ROOT/'t09_table_contact_search_plan_20261020.json').write_text(json.dumps(plans))
    dest=ROOT/'original_value_distance_ledger/t09_table_contact_sample_distances.jsonl'
    dest.write_text(''.join(json.dumps(r)+'\n' for r in bindings))
    summary=dict(event=EVENT,original_states=len(measurements),positive=sum(r['reference_label'] for r in measurements),
                 negative=sum(1-r['reference_label'] for r in measurements),local_intervals=len(plans),
                 unique_samples_with_event_boundary=len({r['sample_id'] for r in bindings}),
                 formal_nearacc_admissions=0,scope='specified visible final event; no global collapse equivalence')
    (ROOT/'t09_table_contact_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
