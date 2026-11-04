"""Merge independently verified axes without replacing concurrent original-axis work."""
import copy,hashlib
from physedit.core100_bindings import interval_distance

def apply_axis_patches(cases,supplement,root,evidence):
    for name,digest in supplement['evidence_sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('conditional_axis_evidence_changed:'+name)
        evidence[name]=digest
    for patch in supplement['patches']:
        row=cases[patch['clip_id']]
        was_ready=row['status']=='distance_ready'
        for key in ['source_state_sha256','reference_video_sha256','sample_id','horizon_s','reference_events']:
            if row[key]!=patch[key]:raise ValueError('conditional_axis_context_mismatch:'+key)
        domain=patch['normalization_domain'];span=domain[1]-domain[0]
        records=copy.deepcopy(patch['records'])
        for record in records:record['distance']=interval_distance(patch['theta'],record['bracket'],span)
        row.setdefault('legacy_primary_axis', {k:copy.deepcopy(row[k])for k in ['status','reason','parameter','theta','normalization_domain','normalization_span','boundary_records']})
        row.setdefault('source_point_axes',{})[row['parameter']]=row['theta']
        row['source_point_axes'][patch['axis']]=patch['theta']
        row.setdefault('conditional_axes',{})[patch['axis']]=dict(parameter=patch['axis'],unit=patch['unit'],theta=patch['theta'],normalization_domain=domain,normalization_span=span,reference_events=copy.deepcopy(row['reference_events']),boundary_records=records,binding_kind='verified_supplemental_conditional_local_search',solver=patch['solver'],source_repeat_max_position_error_m=0.,formal_admission=False,proof=patch['proof'])
        row.update(status='distance_ready',axis_selection_required=True)
        if not was_ready:
            row['reason']='Verified supplemental motion-axis intervals are available with explicit axis selection. Original primary-axis values and evidence are retained separately; repaired numerical evidence does not grant media-quality admission.'
        row.setdefault('notes',[])
        note='Supplemental motion axis is independently verified under an explicit repaired solver. Original primary-axis records remain intact. Axis must be selected explicitly; this is not a global-nearest-boundary or media-quality approval.'
        if note not in row['notes']:row['notes'].append(note)
