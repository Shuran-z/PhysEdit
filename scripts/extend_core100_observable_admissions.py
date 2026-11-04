"""Admit original observable contact/passage references, preserving old cohorts."""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_reference_admission_continue_20261101'


def extend(registry):
    decisions_path=WORK/'OBSERVABILITY_DECISIONS.json'
    if not decisions_path.exists():return registry
    decisions=json.loads(decisions_path.read_text(encoding='utf8'))
    current=json.loads((ROOT/'annotation_site/resources/core100_distance_bindings.json').read_text(encoding='utf8'))
    by={r['clip_id']:r for r in current['cases']}
    truth={r['clip_id']:r for r in json.loads((ROOT/'annotation_site/resources/core100_contact_reference_truth_20261027.json').read_text(encoding='utf8'))['references']}
    identities={r['clip_id']:r for r in json.loads((WORK/'all100/RESULT.json').read_text(encoding='utf8'))}
    original_clocks={r['clip_id']:r for r in json.loads((WORK/'T13_ORIGINAL_WINDOW.json').read_text(encoding='utf8'))}
    result=copy.deepcopy(registry);extra=[]
    for decision in decisions:
        cid=decision['clip_id'];ref=by[cid];identity=identities[cid]
        assert decision['status']=='passed' and decision['video_sha256']==ref['reference_video_sha256']==identity['video_sha256']
        artifact=ROOT/decision['artifact'];assert hashlib.sha256(artifact.read_bytes()).hexdigest()==decision['artifact_sha256']
        event_by_scene={'T05':'gate_passage','T12':'stapler_contacts_tissue_box','T13':'falling_book_to_drink_contact','T14':'passed_channel','T16':'folder_downstream_contact'}
        event=event_by_scene[cid[:3]]
        boundary=next(b for b in ref['boundary_records']if b['event']==event)
        if cid in truth:
            assert truth[cid]['video_sha256']==ref['reference_video_sha256']
            assert truth[cid]['reference_state_sha256']==ref['source_state_sha256']
            assert truth[cid]['reference_label_events'][event]==ref['reference_events'][event]
        if cid.startswith('T13'):
            assert original_clocks[cid]['reference_state_sha256']==ref['source_state_sha256']
            assert ref['end_frame_index']==124 and identity['native_fps']=='24/1'
        if cid=='T16_C05':
            proof=json.loads((WORK/'T16_ORIGINAL_INTERVAL_READBACK.json').read_text(encoding='utf8'))
            assert proof['points'][1]['state_sha256']==ref['source_state_sha256']
            assert proof['points'][0]['fixed_context_sha256']==proof['points'][1]['fixed_context_sha256']==ref['fixed_context_sha256']
        if cid=='T16_C04':
            proof=json.loads((WORK/'T16_ACTIVE_CONTACT_READBACK.json').read_text(encoding='utf8'))
            assert proof['reference_state_sha256']==ref['source_state_sha256'] and proof['reference_events'][event]==ref['reference_events'][event]
        item=dict(clip_id=cid,cohort_id=cid.lower()+'-original-observable',sample_id=ref['sample_id'],
            reference_release_version=ref['reference_release_version'],reference_video_sha256=ref['reference_video_sha256'],
            reference_state_sha256=ref['source_state_sha256'],condition_frame_index=ref['condition_frame_index'],
            end_frame_index=ref['end_frame_index'],reference_fps=float(identity['native_fps'].split('/')[0])/float(identity['native_fps'].split('/')[1]),
            target_event=event,ever_event=decision.get('ever_event',True),reference_label=ref['reference_events'][event],horizon_s=ref['horizon_s'],
            theta=ref['theta'],family_id=ref['parameter'],normalization_domain=ref['normalization_domain'],
            normalization_span=ref['normalization_span'],boundary_interval=boundary['bracket'],
            normalized_distance_interval=boundary['distance']['normalized_absolute_interval'],
            bin=boundary['distance']['bin']if decision.get('distance_admitted',True)else None,
            distance_admitted=decision.get('distance_admitted',True),numerical_candidate_bin=boundary['distance']['bin'],
            fixed_context_sha256=ref.get('fixed_context_sha256'),
            reference_admission=dict(status='admitted',basis='SHA-bound original RGB and original registered event/window evidence',
                scope='fixed_simulator_target_event_only',independent_human_reference_review=False),
            visual_observability='passed_original_native_CPU_decode_reference_review',
            original_protocol_scope='author-approved contact targets 20261027'if cid in truth else'original registered target',
            source_boundary_evidence=ref['evidence'],observability_evidence=decision,
            score_scope='ordinary target accuracy; one-sided Near target accuracy retained, balanced NearAcc requires both classes')
        if cid=='T16_C05':item.update(boundary_scope='observed published local interval, fixed original simulator contract; no unique/robust physical threshold claim',original_physical_QA_diagnostics_unchanged=True)
        extra.append(dict(cohort_id=item['cohort_id'],scoring_adapter='frozen_existing_inputs',references=[item],pairs=[]))
    result['cohorts'].extend(extra)
    refs=[r for c in result['cohorts']for r in c['references']]
    result['summary'].update(formally_registered_reference_cases=len(refs),
        formally_registered_near_points=sum(r.get('bin','near')=='near'for r in refs),
        formally_registered_pairs=sum(len(c['pairs'])for c in result['cohorts']),
        newly_admitted_reference_cases=len(extra),new_scientific_admission_claims=len(extra))
    result['provenance']['observable_admission_decisions_sha256']=hashlib.sha256(decisions_path.read_bytes()).hexdigest()
    media_path=ROOT/'annotation_site/resources/core100_additional_media_verification.json'
    if media_path.exists():result['additional_media_registry_sha256']=hashlib.sha256(media_path.read_bytes()).hexdigest()
    progress_path=ROOT/'annotation_site/resources/core100_reference_observability_progress.json'
    if progress_path.exists():result['reference_progress_registry_sha256']=hashlib.sha256(progress_path.read_bytes()).hexdigest()
    result['note']+=' Additional original observable target-event references are admitted with explicit scope. One-sided cases do not create balanced NearAcc or synthetic pairs.'
    from scripts.admit_remaining74_original_references import extend_remaining
    return extend_remaining(result)


if __name__=='__main__':
    from scripts.build_formal_core100_admission import build
    result=extend(build());p=ROOT/'annotation_site/resources/core100_formal_cohorts.json'
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result['summary']))
