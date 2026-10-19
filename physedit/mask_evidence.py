"""Sparse, source-bound V/P observations and explicit negative identity reviews.

Missing/rejected masks are None, never fabricated empty silhouettes. This module
is separate from the frozen SAM frontend and gravity observations.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

from .runners.media_contract import sha256


def export_masks(rows, contexts, items, root, observations_root):
    measures = {}
    for line in (observations_root / 'measurements_v4.jsonl').read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            if record['id'] in measures:
                raise ValueError('duplicate_mask_measurement_id')
            measures[record['id']] = record
    observation_sha = sha256(observations_root / 'measurements_v4.jsonl')
    entries, failures = {}, {}
    for row in rows:
        sid = row['sample_id']
        if sid not in contexts:
            continue
        ctx, pair, errors = contexts[sid], {}, []
        for kind in ('source', 'generated'):
            try:
                jid = sid + '__vp_' + kind
                m = measures[jid]
                start = ctx['condition_frame'] if kind == 'source' else 0
                scope = list(range(start, ctx[kind + '_frames']))
                if m['frames'] != scope or len(m['statuses']) != len(scope):
                    raise ValueError('vp_mask_measurement_scope_mismatch')
                if m['video_sha256'] != ctx[kind + '_sha256']:
                    raise ValueError('vp_mask_measurement_video_mismatch')
                shape = (row['source_height'], row['source_width'])
                masks, frames, reasons = [], [], []
                for i, f in enumerate(scope):
                    try:
                        declared = m['mask_sha256'].get(str(f))
                        if declared is None:
                            raise ValueError(f'frame {f}: {m["statuses"][i]}')
                        path = observations_root / 'runs/sam31_visible_projection_full30_masks' / f'{hashlib.sha256(jid.encode()).hexdigest()[:12]}_{f}.npz'
                        with np.load(path, allow_pickle=False) as z:
                            mask = z['mask']
                        if mask.dtype.kind not in 'bu' or not np.isin(mask, [0, 1]).all():
                            raise ValueError('vp_mask_not_binary')
                        if mask.shape != shape:
                            raise ValueError('vp_mask_shape_mismatch')
                        mask = mask.astype(np.uint8)
                        if hashlib.sha256(mask.tobytes()).hexdigest() != declared:
                            raise ValueError('vp_mask_measurement_binding_missing_or_mismatched')
                        masks.append(mask)
                        frames.append(f)
                        reasons.append('')
                    except Exception as error:
                        reasons.append(type(error).__name__ + ': ' + str(error))
                if any(reasons):
                    errors.append(kind + ': ' + '; '.join(r for r in reasons if r))
                dest = root / (hashlib.sha256(sid.encode()).hexdigest()[:20] + '_' + kind + '_masks.npz')
                if dest.exists():
                    raise FileExistsError(dest)
                np.savez_compressed(dest, masks=np.stack(masks) if masks else np.empty((0, *shape), np.uint8),
                                    frames=np.asarray(frames, dtype=np.int64), scope_frames=np.asarray(scope, dtype=np.int64),
                                    unavailable_reasons=np.asarray(reasons, dtype=str),
                                    target_name=items[row['item_id']]['object_name'], fps=ctx[kind + '_fps'],
                                    video_sha256=ctx[kind + '_sha256'], mask_method='sam31_frozen_v4',
                                    observation_sha256=observation_sha)
                pair[kind] = dict(path=str(dest.resolve()), sha256=sha256(dest))
            except Exception as error:
                errors.append(f'vp_{kind}_segmentation_failure: {type(error).__name__}: {error}')
        if pair:
            entries[sid] = pair
        if errors:
            failures[sid] = '; '.join(errors)
    with (root / 'vp_mask_manifest.jsonl').open('x') as f:
        for sid, pair in entries.items():
            f.write(json.dumps(dict(sample_id=sid, **pair), allow_nan=False) + '\n')
    return entries, failures


def load_sequence(entry, ctx, kind, target, size):
    if sha256(entry['path']) != entry['sha256']:
        raise ValueError(kind + '_mask_file_drift')
    start = ctx['condition_frame'] if kind == 'source' else 0
    scope = list(range(start, ctx[kind + '_frames']))
    with np.load(entry['path'], allow_pickle=False) as z:
        if str(z['video_sha256'].item()) != ctx[kind + '_sha256']:
            raise ValueError(kind + '_mask_video_mismatch')
        if str(z['target_name'].item()) != target:
            raise ValueError(kind + '_mask_target_mismatch')
        if float(z['fps'].item()) != ctx[kind + '_fps']:
            raise ValueError(kind + '_mask_clock_mismatch')
        indices, masks = z['frames'], z['masks']
        if indices.ndim != 1 or indices.dtype.kind not in 'iu':
            raise ValueError(kind + '_mask_frame_scope_mismatch')
        frames = indices.tolist()
        if frames != sorted(set(frames)) or not set(frames) <= set(scope):
            raise ValueError(kind + '_mask_frame_scope_mismatch')
        if 'scope_frames' in z:
            if z['scope_frames'].dtype.kind not in 'iu' or z['scope_frames'].tolist() != scope:
                raise ValueError(kind + '_mask_frame_scope_mismatch')
            reasons = z['unavailable_reasons'].tolist()
            if not isinstance(reasons, list) or len(reasons) != len(scope):
                raise ValueError(kind + '_mask_validity_scope_mismatch')
            available = set(frames)
            if any(not isinstance(r, str) or ((f in available) != (r == '')) for f, r in zip(scope, reasons)):
                raise ValueError(kind + '_mask_validity_inconsistent')
        else:
            if frames != scope:
                raise ValueError(kind + '_mask_frame_scope_mismatch')
            reasons = [''] * len(scope)
        if masks.ndim != 3 or len(masks) != len(frames) or masks.shape[1:] != (size[1], size[0]):
            raise ValueError(kind + '_mask_shape_mismatch')
        if masks.dtype.kind not in 'bu' or not np.isin(masks, [0, 1]).all():
            raise ValueError(kind + '_mask_not_binary')
        method = str(z['mask_method'].item())
        if not method:
            raise ValueError('missing_mask_method')
        sequence = [None] * len(scope)
        for f, m in zip(frames, masks):
            sequence[f - start] = m.astype(bool)
    rejected = []
    if entry.get('review'):
        ref = entry['review']
        if sha256(ref['path']) != ref['sha256']:
            raise ValueError(kind + '_mask_review_file_drift')
        review = json.loads(Path(ref['path']).read_text())
        if review['video_sha256'] != ctx[kind + '_sha256'] or review['target_name'] != target:
            raise ValueError(kind + '_mask_review_identity_mismatch')
        seen = set()
        for r in review['rejected_frames']:
            f = r['frame_index']
            if type(f) is not int or f not in scope or f in seen or not isinstance(r['reason'], str) or not r['reason'].strip():
                raise ValueError(kind + '_mask_review_frame_invalid')
            seen.add(f)
            m = sequence[f - start]
            if m is None or hashlib.sha256(m.astype(np.uint8).tobytes()).hexdigest() != r['mask_sha256']:
                raise ValueError(kind + '_mask_review_observation_mismatch')
            sequence[f - start] = None
            reasons[f - start] = 'identity_review_rejected: ' + r['reason']
            rejected.append(r)
    provenance = dict(entry, mask_method=method, video_sha256=ctx[kind + '_sha256'],
                      scope_frames=scope, unavailable_frames={str(f): r for f, r in zip(scope, reasons) if r},
                      rejected_frames=rejected, identity_accuracy_certified=False,
                      available_frames=sum(m is not None for m in sequence))
    return sequence, provenance


def required_masks(sequence, indices, kind, provenance):
    indices = list(indices)
    missing = [i for i in indices if i < 0 or i >= len(sequence) or sequence[i] is None]
    if missing:
        detail = {str(provenance['scope_frames'][i]): provenance['unavailable_frames'][str(provenance['scope_frames'][i])]
                  for i in missing if 0 <= i < len(sequence)}
        raise ValueError(kind + '_required_masks_unavailable: ' + json.dumps(detail, sort_keys=True))
    return [sequence[i] for i in indices]


def attach_reviews(entries, rows, manifest):
    records = [json.loads(l) for l in Path(manifest).read_text().splitlines() if l.strip()]
    ids = [r['sample_id'] for r in records]
    if len(ids) != len(set(ids)) or not set(ids) <= {r['sample_id'] for r in rows}:
        raise ValueError('mask_review_manifest_identity_mismatch')
    for record in records:
        if set(record) - {'sample_id', 'source', 'generated'}:
            raise ValueError('mask_review_manifest_unknown_field')
        for kind in ('source', 'generated'):
            if kind in record:
                # If no observations exist, they already fail independently.
                entry = entries.get(record['sample_id'], {}).get(kind)
                if entry is not None:
                    entry['review'] = record[kind]
