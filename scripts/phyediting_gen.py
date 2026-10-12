"""Gravity-editing generation inputs for PhyEditing, and scoring of the generated videos.

`build`: for benchmark items, the condition frame (the last frame of the static prelude, identical across the five
gravities of a scene), a prompt (event description + target gravity) and a generation template row in the format
the physedit runners read.

`score`: generated videos tracked from their first frame (= the condition frame) are fitted in the item's declared
window. Frame times are the condition time plus frame index / model fps. The declared initial state is the reference
trajectory's at the target gravity (as for the ground-truth videos). The default `--v0 agnostic` supplies no reference
linear velocity or direction. Fixed-window scoring retains every scheduled frame; missing observations fail the
whole case. Requested-gravity deviation is not an error against known generated physical truth.

    python scripts/phyediting_gen.py build ITEMS.jsonl OUT_DIR --host-root DIR [--per-gravity N] [--seed S]
    python scripts/phyediting_gen.py rows TEMPLATE.jsonl ROWS.jsonl --model ltx_i2v --frames 81 --fps 16 --out-root DIR
    python scripts/phyediting_gen.py jobs ITEMS.jsonl ROWS.jsonl JOBS.jsonl
    python scripts/phyediting_gen.py score ITEMS.jsonl ROWS.jsonl TRACKS.jsonl OUT.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gravtrace.fit import safe_fit  # noqa: E402

CONDITION_FRAME = 23  # the prelude is static for 24 frames, so this frame is the same at every gravity
MAX_SPEED = 8.0  # m/s, the launch-speed bound of `score --v0 agnostic` (tabletop pushes stay well below)
EVENTS = {
    "T03": "On a table, a thin book slides into a soda can standing at the table edge; the can falls off onto a lower shelf and a phone drops to the floor.",
    "T05": "A soda can slides across a table toward two objects with a gap between them.",
    "T08": "On a small table, a moving book hits another book that carries a mug; the mug and the books slide off the table edge and fall to the floor.",
    "T16": "A folder leaning on a book tips over when its support is removed and falls onto a small box.",
    "T17": "A red soda can rolls down a tilted book used as a ramp on a table, rolls past a tissue box and falls off the table edge.",
    "T18": "A book is pulled out of a stack of books on a table; the books above lose their support, tilt and tumble down.",
    "T19": "A soda can slides across a table and hits another can, which is pushed to the table edge and falls.",
    "T20": "A sliding book pushes a soda can, which pushes a small box, which pushes a cup, in a chain reaction on a table.",
}
GRAVITY = {
    1.62: "The scene takes place under the Moon's low gravity (1.62 m/s^2), so falling objects drop slowly.",
    3.71: "The scene takes place under Mars gravity (3.71 m/s^2), weaker than on Earth, so objects fall more slowly than usual.",
    9.81: "The scene takes place under normal Earth gravity (9.81 m/s^2).",
    15.0: "The scene takes place under strong gravity (15 m/s^2), about 1.5 times Earth's, so objects fall faster than usual.",
    24.0: "The scene takes place under very strong gravity (24 m/s^2), about 2.5 times Earth's, so objects fall very fast.",
}
NEGATIVE = "camera motion, cuts, blurry, distorted objects, objects appearing or disappearing, text, watermark"


def build(args) -> None:
    from physedit.runners.media_contract import sha256, validate_video
    items = [json.loads(line) for line in Path(args.items).read_text().splitlines() if line.strip()]
    if len({it['id'] for it in items}) != len(items):
        raise ValueError('Duplicate registered item IDs')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'conditioning').mkdir()
    (out / 'prompts').mkdir()
    rows, per_g = [], defaultdict(int)
    quota = getattr(args, 'per_gravity', None)
    for k, it in enumerate(items):
        # All registered items remain, including unsupported events and quota exclusions.
        import hashlib
        sid = hashlib.sha256(it['id'].encode()).hexdigest()[:24]
        host = args.host_root.rstrip('/')
        local = Path(args.data_root) / it['video']
        prompt = it.get('generation_prompt') or EVENTS.get(it['event'])
        reason = it.get('input_failure')
        if not reason and (not prompt or it['gravity'] not in GRAVITY):
            reason = 'unsupported_registered_prompt_or_gravity'
        if not reason and (it['window']['max_frames'] < args.min_window_frames or
                it['window']['start_frame'] + it['window']['max_frames'] > args.max_end_frame):
            reason = 'not_applicable_registered_window'
        if not reason and quota is not None and per_g[it['gravity']] >= quota:
            reason = 'not_selected_explicit_per_gravity_quota'
        w, h = it.get('image_size', [0, 0])
        if not reason:
            try:
                validate_video(local, fps=float(it['fps']), width=w, height=h)
                cap = cv2.VideoCapture(str(local))
                try:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, CONDITION_FRAME)
                    ok, img = cap.read()
                finally:
                    cap.release()
                if not ok:
                    raise ValueError('condition_frame_read_failure')
                if not cv2.imwrite(str(out / 'conditioning' / f'{sid}.png'), img):
                    raise ValueError('condition_image_write_failure')
                pdir = out / 'prompts' / sid
                pdir.mkdir()
                (pdir / 'prompt.txt').write_text(f"{prompt} The camera is fixed. {GRAVITY[it['gravity']]}")
                (pdir / 'negative_prompt.txt').write_text(NEGATIVE)
                per_g[it['gravity']] += 1
            except (OSError, ValueError, cv2.error) as error:
                reason = str(error)
        row = {
            'index': k, 'mode': 'i2v', 'sample_id': sid, 'source_sample_id': sid, 'item_id': it['id'],
            'benchmark': f"phyediting_{it['event']}", 'scenario': 'projectile',
            'source_video': f"{args.source_root.rstrip('/')}/{it['video']}", 'source_width': w, 'source_height': h,
            'source_sample_fps': float(it['fps']), 'source_native_fps': float(it['fps']),
            'source_orientation': 'square' if w == h else ('landscape' if w > h else 'portrait'),
            'aspect_ratio': '1:1' if w == h else ('16:9' if w > h else '9:16'),
            'condition_image': f'{host}/conditioning/{sid}.png', 'condition_frames': 1,
            'condition_frame_index': CONDITION_FRAME, 'condition_time_ms': 1000. * CONDITION_FRAME / it['fps'],
            'prompt_file': f'{host}/prompts/{sid}/prompt.txt', 'negative_prompt_file': f'{host}/prompts/{sid}/negative_prompt.txt',
            'prompt_granularity': 'fine', 'seed': args.seed, 'gravity_truth': it['gravity'],
            'protocol': 'phyediting_gravity_v1', 'gen_height': 480, 'gen_width': 704 if w >= h else 480,
            'input_failure': reason, 'split': it.get('split', 'unspecified'),
            'source_video_sha256': sha256(local) if local.is_file() else None,
        }
        rows.append(row)
    for name, content in [('template.jsonl', rows), ('input_failures.jsonl', [r for r in rows if r['input_failure']])]:
        (out/name).write_text(''.join(json.dumps(r)+'\n' for r in content))
    (out/'videos.txt').write_text(''.join(it['video']+'\n' for it in items))
    print(json.dumps(dict(registered=len(rows), eligible=sum(not r['input_failure'] for r in rows), per_gravity=dict(per_g))))


def model_rows(args) -> None:
    """A model's manifest from the template: frame count, frame rate and output paths under OUT_ROOT/<model>."""
    with open(args.out, "x") as f:
        for line in open(args.template):
            row = json.loads(line)
            out_dir = f"{args.out_root.rstrip('/')}/{args.model}/{row['sample_id']}"
            row.update(model_name=args.model, pipeline=args.model, num_frames=args.frames, output_fps=args.fps, out_dir=out_dir,
                       generated_video=f"{out_dir}/raw.mp4", generated_video_resized_to_source=f"{out_dir}/resized.mp4")
            if getattr(args, 'mode', None):
                row['mode'] = args.mode
            if args.canvas:  # the model's generation size (landscape; swapped for portrait sources)
                w, h = map(int, args.canvas.lower().split("x"))
                if row['source_width'] == row['source_height'] and getattr(args, 'square_canvas', None):
                    row['gen_width'] = row['gen_height'] = int(args.square_canvas)
                else:
                    row["gen_width"], row["gen_height"] = (w, h) if row["source_width"] >= row["source_height"] else (h, w)
            f.write(json.dumps(row) + "\n")


