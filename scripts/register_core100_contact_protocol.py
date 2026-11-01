"""Freeze the author's contact-target amendment without rewriting old contracts."""
import copy
import hashlib
import json
from pathlib import Path

BASE = Path('annotation_site/resources/event_contracts.json')
OUT = Path('annotation_site/resources/core100_contact_protocol_20261027.json')
REVISION = 'core100-contact-targets-v1-20261027'


def main():
    old = json.loads(BASE.read_text(encoding='utf-8'))
    clips = copy.deepcopy(old['clips'])
    amended = []
    for cid, clip in clips.items():
        if not cid.startswith(('T12', 'T13')):
            continue
        keys = (['stapler_contacts_tissue_box'] if cid.startswith('T12') else
                ['driver_to_falling_book_contact', 'falling_book_to_drink_contact'])
        clip['parent_contract'] = copy.deepcopy(old['clips'][cid])
        clip['events'] = {key: copy.deepcopy(clip['events'][key]) for key in keys}
        for event in clip['events'].values():
            event.update(role='author_approved_contact_target', formal_scoring_allowed=True,
                         evidence_scope='definition approved; reference truth, RGB visibility, window and boundary admission remain separate')
        clip.update(version=REVISION, status='definition_frozen_reference_admission_pending',
                    critical_contract_status='author_approved_new_contact_target',
                    formal_score_event_ids=keys, critical_targets=keys,
                    required_order=[] if cid.startswith('T12') else [[keys[0], keys[1]]],
                    order_scope='first native contact, lexicographic frame and physics-step order; ties allowed as in the source production check',
                    formal_scoring_admission='pending_source_media_window_and_boundary_admission',
                    scoring_blockers=['reference_admission_pending', 'same_target_boundary_pending'],
                    terminal_outcome_scope='No claim to reconstruct the missing historical motion/fall classifier.',
                    author_approval={'date': '2026-10-27', 'answer': '采用新版本接触协议',
                                     'scope': 'T12 original stapler-box contact; T13 two source-declared contacts and their order'})
        amended.append(cid)
    assert len(clips) == 100 and len(amended) == 10
    payload = dict(schema=REVISION, status='definition_frozen_not_reference_admitted',
                   base_contract_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),
                   prompt_policy='Exact frozen v6 input binding; this amendment does not change generation text or media.',
                   changed_cases=sorted(amended),
                   summary=dict(target_definition_cases=sum(bool(c.get('formal_score_event_ids')) for c in clips.values()),
                                amended_cases=10, new_reference_admissions=0, new_scores=0),
                   source_contracts_preserved=True, clips=clips)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    if OUT.exists() and OUT.read_text(encoding='utf-8') != text:
        raise ValueError('Frozen amendment already exists with different input; create a new revision')
    OUT.write_text(text, encoding='utf-8')
    print(json.dumps(payload['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
