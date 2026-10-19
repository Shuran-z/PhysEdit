"""Apply event-specific visual review without changing numerical evidence."""
import copy
import json
from pathlib import Path
from physedit.boundary import digest

REVIEWS = Path('review/scene_family_completion_20261018/near375_visual/observability_reviews.json')

def apply_review(record, review):
    r = copy.deepcopy(record)
    if review is None:
        return r
    for field in ('sample_id', 'engine', 'target_event', 'reference_state_sha256'):
        if r.get(field) != review.get(field):
            raise ValueError('visual review identity mismatch: ' + field)
    expected = r.get('reference_video_hashes', {}).get(review['camera'])
    if review['status'] == 'pass':
        if not expected or expected != review['video_sha256']:
            raise ValueError('visual review video hash mismatch')
        if digest(review['evidence']) != review['evidence_sha256']:
            raise ValueError('visual review evidence changed')
        r['blocking_reasons'] = [x for x in r.get('blocking_reasons', [])
                                 if x != 'reference_rgb_observability_pending']
        r['rgb_observability_status'] = 'reviewed_cam01_target_event'
    else:
        r['blocking_reasons'] = sorted(set(r.get('blocking_reasons', []) + review['reasons']))
        if review['status'] == 'retired_render':
            r['rgb_observability_status'] = 'retired_render_awaiting_replacement'
            r['blocking_reasons'] = sorted(set(r['blocking_reasons'] + ['reference_render_retired']))
    r['visual_review'] = review
    return r

def load_reviews():
    if not REVIEWS.exists():
        return {}
    rows = json.loads(REVIEWS.read_text(encoding='utf-8'))
    result = {(r['engine'], r['sample_id']): r for r in rows}
    if len(result) != len(rows):
        raise ValueError('duplicate visual reviews')
    return result
