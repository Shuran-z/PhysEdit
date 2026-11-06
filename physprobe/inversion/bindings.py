"""Scene description from the final package's source bindings (2026-11-04): for clips whose reference is another sample than our
formal one (no simulation of ours yet), the camera, the object specs and the start poses come from the binding's effective_config
(render.fixed_view, dynamic_objects). Used by make_gen_jobs.py (PHYSPROBE_BINDINGS = bindings dir, PHYSPROBE_BINDING_CLIPS = json list)
for the SAM prompt boxes; checked against the formal path on unchanged clips (event_prompt/binding_boxes.py: 0-4.5 px)."""
import json, math, os
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as Rot
import common as c2

DIR = Path(os.environ['PHYSPROBE_BINDINGS']) if os.environ.get('PHYSPROBE_BINDINGS') else None
CLIPS = set(json.load(open(os.environ['PHYSPROBE_BINDING_CLIPS']))) if os.environ.get('PHYSPROBE_BINDING_CLIPS') else set()


def cfg(clip):
    return json.load(open(DIR / f'{clip}.json'))['effective_config']


def camera(clip):
    r = cfg(clip)['render']; fv = r['fixed_view']; Wd, Ht = fv.get('resolution') or r['resolution']
    eye = np.array(fv['position'], float); at = np.array(fv['look_at'], float)
    if clip[:3] not in c2.NO_SANITIZE:
        at[2] = max(at[2], float(r.get('camera_min_look_z', 0.08))); eye[2] = max(eye[2], float(r.get('camera_min_pos_z', 0.18)))
    fwd = (at - eye) / np.linalg.norm(at - eye); right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
    return eye, fwd, right, up, (Ht / 2) / math.tan(math.radians(fv['fov_deg']) / 2), Wd, Ht


def movers(clip):
    out = {}
    for o in cfg(clip)['dynamic_objects']:
        s = dict(o.get('spec') or {}, **{k: v for k, v in o.items() if k != 'spec'})
        if s.get('fixed') or 'position' not in (s.get('pose') or {}): continue
        p = s['pose']; out[s['name']] = np.array([[*p['position'], *Rot.from_euler('xyz', p.get('euler_xyz', [0, 0, 0]), degrees=True).as_quat()]])
    return out


def visible_boxes(clip):
    keep = c2.config
    try:
        c2.config = lambda c: cfg(clip); return c2.visible_boxes(clip, camera(clip), movers(clip))
    finally: c2.config = keep