def track_jobs(args) -> None:
    """Initial declared prompts only; missing source/header rows are retained."""
    from phyediting_samples import prompt_boxes
    items = {it['id']: it for it in _json_rows(args.items)}
    jobs = []
    for row in _json_rows(args.rows):
        it = items[row['item_id']]
        reason, boxes = row.get('input_failure'), {}
        if not reason:
            try:
                header = json.loads((Path(args.compact)/f"{it['trajectory']}.json").read_text())
                with np.load(Path(args.compact)/f"{it['trajectory']}.npz", allow_pickle=False) as z:
                    boxes = prompt_boxes(header, z, it['camera_id'], frame=row['condition_frame_index'])
                if it['object_name'] not in boxes:
                    reason = 'missing_declared_target_box'
            except (OSError, ValueError, KeyError) as error:
                reason = 'missing_or_invalid_declared_prompt_source: '+str(error)
        video = row['generated_video_resized_to_source']
        if args.local_prefix:
            video = video.replace(args.host_prefix, args.local_prefix, 1)
        jobs.append(dict(id=row['sample_id'], video=video, prompt_frame=0, objects=boxes,
                         last_frame=int(row['num_frames'])-1, input_failure=reason))
    with Path(args.out).open('x') as output:
        output.write(''.join(json.dumps(j)+'\n' for j in jobs))


