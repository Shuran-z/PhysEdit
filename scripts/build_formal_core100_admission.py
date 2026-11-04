"""Connect already-authorized reference admissions; never promote numerical rows."""
import datetime
import hashlib
import json
from pathlib import Path

from physedit.core100_release import load
from physedit.boundary import distance

ROOT = Path(__file__).resolve().parents[1]


def build():
    root, manifest, conditions, _ = load()
    old_path = ROOT / 'annotation_site/resources/reference_window_admission.json'
    old = json.loads(old_path.read_text(encoding='utf8'))
    active = json.loads((ROOT / 'annotation_site/resources/core100_distance_bindings.json').read_text(encoding='utf8'))
    by_active = {r['clip_id']: r for r in active['cases']}
    old_refs = []
    for r in old['references']:
        current = by_active[r['clip_id']]
        assert r['horizon_s'] == current['horizon_s'] and r['theta'] == current['theta']
        assert r['reference_state_sha256'] == current['source_state_sha256']
        old_refs.append(dict(r, reference_video_sha256=current['reference_video_sha256'],
                             reference_release_version=active['reference_release_version']))
    answers = [json.loads(line) for line in (root / 'answers_t19.jsonl').read_text(encoding='utf8').splitlines()]
    by_condition = {r['clip_id']: r for r in conditions['tasks']}
    references = []
    for answer in answers:
        cid = answer['point_id']; current = by_active[cid]
        assert answer['reference_admission']['status'] == 'admitted'
        assert answer['reference_video_sha256'] == current['reference_video_sha256']
        assert answer['evaluation_horizon_s'] == current['horizon_s']
        qa = json.loads((root / 'references' / cid / 'qa.json').read_text(encoding='utf8'))
        assert qa['status'] == 'PASS' and all(qa['checks'].values())
        assert hashlib.sha256((root / 'references' / cid / 'qa.json').read_bytes()).hexdigest() == answer['source_qa_sha256']
        has_contact = 't19_striker|t19_target' in qa['first_contacts_s']
        assert int(has_contact) == answer['events']['striker_target_contact']
        measured = distance(answer)
        condition = by_condition[cid]
        references.append(dict(clip_id=cid, cohort_id='t19-isaac-v1-h209f',
            sample_id=current['sample_id'], reference_release_version=manifest['version'],
            reference_video_sha256=answer['reference_video_sha256'], condition_sha256=answer['condition_sha256'],
            condition_frame_index=0, target_event=answer['target_event'], reference_label=answer['events'][answer['target_event']],
            horizon_s=answer['evaluation_horizon_s'], theta=answer['theta'], family_id=answer['family_id'],
            fixed_context_sha256=answer['source_group_id'], boundary_interval=answer['boundary']['bracket'],
            normalization_span=answer['boundary']['normalization_span'],
            normalized_distance_interval=measured['normalized_absolute_interval'], bin=measured['bin'],
            prompt_variants_en=condition['prompt_variants_en'], source_config_sha256=answer['source_config_sha256'],
            reference_admission=answer['reference_admission'], evidence_sha256=manifest['files']))
    by_ref = {r['clip_id']: r for r in references}; pairs = []
    for pair in manifest['pairs']:
        a, b = [by_ref[c] for c in pair['clips']]
        assert a['reference_label'] != b['reference_label']
        assert a['fixed_context_sha256'] == b['fixed_context_sha256']
        assert a['boundary_interval'] == b['boundary_interval']
        assert a['horizon_s'] == b['horizon_s']
        worst = max(abs(a['normalized_distance_interval'][i]-b['normalized_distance_interval'][j])
                    for i in (0,1) for j in (0,1))
        assert worst <= .02 and a['bin'] == b['bin'] == 'near'
        pairs.append(dict(pair_id=pair['pair_id'], clips=pair['clips'], horizon_s=a['horizon_s'],
            event=a['target_event'], boundary_interval=a['boundary_interval'],
            worst_case_normalized_distance_asymmetry=worst, pair_tolerance=.02,
            pairing_mode='coupled_prompt_variant_and_seed', independent_pair_accuracy_not_inferred=True))
    return dict(schema='core100-explicit-formal-cohorts-v1',
        generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        policy=dict(near_upper=.05, pair_distance_tolerance=.02,
                    source='docs/critical_boundary/CRITICAL_BOUNDARY_PROTOCOL.md', new_thresholds=False),
        cohorts=[dict(cohort_id='t17-contact-h6p4', scoring_adapter='existing_scoped_outputs',
                      references=old_refs, pairs=old['pairs']),
                 dict(cohort_id='t19-isaac-v1-h209f', scoring_adapter='strict_replacement_inputs',
                      references=references, pairs=pairs)],
        summary=dict(formally_registered_reference_cases=len(old['references'])+len(references),
                     formally_registered_near_points=len(old['references'])+sum(r['bin']=='near' for r in references),
                     formally_registered_pairs=len(old['pairs'])+len(pairs),
                     new_scientific_admission_claims=0, restored_website_admitted_references=5),
        provenance=dict(active_manifest_sha256=hashlib.sha256((root/'MANIFEST.json').read_bytes()).hexdigest(),
                        legacy_window_admission_sha256=hashlib.sha256(old_path.read_bytes()).hexdigest()),
        note='Restores explicit frozen T19 admissions. Calibration-only negative event outcomes remain valid '
             'for this author-admitted fixed-simulator contact protocol, not claims of general physical certification. '
             'Legacy annotations and all existing score fields are preserved.')


if __name__ == '__main__':
    result = build()
    path = ROOT / 'annotation_site/resources/core100_formal_cohorts.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(result['summary']))
