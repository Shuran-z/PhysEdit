"""Read-only reference applicability checks before generation; no fitting or window search."""
import hashlib
import json
import math
from pathlib import Path

from .runners.media_contract import sha256

FIELDS = {'benchmark_items', 'reference_predictions', 'benchmark_sha256', 'reference_predictions_sha256'}
NON_PHYSICAL_FIELDS = {'split', 'generation_prompt', 'input_failure'}


def item_digest(item):
    return hashlib.sha256(json.dumps({k: v for k, v in item.items() if k not in NON_PHYSICAL_FIELDS},
                                    sort_keys=True, allow_nan=False).encode()).hexdigest()


def load_evidence(settings):
    if settings is None:
        return {}, {}, {'reason': 'missing_reference_applicability_evidence'}
    if not isinstance(settings, dict) or set(settings) != FIELDS:
        raise ValueError('applicability requires benchmark_items, reference_predictions and both SHA256 locks')
    bindings = {}
    records = []
    try:
        for key, digest in [('benchmark_items', 'benchmark_sha256'),
                            ('reference_predictions', 'reference_predictions_sha256')]:
            path = Path(settings[key])
            actual = sha256(path)
            if actual != settings[digest]:
                return {}, {}, {'reason': 'reference_applicability_sha256_mismatch', 'file': key}
            rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
            if len({r['id'] for r in rows}) != len(rows):
                return {}, {}, {'reason': 'duplicate_reference_applicability_id', 'file': key}
            records.append({r['id']: r for r in rows})
            bindings[key] = actual
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {}, {}, {'reason': 'unreadable_reference_applicability_evidence', 'detail': str(error)}
    return *records, {'files_sha256': bindings}


def check_item(item, catalog, predictions, receipt, *, frames, fps, condition_frame=23):
    fps = float(fps)
    result = {'item_id': item['id'], 'item_sha256': item_digest(item),
              'status': 'not_applicable', 'reason': receipt.get('reason')}
    if result['reason']:
        return result
    ref, original = catalog.get(item['id']), predictions.get(item['id'])
    reason = None
    if ref is None or original is None:
        reason = 'missing_verified_reference_item'
    elif item_digest(ref) != result['item_sha256']:
        reason = 'registered_reference_item_changed'
    else:
        pred = original.get('prediction', original)
        g = pred.get('gravity')
        sensitivity = ref.get('sensitivity_px')
        if (pred.get('status') != 'ok' or isinstance(g, bool) or not isinstance(g, (int, float))
                or not math.isfinite(g) or g <= 0):
            reason = 'reference_inversion_not_valid'
        elif pred.get('scenario') not in ('projectile', 'freefall'):
            reason = 'reference_motion_not_supported_by_frozen_generation_score'
        elif (isinstance(sensitivity, bool) or not isinstance(sensitivity, (int, float))
              or not math.isfinite(sensitivity) or sensitivity < 15):
            reason = 'reference_not_qualified_by_existing_benchmark'
        elif original.get('target', original.get('gravity_target')) != item['gravity']:
            reason = 'reference_prediction_gravity_identity_mismatch'
        elif pred.get('frames') != item['window']['max_frames']:
            reason = 'reference_prediction_window_mismatch'
        else:
            start = item['window']['start_frame'] / item['fps']
            end = start + (item['window']['max_frames'] - 1) / item['fps']
            condition = condition_frame / item['fps']
            planned = [f for f in range(frames) if start-1e-6 <= condition+f/fps <= end+1e-6]
            result['planned_generated_frames'] = planned
            if start < condition or end > condition+(frames-1)/fps+1e-6 or len(planned) < 4:
                reason = 'generation_clock_does_not_cover_reference_window'
            else:
                visible = item['window'].get('edges_visible', {})
                source_frames = [round((condition+f/fps)*item['fps']) for f in planned]
                if any(not any(visible.get(str(f), [True]*4)) for f in source_frames):
                    reason = 'reference_window_has_unobservable_scheduled_frames'
            result['reference_prediction_sha256'] = hashlib.sha256(
                json.dumps(original, sort_keys=True, allow_nan=False).encode()).hexdigest()
    result.update(status='not_applicable' if reason else 'applicable', reason=reason)
    return result


def assess(items, settings, *, frames, fps):
    catalog, predictions, receipt = load_evidence(settings)
    return {'evidence': receipt, 'items': [check_item(i, catalog, predictions, receipt,
            frames=frames, fps=fps) for i in items], 'uses_generated_results': False,
            'changes_frozen_method': False}
