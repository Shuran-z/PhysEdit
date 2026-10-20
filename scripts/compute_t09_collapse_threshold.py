"""Compute a geometry-derived T09 support-layer drop predicate and scan intervals.

The extracted book is 27mm thick in this release. Crossing half its support
height (13.5mm) separates original-level retention from one-layer settling.
This newly specified operational predicate is not a recovered historic numeric
threshold, and does not alone classify global overturning/disintegration.
"""
import collections
import csv
import json

from scripts.export_original_boundary_distances import ROOT, distances
from scripts.supplement_t09_published_support_boundaries import context


def measure(config,metrics,fraction=.5):
    if not 0<fraction<1:raise ValueError('support-height fraction must be between zero and one')
    e=config['experiment'];name=e['extracted_book_name'];obj=next(o for o in config['dynamic_objects'] if o['name']==name)
    thickness=obj.get('collision_proxy_size',obj['size'])[2]
    if thickness<=0:raise ValueError('positive extracted support thickness required')
    drops={name:metrics[name]['initial_position'][2]-metrics[name]['final_position'][2] for name in e['supported_book_names']}
    threshold=thickness*fraction
    return dict(extracted_support_thickness_m=thickness,drop_threshold_m=threshold,upper_book_final_drops_m=drops,
        max_upper_book_final_drop_m=max(drops.values()),reference_label=int(max(drops.values())>=threshold),
        affected_upper_books=[name for name,value in drops.items() if value>=threshold])


