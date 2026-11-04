"""Active Core100 distance registry, separate from generated-video judgments.

python -m physedit.core100_bindings status [--verify-evidence]
python -m physedit.core100_bindings export --out NEW.jsonl
"""
import argparse
import collections
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'annotation_site/resources/core100_distance_bindings.json'
STATES=('distance_ready','not_applicable_in_registered_scan','incomplete')


def original_family_reference_ready(row):
    """Supplemental directions do not complete a missing original family."""
    if row['status'] != 'distance_ready':
        return False
    if row.get('boundary_records') or row.get('original_calibration_reference'):
        return True
    if row.get('parameter') == 'joint_global_configuration':
        # A conditional A-D probe through a G source is useful, but it does
        # not complete that source's original joint G family.
        axis = row.get('conditional_axes', {}).get('original_G_global_path', {})
        return bool(axis.get('boundary_records') and
                    axis.get('original_registered_family') == 'joint_global_configuration')
    return any(axis.get('boundary_records') and
               axis.get('binding_kind') != 'verified_supplemental_conditional_local_search'
               for axis in row.get('conditional_axes', {}).values())


def interval_distance(theta, bracket, span):
    a,b=bracket
    if not all(type(x)in(int,float)and math.isfinite(x)for x in [theta,a,b,span])or a>=b or span<=0:
        raise ValueError('invalid_core100_boundary_interval_or_scale')
    low=max(a-theta,theta-b,0)/span
    high=max(abs(theta-a),abs(theta-b))/span
    bucket='near'if high<=.05 else'mid'if low>.05 and high<=.15 else'far'if low>.15 else None
    return dict(normalized_absolute_interval=[low,high],bin=bucket)


def load(path=None, *, verify_evidence=False, conditions=None, version=None):
    path=Path(path or REGISTRY)
    result=json.loads(path.read_text(encoding='utf8'))
    if result.get('schema')not in('core100-active-distance-bindings-v1','core100-active-distance-bindings-v2'):
        raise ValueError('unknown_core100_distance_registry')
    if conditions is None:
        from .core100_release import load as load_release
        _,manifest,current,_=load_release()
        conditions=current['tasks'];version=manifest['version']
    if version!=result['reference_release_version']:
        raise ValueError('core100_distance_reference_release_changed')
    references={r['clip_id']:(r.get('reference',{}).get('sha256')or r['source_video_sha256'])for r in conditions}
    rows=result['cases'];ids=[r['clip_id']for r in rows]
    if len(ids)!=100 or len(set(ids))!=100 or set(ids)!=set(references):
        raise ValueError('core100_distance_roster_changed')
    for row in rows:
        if row['reference_video_sha256']!=references[row['clip_id']]:
            raise ValueError('core100_distance_reference_hash_mismatch:'+row['clip_id'])
        if row['status']not in STATES or not row['reason']:
            raise ValueError('core100_distance_status_invalid')
        axes=row.get('conditional_axes',{})
        if axes and result['schema']!='core100-active-distance-bindings-v2':
            raise ValueError('conditional_axes_require_v2_registry')
        if row['status']=='distance_ready'and not row['boundary_records']and not row.get('original_calibration_reference')and not axes:
            raise ValueError('core100_ready_case_missing_boundary')
        calibration=row.get('original_calibration_reference')
        if calibration:
            expected=abs(row['theta']-calibration['value'])
            if calibration['exact_physical_threshold_certified']or calibration['raw_absolute_distance']!=expected:
                raise ValueError('original_calibration_value_was_misrepresented')
            if calibration['normalized_absolute_distance']!=expected/calibration['normalization_span']:
                raise ValueError('original_calibration_distance_changed')
        if row['status']=='not_applicable_in_registered_scan'and row['boundary_records']:
            raise ValueError('core100_no_flip_case_has_boundary')
        if any(type(v)is not int or v not in(0,1)for v in row['reference_events'].values()):
            raise ValueError('core100_reference_events_not_binary')
        contexts=[row]
        for name,axis in axes.items():
            if name!=axis['parameter']or not axis['boundary_records']:
                raise ValueError('core100_conditional_axis_invalid')
            if axis['reference_events']!=row['reference_events']:
                raise ValueError('core100_conditional_axis_truth_changed')
            if axis['theta']!=row['source_point_axes'][name]:
                raise ValueError('core100_conditional_axis_source_value_changed')
            if abs(axis['normalization_span']-(axis['normalization_domain'][1]-axis['normalization_domain'][0]))>1e-12:
                raise ValueError('core100_conditional_axis_scale_changed')
            contexts.append(axis)
        for context,record in [(context,record)for context in contexts for record in context['boundary_records']]:
            if record['event']not in row['reference_events']:
                raise ValueError('core100_boundary_event_not_in_reference_truth')
            if record['endpoint_labels']not in([0,1],[1,0]):
                raise ValueError('core100_boundary_endpoints_do_not_flip')
            measured=interval_distance(context['theta'],record['bracket'],context['normalization_span'])
            if record['distance']!=measured:
                raise ValueError('core100_distance_value_changed')
            if record['exact_theta_star']is not None:
                raise ValueError('interval_was_replaced_with_an_exact_threshold')
    counts=collections.Counter(r['status']for r in rows)
    if result['summary']['total']!=100 or any(result['summary'][s]!=counts[s]for s in STATES):
        raise ValueError('core100_distance_counts_disagree')
    if verify_evidence:
        for name,expected in result['evidence_sha256'].items():
            source=(ROOT/name).resolve()
            if not source.is_relative_to(ROOT)or hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
                raise ValueError('core100_distance_evidence_changed:'+name)
    return result


