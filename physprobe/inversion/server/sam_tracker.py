"""SAM 3.1 lean tracker (2026-10-24): one forward pass per VIDEO, every object of the scene prompted jointly.
Same model, checkpoint and prompt form as the identity tracker of PhysEdit's frozen SAM 3.1 frontend (facebook/sam3.1 multiplex predictor,
box given as its two corners with SAM labels 2/3 at the prompt frame, box = largest connected component of the raw mask,
the frontend's two compatibility shims that change no neural output), but instead of ~8 passes per object (identity x2, semantic,
foreground x4, integrated, RGB health, certification) all objects share one session and one propagation, so each object
keeps its own mask and identity swaps between neighbours are suppressed by construction.
Job (one line per video): {"id": VIDEO_ID, "video": PATH, "prompt_frame": K, "last_frame": optional,
                           "objects": {NAME: [x0, y0, x1, y1] in video pixels at the prompt frame}}
Output (one line per object, the frontend's track format): {"id": "VIDEO_ID__NAME", "video": ..., "tracks": {NAME: {"frames": [...],
"xyxy": [... or null], "area": [...]}}, "model": "facebook/sam3.1", "mode": "lean_joint_box_prompt", "seconds": ...}
Usage: python sam_tracker.py JOBS OUT --sam3 SRC --checkpoint PT [--shard I/N] [--tmp /dev/shm]
Resident mode (2026-11-04, event-prompt round): python sam_tracker.py --watch INBOX --worker NAME --sam3 SRC --checkpoint PT
  loads the model once and keeps tracking: every batch folder INBOX/<batch>/ with READY and without TRACKED is worked on video by video
  (a video is claimed with mkdir <batch>/claims/<video id>, so several resident processes share a batch), each video's rows go to
  <batch>/tracks/<video id>.jsonl; the process that finishes a batch's last video writes tracks_lean.jsonl (jobs order), tracker_info.json
  and TRACKED. Stops when INBOX/../stop_<host12> exists. The per-video tracking is the same code as the one-shot mode."""
import argparse, inspect, json, os, shutil, sys, tempfile, time
from pathlib import Path


