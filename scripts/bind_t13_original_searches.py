"""Match recovered search physics to current T13 samples, retaining all local transitions."""
import collections
import json
from pathlib import Path

from physedit.boundary import digest,distance
from scripts.measure_t13_current_release import context

ROOT=Path('review/scene_family_completion_20261018')


def main():
    current=json.loads((ROOT/'t13_current_measured_events_20261019.json').read_text(encoding='utf-8'))
    source=ROOT/'t13_original_measured_search_results_20261019.json'
    records=json.loads(source.read_text(encoding='utf-8'));groups=collections.defaultdict(list)
    for r in records:
        c=r['config'];meta=c['sample_metadata'];family=meta['main_parameter_name'];theta=meta['main_parameter_value']
        if family not in ['drink_edge_distance','driver_pivot_gap','book_cluster_shift_toward_drink']:continue
        signature=context(c,family,theta,r['runtime_objects'])
        groups[(family,signature)].append(dict(theta=theta,metrics=r['metrics'],config_sha256=r['config_sha256'],state_sha256=r['state_sha256'],source_round=r['source_round']))
    registrations=[];matched_groups=set();conflicts=[]
    for row in current:
        key=(row['family'],row['fixed_context_sha256']);points=groups.get(key)
        if not points:continue
        matched_groups.add(key)
        event_map={'t13_drink_box_motion_ge_1cm':'motion_ge_1cm','drink_drop_ge_5cm':'drop_ge_5cm'}
        for event,metric in event_map.items():
            bytheta=collections.defaultdict(list)
            for point in points:bytheta[point['theta']].append(point)
            consistent={theta:rr for theta,rr in bytheta.items() if len({r['metrics']['t13_drink_box'][metric] for r in rr})==1}
            if row['theta'] in consistent and row['events'][event]!=consistent[row['theta']][0]['metrics']['t13_drink_box'][metric]:
                conflicts.append(dict(sample_id=row['sample_id'],target_event=event,reason='published/recovered_search_label_conflict'));continue
            intervals=[]
            ordered=sorted(consistent)
            for a,b in zip(ordered,ordered[1:]):
                left,right=consistent[a][0],consistent[b][0]
                if left['metrics']['t13_drink_box'][metric]!=right['metrics']['t13_drink_box'][metric]:
                    intervals.append(dict(bracket=[a,b],labels=[left['metrics']['t13_drink_box'][metric],right['metrics']['t13_drink_box'][metric]],source_state_sha256=[left['state_sha256'],right['state_sha256']]))
            if not intervals:continue
            family_values=[r['theta'] for r in current if r['family']==row['family'] and r['background']==row['background'] and r['gravity']==row['gravity']]
            span=max(family_values)-min(family_values)
            registrations.append(dict(engine='genesis',scene_id='T13',sample_id=row['sample_id'],target_event=event,family_id=row['family'],theta=row['theta'],reference_label=row['events'][event],reference_state_sha256=row['state_sha256'],fixed_context_sha256=row['fixed_context_sha256'],
                source=str(source.resolve()),source_sha256=digest(source),original_search_intervals=intervals,
                normalization_basis=dict(domain=[min(family_values),max(family_values)],normalization_span=span,source='current published same-family same-context parameter range'),
                distances=[dict(bracket=x['bracket'],**distance(dict(theta=row['theta'],boundary=dict(status='verified',bracket=x['bracket'],normalization_span=span,source=str(source.resolve()))))) for x in intervals],
                formal_nearacc_eligible=False,status='original_search_physics_matched_local_intervals_repeat_and_rgb_pending',blocking_reasons=['boundary_repeatability_pending','reference_rgb_observability_pending'],note='multiple transition windows retained; no unique threshold claimed'))
    output=ROOT/'t13_original_search_bindings_20261019.json'
    output.write_text(json.dumps(registrations,indent=2),encoding='utf-8')
    summary=dict(matched_physical_context_groups=len(matched_groups),bound_sample_event_records=len(registrations),unique_samples=len({r['sample_id'] for r in registrations}),conflicts=conflicts,formal_new_near=0)
    (ROOT/'t13_original_search_binding_summary_20261019.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':main()