def lookup(clip_id, reference_video_sha256, horizon_s, *, registry=None, axis=None):
    """Callers must supply reference identity and the actual event window."""
    data=registry or load()
    row=next(r for r in data['cases']if r['clip_id']==clip_id)
    if reference_video_sha256!=row['reference_video_sha256']:
        raise ValueError('core100_distance_lookup_reference_mismatch')
    if abs(horizon_s-row['horizon_s'])>1e-9:
        raise ValueError('core100_distance_lookup_window_mismatch')
    if axis is None:return row
    if row.get('conditional_axes'):
        primary=(axis==row['parameter'] and bool(row['boundary_records']))
        if axis not in row['conditional_axes'] and not primary:
            raise ValueError('core100_distance_unknown_or_incomplete_axis:'+axis)
        selected=copy.deepcopy(row)
        if axis in row['conditional_axes']:
            selected.update(copy.deepcopy(row['conditional_axes'][axis]))
        if isinstance(row.get('theta'),dict):
            if selected.get('joint_source_vector',row['theta'])!=row['theta']:
                raise ValueError('core100_joint_axis_source_vector_changed')
            selected['joint_source_vector']=copy.deepcopy(row['theta'])
        selected.pop('conditional_axes',None)
        selected['selected_conditional_axis']=axis
        return selected
    if axis!=row['parameter']:
        raise ValueError('core100_distance_unknown_or_incomplete_axis:'+axis)
    return row


