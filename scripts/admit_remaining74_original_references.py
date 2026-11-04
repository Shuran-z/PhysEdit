"""Add individually reviewed original references, never rewriting prior cohorts."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_remaining74_admission_20261101'
read=lambda p:json.loads(p.read_text(encoding='utf8'))


def extend_remaining(registry):
    path=WORK/'ADMISSION_DECISIONS.json'
    if not path.exists():return registry
    decisions=read(path);live_proof_path=WORK/'native_readback/READBACK.json'
    digest=hashlib.sha256(live_proof_path.read_bytes()).hexdigest()
    proof_path=WORK/'sealed_readbacks'/(digest+'.json');proof_path.parent.mkdir(exist_ok=True)
    if not proof_path.exists():proof_path.write_bytes(live_proof_path.read_bytes())
    assert hashlib.sha256(proof_path.read_bytes()).hexdigest()==digest
    proof={r['clip_id']:r for r in read(proof_path)}
    numeric={r['clip_id']:r for r in read(ROOT/'annotation_site/resources/core100_distance_bindings.json')['cases']}
    identities={r['clip_id']:r for r in read(WORK/'reference_review/RESULT.json')}
    from physedit.core100_release import load
    active={r['clip_id']:r['reference']for r in load()[2]['tasks']}
    existing={r['clip_id']for c in registry['cohorts']for r in c['references']}
    for d in decisions:
        cid=d['clip_id']
        if cid in existing:continue
        p=proof[cid];r=numeric[cid];identity=identities[cid];source=p['points'][0];event=d['target_event']
        assert p['status']=='source_hash_clock_readback_verified'
        assert p['video_sha256']==r['reference_video_sha256']==identity['video_sha256']
        assert source['condition_frame_index']==r['condition_frame_index'] and source['end_frame_index']==r['end_frame_index']
        assert r['horizon_s']==(source['end_frame_index']-source['condition_frame_index'])*source['physical_frame_period_s']
        source_digests=(source['state_sha256'],source['stored_state_sha256'],source['decoded_state_sha256'])
        source_hash=r['source_state_sha256']or source['state_sha256']
        if source_hash not in source_digests:
            assert not d['distance_admitted'], cid+' numerical source differs'
            source_hash=active[cid].get('state_sha256')
            assert source_hash in source_digests and active[cid]['sha256']==p['video_sha256'], cid+' active source differs'
        if cid.startswith(('T16','T17')):
            label=source['labels'][event]
            assert all(x['fixed_context_sha256']==source['fixed_context_sha256']for x in p['points'])
        elif cid.startswith('T18'):label=source['original_terminal_event']['label']
        elif cid.startswith('T14'):label=source['original_gate_event']['label']
        elif cid.startswith(('T01','T02','T03','T04','T05','T06','T07','T08','T15','T20')):label=source['original_metric_events']['labels'][event]
        else:raise ValueError('No original target extractor registered: '+cid)
        assert label==r['reference_events'][event]==d['reference_label']
        for field in ('artifact','sequence_artifact'):
            artifact=ROOT/d[field];assert hashlib.sha256(artifact.read_bytes()).hexdigest()==d[field+'_sha256']
        boundary=next((b for b in r['boundary_records']if b['event']==event),None)
        verified_boundaries=[]
        if d['distance_admitted']:
            assert boundary
            if cid.startswith(('T16','T17')):
                verified_boundaries=[b for b in r['boundary_records']if b['event']==event]
                for candidate in verified_boundaries:
                    for endpoint in candidate['endpoints']:
                        assert endpoint
                        for x in endpoint:
                            assert any(v['state_sha256']==x['state_sha256']for v in p['points'])
            else:
                pointer=d['distance_evidence'];file=ROOT/pointer['file']
                assert hashlib.sha256(file.read_bytes()).hexdigest()==pointer['sha256']
                interval=next(x for x in read(file)if x['clip_id']==cid)
                assert interval['status']=='verified_original_published_interval'
                assert interval['source']['state_sha256']==source['decoded_state_sha256']
                assert interval['original_boundary_interval']==boundary['bracket']
                assert interval['original_labels']==boundary['endpoint_labels']
                verified_boundaries=[b for b in r['boundary_records']if b['event']==event]
                assert all(any(v['bracket']==b['bracket']and v['labels']==b['endpoint_labels']for v in interval['verified_intervals'])for b in verified_boundaries)
        distance=boundary['distance']if boundary else None
        if verified_boundaries:
            boundary=min(verified_boundaries,key=lambda b:b['distance']['normalized_absolute_interval'][1])
            low=min(b['distance']['normalized_absolute_interval'][0]for b in verified_boundaries)
            high=min(b['distance']['normalized_absolute_interval'][1]for b in verified_boundaries)
            policy=read(ROOT/'annotation_site/resources/core100_admission.json')['frozen_policy']
            bucket='near'if high<=policy['near_upper']else'mid'if low>policy['near_upper']and high<=policy['mid_upper']else'far'if low>policy['mid_upper']else None
            distance=dict(normalized_absolute_interval=[low,high],bin=bucket)
        item=dict(clip_id=cid,cohort_id=cid.lower()+'-original-observable',sample_id=r['sample_id'],
            reference_release_version=r['reference_release_version'],reference_video_sha256=r['reference_video_sha256'],
            reference_state_sha256=source_hash,numerical_source_state_sha256=r['source_state_sha256'],
            condition_frame_index=r['condition_frame_index'],end_frame_index=r['end_frame_index'],
            reference_fps=float(Fraction(identity['native_fps'])),source_encoded_media_fps=source['native_fps'],target_event=event,ever_event=d['ever_event'],reference_label=label,
            horizon_s=r['horizon_s'],theta=r['theta'],family_id=r['parameter'],normalization_domain=r['normalization_domain'],
            normalization_span=r['normalization_span'],boundary_interval=boundary['bracket']if boundary else None,
            normalized_distance_interval=distance['normalized_absolute_interval']if distance else None,
            bin=distance['bin']if distance and d['distance_admitted']else None,
            distance_admitted=d['distance_admitted'],fixed_context_sha256=source.get('fixed_context_sha256'),
            reference_admission=dict(status='admitted',basis='exact original sidecar, registered native clock, native RGB and event-specific sequence reviewed',scope='original_target_event; original observed local interval only when explicitly admitted',independent_human_reference_review=False),
            visual_observability='passed_original_native_CPU_decode_reference_review',
            original_protocol_scope='original registered target; no thresholds added',
            source_boundary_evidence=r['evidence'],observability_evidence=d,
            original_state_readback_evidence=dict(file=proof_path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(proof_path.read_bytes()).hexdigest()),
            score_scope='single original target; no full EventExact, balanced NearAcc or synthetic pair claim')
        if verified_boundaries:
            item['verified_original_boundary_intervals']=[b['bracket']for b in verified_boundaries]
            item['distance_scope']='nearest among the verified published original local intervals only; no global uniqueness claim'
        registry['cohorts'].append(dict(cohort_id=item['cohort_id'],scoring_adapter='frozen_existing_inputs',references=[item],pairs=[]))
    refs=[r for c in registry['cohorts']for r in c['references']]
    registry['summary'].update(formally_registered_reference_cases=len(refs),formally_registered_near_points=sum(r.get('bin','near')=='near'for r in refs),formally_registered_pairs=sum(len(c['pairs'])for c in registry['cohorts']),newly_admitted_reference_cases=len(refs)-7,new_scientific_admission_claims=len(refs)-7)
    registry['summary']['formally_registered_interval_reference_cases']=sum(r.get('distance_admitted',True)for r in refs)
    registry['provenance']['remaining74_admission_decisions_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    from scripts.admit_remaining20_references import extend_remaining20
    return extend_remaining20(registry)


if __name__=='__main__':
    path=ROOT/'annotation_site/resources/core100_formal_cohorts.json'
    r=extend_remaining(read(path));path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(r['summary']))