def _json_rows(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def _read_tracks(path) -> dict:
    tracks = {}
    for rec in _json_rows(path):
        if rec["id"] in tracks:
            raise ValueError("Duplicate observation ID: "+rec["id"])
        tracks[rec["id"]] = rec
    return tracks


def _read_camera_motion(path) -> dict:
    motion_of = {}
    if path:  # per-frame similarity onto frame 0 (scripts/camera_motion.py)
        for line in open(path):
            rec = json.loads(line)
            if "affine" in rec:
                motion_of[rec["id"]] = dict(zip(rec["frames"], (np.asarray(a) for a in rec["affine"])))
    return motion_of


def _sample(row: dict, it: dict, track: dict, v0: str, to_first: dict, shift: float = 0.0) -> dict:
    """GravTrace sample of a generated video in the item's window, moved by `shift` seconds (0: the reference
    window, whose declared edge visibility then applies)."""
    tr = track.get("tracks", {}).get(it["object_name"])
    fps_gen = float(row.get("output_fps") or track.get("fps") or 16.0)
    t_cond = row["condition_frame_index"] / float(it["fps"])
    w0, n = it["window"]["start_frame"] / float(it["fps"]) + shift, it["window"]["max_frames"]
    w1 = w0 + (n - 1) / float(it["fps"])
    frames, boxes, times = [], [], []
    for f, b in zip(tr["frames"] if tr else [], tr["xyxy"] if tr else []):
        if f in to_first:  # undo the generated camera's motion: the box in frame 0's image
            corners = np.array([[b[0], b[1], 1.0], [b[2], b[1], 1.0], [b[0], b[3], 1.0], [b[2], b[3], 1.0]]) @ to_first[f].T
            b = [*corners.min(axis=0).tolist(), *corners.max(axis=0).tolist()]
        t = t_cond + f / fps_gen
        if w0 - 1e-6 <= t <= w1 + 1e-6:
            frames.append(int(round((t - shift) * it["fps"])))
            boxes.append(b)
            times.append(t - w0)
    motion = dict(it["motion"])
    if times:  # GravTrace times the first fitted frame from the declared state by t0
        motion["t0"] = [times[0], times[0]]
    if v0 == "free":  # robustness variant: launch speed within +-50 %, direction free
        speed = float(np.linalg.norm(motion.pop("v0")))
        motion.update(speed=[0.5 * speed, 1.5 * speed + 0.05], angle_deg=[-89.0, 89.0],
                      directions=[(np.asarray(it["motion"]["v0"]) / max(speed, 1e-9)).tolist()])
    elif v0 == "agnostic":  # nothing from the reference velocity: any speed up to MAX_SPEED, any direction
        motion.pop("v0", None)
        motion.update(speed=[0.0, MAX_SPEED], angle_deg=[-89.0, 89.0])
    # the declared visibility of each edge, at the reference frame nearest in time (all edges when shifted)
    seen = it["window"].get("edges_visible", {}) if abs(shift) < 1e-9 else {}
    window = {"max_frames": len(frames), "start_frame": 0,
              "edges_visible": {str(i): seen.get(str(f), [True] * 4) for i, f in enumerate(frames)}}
    return {"id": row["sample_id"], "scenario": "projectile", "fps": it["fps"], "image_size": it["image_size"],
            "camera": it["camera"], "object": it["object"], "motion": motion, "window": window,
            "boxes": {"frames": list(range(len(frames))), "xyxy": boxes, "times": times}}


def score(args) -> None:
    items = {json.loads(l)["id"]: json.loads(l) for l in open(args.items)}
    tracks = _read_tracks(args.tracks)
    motion_of = _read_camera_motion(args.camera_motion)
    out = open(args.out, "x")
    shard, shards = (int(v) for v in args.shard.split("/"))
    for k, line in enumerate(open(args.rows)):
        if k % shards != shard:
            continue
        row = json.loads(line)
        it = items[row["item_id"]]
        track = tracks.get(row["sample_id"], {})
        to_first = motion_of.get(row["sample_id"], {})
        if not args.scan:
            pred = _score_fixed_window(row, it, track, args.v0, to_first, args.offset_mode)
            out.write(json.dumps({**pred, "item_id": row["item_id"], "gravity_target": row["gravity_truth"]}) + "\n")
            continue
        # scan: the item's window slid over the whole clip, --scan-step generated frames at a time
        fps_gen = float(row.get("output_fps") or track.get("fps") or 16.0)
        tr = track.get("tracks", {}).get(it["object_name"])
        last = (max(tr["frames"]) if tr and tr["frames"] else 0) / fps_gen
        t_cond = row["condition_frame_index"] / float(it["fps"])
        w0 = it["window"]["start_frame"] / float(it["fps"])
        span = (it["window"]["max_frames"] - 1) / float(it["fps"])
        shifts = [t_cond + j / fps_gen - w0 for j in range(0, int(last * fps_gen) + 1, args.scan_step)
                  if j / fps_gen + span <= last + 1e-6]
        scan = []
        for sh in shifts:
            sample = _sample(row, it, track, args.v0, to_first, shift=sh)
            sample["offset_mode"] = args.offset_mode
            if len(sample["boxes"]["xyxy"]) >= 4:
                pred = safe_fit(sample)
                scan.append([round(sh, 4), pred.get("gravity"), pred.get("status")])
        out.write(json.dumps({"id": row["sample_id"], "item_id": row["item_id"], "gravity_target": row["gravity_truth"],
                              "scan": scan}) + "\n")


def _score_fixed_window(row, it, track, v0="agnostic", to_first=None, offset_mode="anchor"):
    """Check the registered frame contract before calling the unchanged fitter."""
    fps = float(row.get("output_fps") or track.get("fps") or 16.0)
    start = it["window"]["start_frame"] / float(it["fps"])
    end = start + (it["window"]["max_frames"] - 1) / float(it["fps"])
    condition = row["condition_frame_index"] / float(it["fps"])
    planned = [f for f in range(int(row["num_frames"]))
               if start - 1e-6 <= condition + f / fps <= end + 1e-6]
    base = {"id": row["sample_id"], "frames": 0, "planned_frames": len(planned),
            "planned_generated_frames": planned}
    failure = _binding_failure(row, track)
    if failure:
        return {**base, 'status': 'input_failure', 'reason': failure}
    tr = track.get("tracks", {}).get(it["object_name"], {})
    frames, boxes = tr.get("frames", []), tr.get("xyxy", [])
    if len(frames) != len(boxes) or len(set(frames)) != len(frames):
        return {**base, "status": "invalid_observation"}
    observed = dict(zip(frames, boxes))
    missing = [f for f in planned if observed.get(f) is None]
    if missing:
        return {**base, "status": "missing_observation", "missing_generated_frames": missing,
                "reason": "missing_registered_observation",
                "missing_observation_reasons": {str(f): track.get('reasons', [])[frames.index(f)]
                    if f in frames and frames.index(f) < len(track.get('reasons', [])) else 'missing_frame'
                    for f in missing}}
    if len(planned) < 4:
        return {**base, "status": "few_frames"}
    if any(len(observed[f]) != 4 or not np.isfinite(observed[f]).all() for f in planned):
        return {**base, "status": "invalid_observation"}
    # Match the frozen fitter's existing zero-weight definition. A nonempty
    # residual pixel is not a complete observation of a registered frame.
    unusable = [f for f in planned
                if ((np.asarray(observed[f])[2:] - np.asarray(observed[f])[:2]) < 6).any()
                or np.prod(np.asarray(observed[f])[2:] - np.asarray(observed[f])[:2]) < 36]
    if unusable:
        return {**base, "status": "invalid_observation",
                "unusable_generated_frames": unusable,
                "observation_reason": "tiny_by_original_fitter"}
    scheduled_track = {**track, "tracks": {it["object_name"]: {
        "frames": planned, "xyxy": [observed[f] for f in planned]}}}
    sample = _sample(row, it, scheduled_track, v0, to_first or {})
    assert len(sample["boxes"]["frames"]) == len(planned)
    sample["offset_mode"] = offset_mode
    sample["window"]["contact_check"] = False
    if v0 == "agnostic":
        # A stale direction in an imported manifest must not become a prior.
        sample["motion"].pop("directions", None)
    pred = safe_fit(sample)
    assert pred.get("frames", len(planned)) == len(planned), "Fixed-window fit trimmed scheduled frames"
    return {**base, **pred}


def _binding_failure(row, track):
    """Engineering provenance/clock gate before the unchanged fixed-window fitter."""
    from physedit.runners.media_contract import sha256, validate_row
    from sam31_frontend import lock, FROZEN
    if row.get('input_failure'):
        return row['input_failure']
    if not track:
        return 'missing_observation_record'
    try:
        lock()
        if track.get('frontend') != 'sam31_single_view_frozen_v4':
            raise ValueError('frontend_version_mismatch')
        if track.get('frontend_manifest_sha256') != sha256(FROZEN/'manifest.json'):
            raise ValueError('frontend_manifest_mismatch')
        if track.get('fps') != row['output_fps']:
            raise ValueError('track_manifest_fps_mismatch')
        media = validate_row(row)
        if track.get('video_sha256') != media['video_sha256']:
            raise ValueError('track_video_sha256_mismatch')
        if Path(track.get('video', '')).resolve() != Path(row['generated_video_resized_to_source']).resolve():
            raise ValueError('track_video_path_mismatch')
        details_path = Path(track['measurements_path'])
        if sha256(details_path) != track['measurements_sha256']:
            raise ValueError('measurement_receipt_drift')
        raw_details = _json_rows(details_path)
        details = {d['id']: d for d in raw_details}
        if len(details) != len(raw_details) or track['id'] != row['sample_id']:
            raise ValueError('measurement_identity_mismatch')
        detail = details[row['sample_id']]
        if detail['video_sha256'] != media['video_sha256']:
            raise ValueError('measurement_video_mismatch')
        target_tracks = track.get('tracks', {})
        if len(target_tracks) != 1 or detail['frames'] != next(iter(target_tracks.values()))['frames']:
            raise ValueError('measurement_frame_mismatch')
        reasons = track.get('reasons', [])
        if reasons != detail['statuses']:
            raise ValueError('measurement_status_mismatch')
    except (OSError, ValueError, KeyError, StopIteration, TypeError) as error:
        return str(error)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("items")
    b.add_argument("out")
    b.add_argument("--host-root", required=True)
    b.add_argument("--data-root", default="data/phyediting")
    b.add_argument("--source-root", required=True, help="where the reference videos are on the generation host")
    b.add_argument("--per-gravity", type=int, help="explicit prototype quota; excluded rows remain with reasons")
    b.add_argument("--min-window-frames", type=int, default=8, help="reference frames in the window (8: >= 4 frames at 16 fps)")
    b.add_argument("--max-end-frame", type=int, default=170, help="window end (reference frame) a 5 s clip from frame 23 reaches")
    b.add_argument("--seed", type=int, default=20261008)
    s = sub.add_parser("score")
    s.add_argument("items")
    s.add_argument("rows")
    s.add_argument("tracks")
    s.add_argument("out")
    s.add_argument("--v0", default="agnostic", choices=["declared", "free", "agnostic"],
                   help="agnostic avoids reference-velocity leakage; declared is only a conditional control")
    s.add_argument("--offset-mode", default="anchor", choices=["anchor", "centred"])
    s.add_argument("--shard", default="0/1", help="i/n: score every n-th row starting at i")
    s.add_argument("--camera-motion", help="camera_motion.py output: boxes are mapped into frame 0 before fitting")
    s.add_argument("--scan", action="store_true", help="fit the item's window at every start over the whole clip")
    s.add_argument("--scan-step", type=int, default=2, help="generated frames between scanned window starts")
    m = sub.add_parser("rows")
    m.add_argument("template")
    m.add_argument("out")
    m.add_argument("--model", required=True)
    m.add_argument("--frames", type=int, default=81)
    m.add_argument("--fps", type=float, default=16.0)
    m.add_argument("--out-root", required=True)
    m.add_argument("--canvas", help="generation size WxH, e.g. 832x480")
    t = sub.add_parser("jobs")
    t.add_argument("items")
    t.add_argument("rows")
    t.add_argument("out")
    t.add_argument("--compact", default="data/compact")
    t.add_argument("--host-prefix", default="")
    t.add_argument("--local-prefix", default="")
    args = ap.parse_args()
    {"build": build, "score": score, "rows": model_rows, "jobs": track_jobs}[args.cmd](args)


if __name__ == "__main__":
    main()