def pixel_box(mask):
    import cv2, numpy as np
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if n <= 1: return None, 0
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = map(int, stats[i, :4])
    return [x, y, x + w, y + h], int(stats[i, cv2.CC_STAT_AREA])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('jobs', nargs='?'); ap.add_argument('out', nargs='?')
    ap.add_argument('--watch', help='resident mode: inbox of batch folders'); ap.add_argument('--worker', default='w0')
    ap.add_argument('--direct', action='store_true', help='resident mode on a host that mounts the shared storage: take TRACK_REQUEST batches, write ROUTED')
    ap.add_argument('--sam3', required=True); ap.add_argument('--checkpoint', required=True)
    ap.add_argument('--shard', default='0/1'); ap.add_argument('--tmp', default='/dev/shm' if os.path.isdir('/dev/shm') else None)
    a = ap.parse_args()
    si, sn = map(int, a.shard.split('/'))
    sys.path.insert(0, a.sam3)
    import cv2, numpy as np, torch
    from sam3.model_builder import build_sam3_multiplex_video_predictor
    cv2.setNumThreads(1); torch.manual_seed(20261010)
    predictor = build_sam3_multiplex_video_predictor(checkpoint_path=a.checkpoint, use_fa3=False, use_rope_real=False,
                                                     compile=False, warm_up=False, async_loading_frames=False)
    original_init = predictor.model.init_state            # compatibility shim 1: unsupported false-default option
    if 'offload_state_to_cpu' not in inspect.signature(original_init).parameters:
        def init_compat(*x, offload_state_to_cpu=False, **k):
            assert offload_state_to_cpu is False
            return original_init(*x, **k)
        predictor.model.init_state = init_compat
    original_merge = predictor.model._build_sam2_output   # compatibility shim 2: keep tracker masks the refinement merge drops
    def merge_compat(state, frame_idx, refined_obj_id_to_mask=None):
        if frame_idx not in state['cached_frame_outputs'] and refined_obj_id_to_mask: return refined_obj_id_to_mask.copy()
        return original_merge(state, frame_idx, refined_obj_id_to_mask)
    predictor.model._build_sam2_output = merge_compat
    def track(j, out):
        t0 = time.time(); names = list(j['objects']); sid = None; err = None
        cap = cv2.VideoCapture(j['video']); nfr = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        last = min(nfr - 1, j.get('last_frame', nfr - 1)); frames = list(range(j['prompt_frame'], last + 1))
        rec = {n: dict(frames=frames, xyxy=[None] * len(frames), area=[0] * len(frames)) for n in names}
        tmp = tempfile.mkdtemp(dir=a.tmp)
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frames[0]); h = w = None
            for k in range(len(frames)):
                ok, img = cap.read()
                if not ok: frames = frames[:k]; break
                h, w = img.shape[:2]
                cv2.imwrite(os.path.join(tmp, f'{k:05d}.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            cap.release()
            for n in names: rec[n] = dict(frames=frames, xyxy=[None] * len(frames), area=[0] * len(frames))
            sid = predictor.handle_request(dict(type='start_session', resource_path=tmp, offload_video_to_cpu=True))['session_id']
            ids = {}
            for i, n in enumerate(names, 1):
                x0, y0, x1, y1 = j['objects'][n]; ids[i] = n
                seed = predictor.handle_request(dict(type='add_prompt', session_id=sid, frame_index=0, obj_id=i,
                                                     points=[[x0 / w, y0 / h], [x1 / w, y1 / h]], point_labels=[2, 3]))
            def record(resp):
                k = int(resp['frame_index'])
                if k >= len(frames): return
                oid = np.asarray(resp['outputs']['out_obj_ids']); masks = np.asarray(resp['outputs']['out_binary_masks'])
                for t, i in enumerate(oid):
                    n = ids.get(int(i))
                    if n is None: continue
                    b, ar = pixel_box(masks[t].squeeze())
                    rec[n]['xyxy'][k] = b; rec[n]['area'][k] = ar
            record(seed)
            for resp in predictor.handle_stream_request(dict(type='propagate_in_video', session_id=sid, propagation_direction='forward',
                                                             start_frame_index=0, max_frame_num_to_track=len(frames),
                                                             force_tracker_propagation=True)):
                record(resp)
        except Exception as e:
            err = f'{type(e).__name__}: {str(e)[:300]}'
        finally:
            if sid is not None: predictor.handle_request(dict(type='close_session', session_id=sid))
            shutil.rmtree(tmp, ignore_errors=True)
        dt = round(time.time() - t0, 1)
        for n in names:
            out.write(json.dumps(dict(id=f"{j['id']}__{n}", video=j['video'], prompt_frame=j['prompt_frame'], tracks={n: rec[n]},
                                      model='facebook/sam3.1', mode='lean_joint_box_prompt', seconds=dt, exception=err)) + '\n')
        out.flush()
        print(json.dumps(dict(id=j['id'], objects=len(names), frames=len(frames), seconds=dt, exception=err)), flush=True)
        return err

    try:
        if a.watch:
            with torch.inference_mode(): watch(a, track)
        else:
            done = set()
            if Path(a.out).exists():
                for r in map(json.loads, open(a.out)): done.add(r['id'].split('__', 1)[0])
            jobs = [j for k, j in enumerate(map(json.loads, open(a.jobs))) if k % sn == si and j['id'] not in done]
            with open(a.out, 'a') as out, torch.inference_mode():
                for j in jobs: track(j, out)
    finally:
        predictor.shutdown()


def slot_ok(inbox, worker):
    """gpu_slots.py (review session 2026-11-05): this worker's slot on its GPU (EVP_SLOT, else the worker number // EVP_NGPU) must be
    below the slots allowed now; no state file = no limit"""
    import socket
    g = os.environ.get('CUDA_VISIBLE_DEVICES', ''); f = inbox.parent / f"slots_{socket.gethostname()[:12]}_{g}.json"
    if not g or not f.exists(): return True
    n = worker.rsplit('.', 1)[-1]
    slot = int(os.environ['EVP_SLOT']) if os.environ.get('EVP_SLOT') else (int(n) // int(os.environ.get('EVP_NGPU', '1')) if n.isdigit() else 0)
    try: return slot < int(json.load(open(f))['slots'])
    except (OSError, ValueError, KeyError): return True


def claim(c):
    """mkdir claim; a claim left by a dead process on this host (or older than 3 h on any host) is taken over"""
    import socket
    me = f'{socket.gethostname()} {os.getpid()}'
    try:
        c.mkdir(); (c / 'owner').write_text(me); return True
    except FileExistsError:
        pass
    try:
        host, pid = (c / 'owner').read_text().split()
    except (OSError, ValueError):
        return False
    dead = host == socket.gethostname() and not os.path.exists(f'/proc/{pid}')
    if not dead and time.time() - c.stat().st_mtime < 3 * 3600: return False
    (c / 'owner').write_text(me); return True


def torch_empty_cache():
    import torch
    torch.cuda.empty_cache()


def watch(a, track):
    import socket, subprocess
    inbox = Path(a.watch); stop = inbox.parent / f"stop_{socket.gethostname()[:12]}"
    while not stop.exists():
        worked = False
        for b in sorted(inbox.glob('evp_b*')):
            if not (b / ('TRACK_REQUEST' if a.direct else 'READY')).exists() or (b / 'TRACKED').exists(): continue
            if a.direct:   # a batch the relay already sent elsewhere is not taken; the first direct taker writes ROUTED
                r = b / 'ROUTED'
                if r.exists() and not r.read_text().endswith(' direct\n'): continue
                if not r.exists(): r.write_text(f'{socket.gethostname()[:12]} direct\n')
            jobs = [json.loads(l) for l in open(b / 'jobs.jsonl') if l.strip()]
            (b / 'claims').mkdir(exist_ok=True); (b / 'tracks').mkdir(exist_ok=True)
            if not (b / 'tracker_start').exists(): (b / 'tracker_start').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
            for j in jobs:
                c = b / 'claims' / j['id']
                if (b / 'tracks' / f"{j['id']}.jsonl").exists(): continue
                if not slot_ok(inbox, a.worker): break   # fewer trackers on a GPU that other users share (gpu_slots.py), only between videos
                if not claim(c): continue
                part = b / 'tracks' / f"{j['id']}.jsonl.part"
                t0 = time.time()
                with open(part, 'w') as out: err = track(j, out)
                worked = True
                if err:   # e.g. CUDA out of memory mid-propagation: the rows after the failure are empty, so the video is not accepted
                    n = len(list((b / 'tracks').glob(f"{j['id']}.failed*")))
                    part.replace(b / 'tracks' / f"{j['id']}.failed{n}")
                    with open(b / f'lean_s_{a.worker}.log', 'a') as lg: lg.write(f"{j['id']} FAILED ({err[:80]}) {socket.gethostname()[:12]}\n")
                    if n < 2: shutil.rmtree(c)   # retried (by any process); after 3 failures the claim stays and the batch is never TRACKED
                    torch_empty_cache(); time.sleep(30); continue
                part.replace(b / 'tracks' / f"{j['id']}.jsonl")
                with open(b / f'lean_s_{a.worker}.log', 'a') as lg: lg.write(f"{j['id']} {time.time() - t0:.1f}s {socket.gethostname()[:12]}\n")
            if all((b / 'tracks' / f"{j['id']}.jsonl").exists() for j in jobs):
                try: (b / 'finalize').mkdir()
                except FileExistsError: continue
                with open(b / 'tracks_lean.jsonl', 'w') as o:
                    for j in jobs: o.write(open(b / 'tracks' / f"{j['id']}.jsonl").read())
                gpus = os.environ.get('CUDA_VISIBLE_DEVICES', '')
                names = subprocess.run(['nvidia-smi', '--query-gpu=index,name', '--format=csv,noheader', '-i', gpus], stdout=subprocess.PIPE,
                                       universal_newlines=True).stdout.strip().splitlines() if gpus else []
                json.dump(dict(host=socket.gethostname(), stack=os.environ.get('EVP_STACK', ''), mode='resident', worker=a.worker, gpus=gpus, start=(b / 'tracker_start').read_text(),
                               end=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), gpu_names=names), open(b / 'tracker_info.json', 'w'), indent=1)
                (b / 'TRACKED').write_text(time.strftime('%c') + '\n'); print(f'{b.name} tracked ({len(jobs)} videos)', flush=True)
        if not worked: time.sleep(20)


if __name__ == '__main__': main()