def main():
    published=[r for p in ROOT.glob('published_batch_*.json') for r in json.loads(p.read_text(encoding='utf-8')) if r['scene_id']=='T09']
    from pathlib import Path
    manifest_path=Path('../_audit_t01_t20_20261018/metadata/phy2__data__T09__genesis_44_480p_20260927__TRANSFER_MANIFEST.json')
    transfer={r['destination']:r for r in json.loads(manifest_path.read_text(encoding='utf-8'))['files']}
    states={r['sample_id']:r for r in json.loads((ROOT/'t06_t09_surviving_original_state_evidence.json').read_text(encoding='utf-8')) if r['scene_id']=='T09' and r['status']=='original_annotation_recovered'}
    groups=collections.defaultdict(list);events=[];rows=[]
    for r in published:
        c=r['config'];e=c['experiment'];param=e['parameter'];axis=param['parameter_name'];state=states.get(r['sample_id'])
        if state and (state['published_config_sha256']!=r['sha256'] or state['dynamic_spec_mismatches'] or not state['runtime_force_core_matches'] or not state['scene_consumed_physics_matches']):
            raise ValueError('original state/config physical correspondence mismatch')
        measurement=measure(c,state['metrics']) if state else dict(reference_label=None)
        release=r['sidecar'].split('/configs/')[0]
        videos={cam:dict(path=release+'/videos/'+r['sample_id']+'__'+cam+'.mp4',sha256=transfer[release+'/videos/'+r['sample_id']+'__'+cam+'.mp4']['sha256']) for cam in ['cam01','cam02','cam03']}
        row=dict(scene_id='T09',engine='genesis',sample_id=r['sample_id'],family_id=axis,theta=param['parameter_value'],parameter_unit='N' if axis=='pull_force' else 'dimensionless',
            repo_id=r['repo_id'],release=release,published_config_path=r['sidecar'],videos=videos,
            current_transfer_config_matches=transfer[r['sidecar']]['sha256']==r['sha256'],publication_transfer_manifest=str(manifest_path.resolve()),
            revision=r['revision'],source_config_sha256=r['sha256'],reference_state_sha256=state['source_sha256'] if state else None,
            original_state_path=state['source_path'] if state else None,simulation_seed=c.get('seed'),**measurement,
            target_event='upper_stack_support_layer_drop',target_definition='At least one book above the extraction layer ends at least half an extracted-book thickness below its initial settled height.',
            global_collapse_label=None,global_collapse_note='Support-layer descent alone does not classify global overturning.',
            fixed_context_sha256=context(c,axis),extra_validation_separate=True)
        groups[(axis,row['fixed_context_sha256'])].append(row);rows.append(row)
        if state:events.append(row)
    windows=[];bindings=[]
    for (axis,key),items in groups.items():
        known=sorted((r for r in items if r['reference_label'] is not None),key=lambda r:r['theta'])
        domain=[min(r['theta'] for r in items),max(r['theta'] for r in items)];span=domain[1]-domain[0]
        for a,b in zip(known,known[1:]):
            if a['theta']==b['theta'] or a['reference_label']==b['reference_label']:continue
            window=dict(family_id=axis,fixed_context_sha256=key,bracket=[a['theta'],b['theta']],endpoint_labels=[a['reference_label'],b['reference_label']],
                endpoint_sample_ids=[a['sample_id'],b['sample_id']],endpoint_state_sha256=[a['reference_state_sha256'],b['reference_state_sha256']],endpoint_simulation_seeds=[a['simulation_seed'],b['simulation_seed']])
            windows.append(window)
            for row in items:
                d=distances(row['theta'],bracket=window['bracket'])
                bindings.append({**row,**window,'original_boundary_interval':window['bracket'],**d,'normalization_domain':domain,'normalization_span':span,
                    'normalized_distance_lower':d['distance_lower']/span,'normalized_distance_upper':d['distance_upper']/span,
                    'original_reference_kind':'supplemental_interval_from_geometry_labeled_original_seed_varied_scan',
                    'predicate_origin':'new geometry-derived operational definition, not recovered historic threshold',
                    'seed_scope':'Original released seed-varied scan; observed transition interval, not an exact same-seed threshold.'})
    out=ROOT/'original_value_distance_ledger'
    (ROOT/'t09_geometry_drop_events.json').write_text(json.dumps(events),encoding='utf-8')
    (ROOT/'t09_geometry_drop_parameters.json').write_text(json.dumps(rows),encoding='utf-8')
    (ROOT/'t09_geometry_drop_windows.json').write_text(json.dumps(windows,indent=2),encoding='utf-8')
    (out/'t09_geometry_drop_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bindings),encoding='utf-8')
    with (out/'t09_geometry_drop_sample_distances.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['sample_id','family_id','theta','parameter_unit','original_boundary_interval','distance_lower','distance_upper','reference_label','drop_threshold_m','max_upper_book_final_drop_m']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(bindings)
    negative=[r['max_upper_book_final_drop_m'] for r in events if not r['reference_label']];positive=[r['max_upper_book_final_drop_m'] for r in events if r['reference_label']]
    summary=dict(predicate_origin='new geometry-derived operational definition',target_event='upper_stack_support_layer_drop',
        extracted_support_thicknesses_m=sorted({r['extracted_support_thickness_m'] for r in events}),drop_thresholds_m=sorted({r['drop_threshold_m'] for r in events}),
        measured_original_states=len(events),published_parameters=len(rows),current_transfer_config_matches=sum(r['current_transfer_config_matches'] for r in rows),positive=sum(r['reference_label'] for r in events),negative=len(negative),
        largest_negative_final_drop_m=max(negative) if negative else None,smallest_positive_final_drop_m=min(positive) if positive else None,
        sensitivity_label_counts={str(fraction):sum(r['max_upper_book_final_drop_m']>=fraction*r['extracted_support_thickness_m'] for r in events) for fraction in [.25,.5,.75]},
        local_intervals=len(windows),sample_interval_records=len(bindings),unique_published_samples_with_distance=len({r['sample_id'] for r in bindings}),
        interval_counts_by_axis=dict(collections.Counter(w['family_id'] for w in windows)),all_T09_completed=False,global_collapse_definition_completed=False)
    (out/'t09_geometry_drop_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':main()
