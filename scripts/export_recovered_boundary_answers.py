"""Export provenance-bound candidate answers; only admitted references get scoring bindings.

Reference admission happens before generation, never in response to a bad output.
Pending candidates are retained for review; no generated failure is filtered here.
"""
import collections
import json
from pathlib import Path
from physedit.boundary import digest, distance
from scripts.audit_nearacc_readiness import readiness
from scripts.reference_visual_admission import apply_review, load_reviews

OUT = Path('review/scene_family_completion_20261018')

def answer(r):
    if not r.get('numerical_reference_verified'):
        raise ValueError('numerical truth is not verified')
    if r.get('mapping_status') != 'matched' or not r.get('mapping_evidence'):
        raise ValueError('missing version mapping')
    source = Path(r['boundary']['source'])
    if digest(source) != r['boundary']['source_sha256']:
        raise ValueError('changed boundary evidence')
    norm = r['normalization_basis']
    if not norm or not r.get('parameter_unit'):
        raise ValueError('missing normalization/units')
    group = r.get('cell')
    if not group:
        # Rendering context remains separate even when physics was checked identical.
        parts = r['sample_id'].split('__')
        group = '__'.join(parts[:3])
    state = r.get('reference_state_sha256')
    if not state or len(state) != 64:
        raise ValueError('missing state identity')
    events = {r['target_event']: r['reference_label']}
    eligible, reasons, d = readiness(r)
    return dict(sample_id=r['engine']+'__'+r['sample_id'], reference_sample_id=r['sample_id'],
        engine=r['engine'], scene_id=r['scene_id'], family_id=r['family_id'],
        source_group_id=r['engine']+'__'+group, point_id=r['sample_id'],
        theta=r['theta'], parameter_name=r['parameter_name'],parameter_unit=r['parameter_unit'],
        target_event=r['target_event'], events=events, reference_state_sha256=state,
        boundary=r['boundary'], normalization_basis=norm, distance=d,
        mapping_status=r['mapping_status'],mapping_evidence=r['mapping_evidence'],
        reference_admission=dict(status='admitted' if eligible else 'pending',reasons=reasons),
        visual_review=r.get('visual_review'),
        inversion=dict(status='pending_reference_validation',reason='inversion eligibility is independent of event/near eligibility'),
        event_scope='target event only; full EventExact chain still requires a registered chain contract')

def main():
    candidates=[]
    reviews=load_reviews()
    for name in ['isaac_verified_numerical_registry.json','t02_published_scoring_registry.json']:
        for r in json.loads((OUT/name).read_text(encoding='utf-8')):
            if r.get('numerical_reference_verified'):
                r=apply_review(r,reviews.get((r['engine'],r['sample_id'])))
                candidates.append(answer(r))
    def write(name,rows):
        (OUT/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    write('candidate_reference_answers.jsonl',candidates)
    admitted=[r for r in candidates if r['reference_admission']['status']=='admitted']
    write('admitted_near_reference_answers.jsonl',admitted)
    groups=collections.defaultdict(list)
    for r in candidates:
        groups[(r['source_group_id'],r['family_id'])].append(r)
    coverage=[]
    for (group,family),items in sorted(groups.items()):
        near=[r for r in items if r['distance']['bin']=='near']
        labels=collections.Counter(r['events'][r['target_event']] for r in near)
        coverage.append(dict(source_group_id=group,family_id=family,near_negative=labels[0],near_positive=labels[1],
            near_both_classes_present=bool(labels[0] and labels[1]),
            sample_ids=[r['sample_id'] for r in near]))
    (OUT/'candidate_near_group_coverage.json').write_text(json.dumps(coverage,indent=2),encoding='utf-8')
    summary=dict(candidate_answers=len(candidates),admitted_near_answers=len(admitted),
        near_candidates=sum(r['distance']['bin']=='near' for r in candidates),
        near_two_class_groups=sum(g['near_both_classes_present'] for g in coverage),
        near_candidates_in_two_class_groups=sum(g['near_negative']+g['near_positive'] for g in coverage if g['near_both_classes_present']),
        candidate_answers_sha256=digest(OUT/'candidate_reference_answers.jsonl'),
        scope='reference candidate pool; not a final held-out split, not a generated-model score')
    (OUT/'reference_answer_export_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))

if __name__=='__main__':main()
