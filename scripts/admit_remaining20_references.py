"""Append original-target admissions backed by complete native-frame review."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_remaining20_20261101'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def extend_remaining20(registry):
    decision_path=WORK/'FULL_FRAME_DECISIONS.json'
    if not decision_path.exists():return registry
    extraction=WORK/'FULL_FRAME_EXTRACTION.json'
    proofs={x['clip_id']:x for x in read(extraction)}
    decisions=read(decision_path)
    numeric={x['clip_id']:x for x in read(ROOT/'annotation_site/resources/core100_distance_bindings.json')['cases']}
    sourcepath=ROOT/'review/core100_remaining74_admission_20261101/native_readback/READBACK.json'
    sealed=WORK/'sealed_readbacks'/(sha(sourcepath)+'.json');sealed.parent.mkdir(exist_ok=True)
    if not sealed.exists():sealed.write_bytes(sourcepath.read_bytes())
    sources={x['clip_id']:x for x in read(sealed)}
    existing={x['clip_id']for c in registry['cohorts']for x in c['references']}
    for d in decisions:
        cid=d['clip_id']
        if d['status']!='passed' or cid in existing:continue
        assert cid=='T15_C04','No additional source extractor authorized by this module'
        proof=proofs[cid];r=numeric[cid];source=sources[cid]['points'][0]
        assert proof['video_sha256']==r['reference_video_sha256']
        assert proof['native_frames']==210 and proof['all_frames_decoded']and not proof['temporal_subsampling']
        coverage=[]
        for sheet in proof['sheets']:
            file=WORK/'full_frame_review'/cid/Path(sheet['file']).name
            assert sha(file)==sheet['sha256']
            coverage.extend(range(sheet['first_frame'],sheet['last_frame']+1))
        assert coverage==list(range(210))
        assert r['source_state_sha256']==source['state_sha256']
        assert source['original_metric_events']['labels']['laptop_contacts_phone']==r['reference_events']['laptop_contacts_phone']==d['reference_label']==0
        assert source['original_metric_events']['first_contact'] is None
        assert 'all solver steps sampled'in source['original_metric_events']['original_contact_recording_contract']['contact_aggregation']
        template=next(x for c in registry['cohorts']for x in c['references']if x['clip_id']=='T15_C05')
        item=copy.deepcopy(template)
        for key in ('clip_id','sample_id','reference_release_version','reference_video_sha256','condition_frame_index','end_frame_index','horizon_s','theta','normalization_domain','normalization_span'):
            item[key]=r[key]
        item.update(cohort_id=cid.lower()+'-original-observable',reference_state_sha256=r['source_state_sha256'],
            numerical_source_state_sha256=r['source_state_sha256'],target_event='laptop_contacts_phone',reference_label=0,
            family_id=r['parameter'],distance_admitted=False,bin=None,boundary_interval=None,normalized_distance_interval=None,
            fixed_context_sha256=source.get('fixed_context_sha256'),source_boundary_evidence=r['evidence'],
            reference_admission=dict(status='admitted',basis='all210 original native frames reviewed plus same-source all-substep contact record',
                scope='original contact target over original five-second window only; no boundary admission',independent_human_reference_review=False),
            visual_observability='passed_all210_native_frames_original_contact_negative_review',
            observability_evidence=d,original_state_readback_evidence=dict(file=sealed.relative_to(ROOT).as_posix(),sha256=sha(sealed)),
            full_frame_review_evidence=dict(file=extraction.relative_to(ROOT).as_posix(),sha256=sha(extraction)),
            score_scope='original laptop-phone contact target only; distance, NearAcc and PairAcc pending')
        registry['cohorts'].append(dict(cohort_id=item['cohort_id'],scoring_adapter='frozen_existing_inputs',references=[item],pairs=[]))
    refs=[x for c in registry['cohorts']for x in c['references']]
    registry['summary'].update(formally_registered_reference_cases=len(refs),newly_admitted_reference_cases=len(refs)-7,new_scientific_admission_claims=len(refs)-7)
    registry['provenance']['remaining20_full_frame_decisions_sha256']=sha(decision_path)
    return registry
