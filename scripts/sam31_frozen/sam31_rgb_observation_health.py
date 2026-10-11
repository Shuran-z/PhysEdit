"""Image-only observation checks. No fitting, gravity or trajectory inputs."""
import cv2
import numpy as np
from repair_sam31_static_attachment import _repair_core


def initial_background_valid(shape, scene_boxes):
    valid = np.ones(shape, dtype=bool)
    h, w = shape
    for box in scene_boxes.values():
        x, y, xx, yy = box
        valid[max(0, int(np.floor(y))-2):min(h, int(np.ceil(yy))+2),
              max(0, int(np.floor(x))-2):min(w, int(np.ceil(xx))+2)] = False
    return valid


def foreground_evidence(rgb, initial, valid):
    current = rgb.astype(np.float32)
    bg = initial.astype(np.float32)
    changed = np.max(np.abs(current-bg), axis=-1) > 12
    scale = np.sum(current*bg, axis=-1)/np.maximum(np.sum(bg*bg, axis=-1), 1)
    dim_only = (scale >= 0) & (scale <= 1) & (np.max(np.abs(current-scale[..., None]*bg), axis=-1) <= 2)
    return changed & ~dim_only & valid


def choose_actual_mask(rgb, initial, valid, primary, alternate):
    """Choose neural observations by current RGB agreement, never fitted error.

    Both candidates already have the same initial target identity. Evaluate
    only where the initial scene boxes certify an unobstructed background.
    Retain the declared initial route when evidence is insufficient/ambiguous.
    """
    if alternate is None:
        return primary, dict(route='no_alternate_actual_mask')
    if primary is None:
        return alternate, dict(route='missing_primary_actual_mask')
    union = (primary > 0) | (alternate > 0)
    yy, xx = np.where(union)
    if not len(xx): return primary, dict(route='empty_candidates')
    roi = np.zeros_like(valid)
    roi[max(0, yy.min()-3):yy.max()+4, max(0, xx.min()-3):xx.max()+4] = True
    known = roi & valid
    fraction = float(known.sum()/max(roi.sum(), 1))
    if fraction < .8:
        return primary, dict(route='initial_background_not_certified', known_fraction=fraction)
    foreground = foreground_evidence(rgb, initial, valid) & roi
    if foreground.sum() < 16:
        return primary, dict(route='insufficient_rgb_foreground', known_fraction=fraction)
    scores = []
    for m in (primary, alternate):
        pred = (m > 0) & known
        overlap = (pred & foreground).sum()
        scores.append(float(2*overlap/max(pred.sum()+foreground.sum(), 1)))
    use_alt = scores[1] > scores[0] + .1
    return (alternate if use_alt else primary), dict(
        route='alternate_rgb_agreement' if use_alt else 'primary_rgb_agreement',
        known_fraction=fraction, primary_f1=scores[0], alternate_f1=scores[1],
        rgb_foreground_pixels=int(foreground.sum()))


def repair_certified(images, masks, initial, valid):
    """Veto false background evidence caused by a missed foreground mask.

    Existing temporal attachment policy is kept where the initial object
    blocks a background observation. Else an erased pixel must independently
    agree with the initial real background. No foreground is filled/invented.
    """
    ms = np.asarray(masks, dtype=np.uint8)
    yy, xx = np.where(ms.any(axis=0))
    if not len(xx): return list(ms), []
    h, w = ms.shape[1:]
    x, y = max(0, xx.min()-3), max(0, yy.min()-3)
    x1, y1 = min(w, xx.max()+4), min(h, yy.max()+4)
    # The original policy proposes removals. Validate each actual proposed
    # pixel against independently observed, initially unoccluded background.
    cropped = ms[:, y:y1, x:x1]
    rgb = [im[y:y1, x:x1] for im in images]
    proposed, audits = _repair_core(rgb, cropped)
    outputs = []
    for k, (old, candidate) in enumerate(zip(cropped, proposed)):
        veto = foreground_evidence(rgb[k], initial[y:y1, x:x1], valid[y:y1, x:x1]) & (old > 0) & (candidate == 0)
        candidate[veto] = old[veto]
        full = ms[k].copy(); full[y:y1, x:x1] = candidate
        outputs.append(full)
        audits[k]['independent_rgb_foreground_retained'] = int(veto.sum())
        audits[k]['after_pixels'] = int(candidate.sum())
        audits[k]['removed_background_pixels'] = int(old.sum()-candidate.sum())
    return outputs, audits
