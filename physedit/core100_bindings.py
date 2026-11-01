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
    if result.get('schema')!='core100-active-distance-bindings-v1':
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
        if row['status']=='distance_ready'and not row['boundary_records']and not row.get('original_calibration_reference'):
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
        for record in row['boundary_records']:
            if record['event']not in row['reference_events']:
                raise ValueError('core100_boundary_event_not_in_reference_truth')
            if record['endpoint_labels']not in([0,1],[1,0]):
                raise ValueError('core100_boundary_endpoints_do_not_flip')
            measured=interval_distance(row['theta'],record['bracket'],row['normalization_span'])
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


def lookup(clip_id, reference_video_sha256, horizon_s, *, registry=None):
    """Callers must supply reference identity and the actual event window."""
    data=registry or load()
    row=next(r for r in data['cases']if r['clip_id']==clip_id)
    if reference_video_sha256!=row['reference_video_sha256']:
        raise ValueError('core100_distance_lookup_reference_mismatch')
    if abs(horizon_s-row['horizon_s'])>1e-9:
        raise ValueError('core100_distance_lookup_window_mismatch')
    return row


def bind_answer(answer, *, reference_video_sha256, horizon_s, registry=None):
    """Attach distances to an existing answer key; never replace its labels.

    Reference admission, full event vector, temporal order, inversion eligibility
    and failure denominators remain the caller's existing registrations.
    """
    cid=answer.get('clip_id')or answer['point_id']
    row=lookup(cid,reference_video_sha256,horizon_s,registry=registry)
    result=copy.deepcopy(answer)
    if row['status']=='incomplete':
        raise ValueError('core100_reference_binding_incomplete:'+cid)
    target=result['target_event']
    if target not in row['reference_events']:
        raise ValueError('core100_target_event_not_bound:'+target)
    for event,label in row['reference_events'].items():
        if event in result['events']and result['events'][event]!=label:
            raise ValueError('core100_reference_event_labels_conflict:'+event)
    if 'theta'in result and abs(result['theta']-row['theta'])>1e-8:
        raise ValueError('core100_parameter_value_conflict')
    result['theta']=row['theta']
    source=str(REGISTRY)
    proof=hashlib.sha256(REGISTRY.read_bytes()).hexdigest()
    records=[b for b in row['boundary_records']if b['event']==target]
    if row.get('original_calibration_reference'):
        result['boundary']=dict(status='recorded_reference',source=source,source_sha256=proof,
            reference_value=row['original_calibration_reference']['value'],
            reason='Original calibration reference retained; not certified as an exact physical threshold.')
        result['recorded_reference_distance']=copy.deepcopy(row['original_calibration_reference'])
    elif not records:
        result['boundary']=dict(status='not_applicable',reason=row['reason'],source=source,source_sha256=proof)
    elif row['binding_kind']=='released_state_scan'or len(records)>1:
        result['boundary']=dict(status='observed',intervals=[dict(bracket=b['bracket'],labels=b['endpoint_labels'])for b in records],
            normalization_span=row['normalization_span'],source=source,source_sha256=proof,
            scope='Observed local transitions; no unique exact or nearest-global threshold asserted.')
    else:
        result['boundary']=dict(status='verified',bracket=records[0]['bracket'],
            normalization_span=row['normalization_span'],source=source,source_sha256=proof,
            verification_scope='Completed fixed-context conditional local interval; formal admission is unchanged.')
    result['active_distance_status']=row['status']
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