def bind_answer(answer, *, reference_video_sha256, horizon_s, registry=None, axis=None):
    """Attach distances to an existing answer key; never replace its labels.

    Reference admission, full event vector, temporal order, inversion eligibility
    and failure denominators remain the caller's existing registrations.
    """
    cid=answer.get('clip_id')or answer['point_id']
    row=lookup(cid,reference_video_sha256,horizon_s,registry=registry,axis=axis or answer.get('boundary_axis'))
    if row.get('conditional_axes'):
        raise ValueError('core100_distance_axis_required:'+cid)
    result=copy.deepcopy(answer)
    if row['status']=='incomplete':
        raise ValueError('core100_reference_binding_incomplete:'+cid)
    target=result['target_event']
    if target not in row['reference_events']:
        raise ValueError('core100_target_event_not_bound:'+target)
    for event,label in row['reference_events'].items():
        if event in result['events']and result['events'][event]!=label:
            raise ValueError('core100_reference_event_labels_conflict:'+event)
    if isinstance(result.get('theta'),dict):
        if result['theta']!=row.get('joint_source_vector'):
            raise ValueError('core100_joint_parameter_vector_conflict')
    elif 'theta'in result and abs(result['theta']-row['theta'])>1e-8:
        raise ValueError('core100_parameter_value_conflict')
    if row.get('joint_source_vector'):
        if result.get('joint_source_vector',row['joint_source_vector'])!=row['joint_source_vector']:
            raise ValueError('core100_joint_parameter_vector_conflict')
        result['joint_source_vector']=copy.deepcopy(row['joint_source_vector'])
    result['theta']=row['theta']
    source=str(REGISTRY)
    proof=hashlib.sha256(REGISTRY.read_bytes()).hexdigest()
    all_records=[b for b in row['boundary_records']if b['event']==target]
    # Retain every original interval and its distances as evidence. Known
    # discordance (or an explicitly pending repeat check) cannot be promoted
    # into a usable scoring boundary merely because the original run flipped.
    records=[b for b in all_records if b.get('endpoint_repeatability',{}).get('status','reproduced')=='reproduced']
    if row.get('original_calibration_reference'):
        result['boundary']=dict(status='recorded_reference',source=source,source_sha256=proof,
            reference_value=row['original_calibration_reference']['value'],
            reason='Original calibration reference retained; not certified as an exact physical threshold.')
        result['recorded_reference_distance']=copy.deepcopy(row['original_calibration_reference'])
    elif not records:
        status='not_applicable'if row['status']=='not_applicable_in_registered_scan'else'unavailable'
        result['boundary']=dict(status=status,
            reason=('Endpoint repeatability is discordant or pending; original intervals remain in the evidence registry.'if all_records else
                    row['reason']if status=='not_applicable'else'No boundary is bound for the requested event; another event having an interval does not exclude this event.'),
            source=source,source_sha256=proof)
        if all_records:result['boundary']['endpoint_repeatability']=[copy.deepcopy(b['endpoint_repeatability'])for b in all_records]
    elif row['binding_kind']=='released_state_scan'or len(records)>1:
        result['boundary']=dict(status='observed',intervals=[dict(bracket=b['bracket'],labels=b['endpoint_labels'])for b in records],
            normalization_span=row['normalization_span'],source=source,source_sha256=proof,
            scope='Observed local transitions; no unique exact or nearest-global threshold asserted.')
    else:
        result['boundary']=dict(status='verified',bracket=records[0]['bracket'],
            normalization_span=row['normalization_span'],source=source,source_sha256=proof,
            verification_scope='Completed fixed-context conditional local interval; formal admission is unchanged.')
    result['active_distance_status']=row['status']
    if row.get('selected_conditional_axis'):
        result['boundary_axis']=row['selected_conditional_axis']
    return result


def export_rows(registry):
    """Keep all100 rows. Missing/not-applicable boundaries never become zeros.

    Observed intervals remain observed. This export supplies reference metadata;
    it does not convert reference labels to generated-video annotations or grant
    an unreviewed reference automatic formal scoring admission.
    """
    for row in registry['cases']:
        yield dict(clip_id=row['clip_id'],reference_video_sha256=row['reference_video_sha256'],
            reference_release_version=row['reference_release_version'],horizon_s=row['horizon_s'],
            condition_frame_index=row['condition_frame_index'],end_frame_index=row['end_frame_index'],
            theta=row['theta'],parameter=row['parameter'],normalization_domain=row['normalization_domain'],
            reference_events=row['reference_events'],distance_status=row['status'],reason=row['reason'],
            boundary_records=row['boundary_records'],ordinary_event_denominator_retained=True,
            original_calibration_reference=row.get('original_calibration_reference'),
            conditional_axes=copy.deepcopy(row.get('conditional_axes',{})),
            axis_selection_required=bool(row.get('conditional_axes')),
            numerical_binding_only=True,not_a_complete_event_exact_answer_key=True,
            generated_event_labels=None)


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('status');p.add_argument('--verify-evidence',action='store_true')
    p=sub.add_parser('export');p.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();data=load(verify_evidence=getattr(args,'verify_evidence',False))
    if args.command=='status':
        print(json.dumps(dict(summary=data['summary'],scenes=data['scenes'],
            pending=[dict(clip_id=r['clip_id'],reason=r['reason'])for r in data['cases']if r['status']=='incomplete']),ensure_ascii=False,indent=2))
    else:
        with args.out.open('x',encoding='utf8')as f:
            for row in export_rows(data):f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps(dict(exported=100,out=str(args.out))))


if __name__=='__main__':main()
