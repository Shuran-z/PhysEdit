"""All 1038 cases, original frames, image-only boundary/observation repair."""
import copy, hashlib, inspect, json, sys, tempfile
from pathlib import Path
import cv2, numpy as np
from track_sam31_identity_center_control import pixel_box
from sam31_rgb_observation_health import initial_background_valid, choose_actual_mask, repair_certified


def main():
    root = Path(sys.argv[1]); cv2.setNumThreads(1)
    protocol = json.loads((root/'sam31_rgb_health_full30_protocol.json').read_text())
    for name, sha in protocol['sources'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest() == sha
    jobs = {j['id']:j for j in map(json.loads, (root/'sam31_rgb_health_full30_jobs.jsonl').read_text().splitlines())}
    assert len(jobs) == 1038 and sum(len(j['frames']) for j in jobs.values()) == 13918
    assert sum(j['frames'][-1]-j['prompt_frame']+1 for j in jobs.values()) == 79687
    tracks = {t['id']:t for t in map(json.loads, (root/'runs/sam31_integrated_full30_tracks.jsonl').read_text().splitlines())}
    instance, semantic, idir, sdir = {}, {}, {}, {}
    for w in (0, 1):
        for t in map(json.loads, (root/f'runs/sam31_identity_full30_w{w}_tracks.jsonl').read_text().splitlines()):
            instance[t['id']] = t; idir[t['id']] = root/f'runs/sam31_identity_full30_w{w}_masks'
        for t in map(json.loads, (root/f'runs/sam31_semantic_books_full30_w{w}_tracks.jsonl').read_text().splitlines()):
            semantic[t['id']] = t; sdir[t['id']] = root/f'runs/sam31_semantic_books_full30_w{w}_masks'
    assert set(jobs) == set(tracks) == set(instance)
    outdir = root/'runs/sam31_rgb_health_full30_masks'; outdir.mkdir(exist_ok=True)
    vis = root/'runs/sam31_rgb_health_full30_actual_rgb'; vis.mkdir(exist_ok=True)
    output = root/'runs/sam31_rgb_health_full30_tracks.jsonl'
    done = {t['id'] for t in map(json.loads, output.read_text().splitlines())} if output.exists() else set()
    assert done <= set(jobs)
    predictor = None

    def model():
        nonlocal predictor
        if predictor is not None: return predictor
        import torch
        sys.path.insert(0, str(root/'sam31_official'))
        from sam3.model_builder import build_sam3_multiplex_video_predictor
        torch.manual_seed(20261010)
        predictor = build_sam3_multiplex_video_predictor(checkpoint_path=str(root/'weights/sam3.1/sam3.1_multiplex.pt'),
            use_fa3=False,use_rope_real=False,compile=False,warm_up=False,async_loading_frames=False)
        old = predictor.model.init_state
        if 'offload_state_to_cpu' not in inspect.signature(old).parameters:
            def compat(*args, offload_state_to_cpu=False, **kwargs):
                assert offload_state_to_cpu is False
                return old(*args, **kwargs)
            predictor.model.init_state = compat
        merge = predictor.model._build_sam2_output
        def merge_compat(state, frame_idx, refined_obj_id_to_mask=None):
            if frame_idx not in state['cached_frame_outputs'] and refined_obj_id_to_mask:
                return refined_obj_id_to_mask.copy()
            return merge(state, frame_idx, refined_obj_id_to_mask)
        predictor.model._build_sam2_output = merge_compat
        state = torch.load(root/'weights/sam3.1/sam3.1_multiplex.pt', map_location='cpu', weights_only=True, mmap=True)
        if 'model' in state: state = state['model']
        params = dict(predictor.model.named_parameters())
        assert all(n in state and p.shape == state[n].shape for n,p in params.items())
        names = sorted(params)
        for n in names[::max(1,len(names)//12)]:
            assert torch.equal(params[n].detach().flatten()[:64].cpu(),state[n].flatten()[:64])
        del state
        print(json.dumps({'checkpoint_parameters_verified':len(params)}),flush=True)
        return predictor

    def loadmask(directory, stem, frame):
        path = directory/f'{stem}_{frame}.npz'
        if not path.exists(): return None
        mask = np.load(path)['mask'].astype(np.uint8)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask,connectivity=8)
        if n <= 1: return None
        return (labels == 1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))).astype(np.uint8)

    def observe_missing(rgb, actual_neighbour, frame, stem):
        """Current RGB instance observation; no positional interpolation.

        Semantic recognition of a tiny cap/page is unreliable. Prompt the
        SAME SAM3.1 instance path with the nearest actual target mask box.
        Adjacent later observations are within the already supplied window.
        """
        box = pixel_box(actual_neighbour)
        if box is None: return None, dict(status='no_actual_neighbour', frame=frame)
        x,y,xx,yy = box; h,w = actual_neighbour.shape
        rx,ry,x1,y1 = max(0,x-32),max(0,y-32),min(w,xx+32),min(h,yy+32)
        up = cv2.resize(rgb[ry:y1,rx:x1],None,fx=8,fy=8,interpolation=cv2.INTER_NEAREST)
        p = model(); sid = None
        try:
            import torch
            with torch.inference_mode(), tempfile.TemporaryDirectory() as tmp:
                assert cv2.imwrite(str(Path(tmp)/'00000.jpg'),up,[cv2.IMWRITE_JPEG_QUALITY,95])
                sid = p.handle_request(dict(type='start_session',resource_path=tmp,offload_video_to_cpu=True))['session_id']
                data = p.handle_request(dict(type='add_prompt',session_id=sid,frame_index=0,obj_id=1,
                    points=[[(x-rx)/(x1-rx),(y-ry)/(y1-ry)],[(xx-rx)/(x1-rx),(yy-ry)/(y1-ry)]],
                    point_labels=[2,3]))['outputs']
                where = np.flatnonzero(np.asarray(data['out_obj_ids']) == 1)
                if not len(where): return None, dict(status='no_current_rgb_instance_mask',frame=frame,neighbour_box=box)
                mask = np.asarray(data['out_binary_masks'])[where[0]].squeeze().astype(bool)
                assert mask.shape == up.shape[:2]
                small = mask.reshape(y1-ry,8,x1-rx,8).sum(axis=(1,3)) >= 32
                full = np.zeros_like(actual_neighbour); full[ry:y1,rx:x1] = small
                bbox = pixel_box(full)
                if bbox is None: return None, dict(status='empty_current_rgb_instance_mask',frame=frame,neighbour_box=box)
                return full, dict(status='current_rgb_instance_crop',frame=frame,neighbour_box=box,box=bbox,roi=[rx,ry,x1,y1],scale=8)
        except Exception as e:
            return None, dict(status='current_rgb_model_exception',frame=frame,exception=type(e).__name__+': '+str(e))
        finally:
            if sid is not None: p.handle_request(dict(type='close_session',session_id=sid))

    try:
        with output.open('a') as writer:
            for id,j in jobs.items():
                if id in done: continue
                t = copy.deepcopy(tracks[id]); stem = hashlib.sha256(id.encode()).hexdigest()[:12]
                assert t['frames'] == j['frames']
                cap = cv2.VideoCapture(j['video']); cap.set(cv2.CAP_PROP_POS_FRAMES,j['prompt_frame'])
                ok, initial = cap.read(); assert ok
                valid_bg = initial_background_valid(initial.shape[:2],j['scene_boxes'])
                images, masks, choices = [], [], []
                for k, f in enumerate(j['frames']):
                    cap.set(cv2.CAP_PROP_POS_FRAMES,f); ok, rgb = cap.read(); assert ok
                    images.append(rgb)
                    raw_i = loadmask(idir[id],stem,f) if instance[id]['boxes'][k] is not None else None
                    if t['initial_routing_reason'] == 'initial_semantic_target_identified':
                        raw_s = loadmask(sdir[id],stem,f) if semantic[id]['boxes'][k] is not None else None
                        primary, z = choose_actual_mask(rgb,initial,valid_bg,raw_s,raw_i)
                    else:
                        primary = raw_i; z = dict(route='original_initial_route')
                    if primary is None and t['boxes'][k] is not None:
                        primary = loadmask(root/'runs/sam31_integrated_full30_crop_masks',stem,f)
                        z['retained_real_crop_measurement'] = primary is not None
                    masks.append(primary); z['frame'] = f; choices.append(z)
                cap.release()
                missing = []
                # Never interpolate boxes or remove a frame. Every recovery
                # invokes the actual current RGB model. Use the nearest real
                # mask in either direction, including at the window start.
                for k, m in enumerate(masks):
                    if m is not None: continue
                    observed = [q for q,z in enumerate(masks) if z is not None]
                    if not observed:
                        missing.append(dict(frame=j['frames'][k],status='no_actual_observed_neighbour'));continue
                    q = min(observed,key=lambda q:(abs(q-k),q))
                    m, z = observe_missing(images[k],masks[q],j['frames'][k],stem)
                    z['neighbour_actual_frame'] = j['frames'][q]; missing.append(z); masks[k] = m
                indices = [k for k,m in enumerate(masks) if m is not None]
                if len(indices) >= 4:
                    fixed, audit = repair_certified([images[k] for k in indices],[masks[k] for k in indices],initial,valid_bg)
                else: fixed, audit = [masks[k] for k in indices], []
                boxes = [None]*len(masks)
                for index,m in zip(indices,fixed):
                    path = outdir/f'{stem}_{j["frames"][index]}.npz'; np.savez_compressed(path,mask=m)
                    boxes[index] = pixel_box(m)
                    if j.get('review_actual_rgb'):
                        im = images[index].copy(); contours,_ = cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                        cv2.drawContours(im,contours,-1,(0,255,0),1)
                        b = boxes[index]
                        if b:
                            x,y,xx,yy=b;im=im[max(0,y-20):min(im.shape[0],yy+20),max(0,x-20):min(im.shape[1],xx+20)]
                            im=cv2.resize(im,None,fx=4,fy=4,interpolation=cv2.INTER_NEAREST)
                        cv2.imwrite(str(vis/f'{stem}_{j["frames"][index]}.png'),im)
                t['boxes'] = boxes; t['reasons'] = ['sam31_rgb_health_actual_mask' if b else 'missing_model_prediction' for b in boxes]
                t['box_mode'] = 'prefix_rgb_health_component_pixel'
                t['rgb_health_choices'] = choices; t['rgb_health_recovery'] = missing; t['rgb_health_cleanup'] = audit
                t['rgb_health_runner_sha256'] = protocol['sources'][Path(__file__).name]
                assert len(boxes) == len(j['frames']) and all(b is None or all(isinstance(v,int) for v in b) for b in boxes)
                writer.write(json.dumps(t)+'\n');writer.flush();done.add(id)
                print(json.dumps(dict(id=id,done=len(done),frames=len(boxes),missing=sum(b is None for b in boxes),image_route_changes=sum(z['route']=='alternate_rgb_agreement' for z in choices),recovery=missing)),flush=True)
    finally:
        if predictor is not None: predictor.shutdown()


if __name__ == '__main__': main()
