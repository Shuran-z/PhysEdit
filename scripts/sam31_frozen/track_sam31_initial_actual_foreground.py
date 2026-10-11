"""Official SAM3.1 semantic book grounding, fixed seed identity, exact prefix/evaluation frames.
No later-reference prompts, subpixel correction, fitting changes or frame exclusions.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path


def pixel_box(mask):
    import cv2
    import numpy as np
    n,labels,stats,centroids=cv2.connectedComponentsWithStats(mask.astype(np.uint8),connectivity=8)
    if n<=1:return None
    i=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
    x,y,w,h=map(int,stats[i,:4])
    return [x,y,x+w,y+h]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('jobs'); ap.add_argument('out')
    ap.add_argument('--sam3', required=True); ap.add_argument('--checkpoint', required=True)
    ap.add_argument('--visual-dir'); ap.add_argument('--mask-dir')
    a = ap.parse_args()
    assert Path(a.checkpoint).is_file(), 'Official SAM3.1 checkpoint must exist locally'
    sys.path.insert(0, a.sam3)
    import cv2
    import numpy as np
    import torch
    from sam3.model_builder import build_sam3_multiplex_video_predictor
    cv2.setNumThreads(1); torch.manual_seed(20261010)
    predictor = build_sam3_multiplex_video_predictor(
        checkpoint_path=a.checkpoint, use_fa3=False, use_rope_real=False,
        compile=False, warm_up=False, async_loading_frames=False)
    # Current official shared session wrapper passes this SAM3-only option to
    # multiplex init_state. Drop only its unsupported, false default.
    import inspect
    original_init = predictor.model.init_state
    if 'offload_state_to_cpu' not in inspect.signature(original_init).parameters:
        def init_compat(*args, offload_state_to_cpu=False, **kwargs):
            assert offload_state_to_cpu is False
            return original_init(*args, **kwargs)
        predictor.model.init_state = init_compat
    # The builder's intermediate tracker load prints misleading warnings for a
    # merged checkpoint; verify the fully assembled model before inference.
    checkpoint = torch.load(a.checkpoint, map_location='cpu', weights_only=True, mmap=True)
    if 'model' in checkpoint: checkpoint = checkpoint['model']
    parameters = dict(predictor.model.named_parameters())
    missing = [n for n in parameters if n not in checkpoint]
    assert not missing, 'Unloaded model parameters: '+str(missing[:10])
    assert all(p.shape == checkpoint[n].shape for n,p in parameters.items())
    names = sorted(parameters)
    probes = names[::max(1,len(names)//12)]
    for name in probes:
        assert torch.equal(parameters[name].detach().flatten()[:64].cpu(),
                           checkpoint[name].flatten()[:64]), name
    print(json.dumps({'checkpoint_parameter_coverage':'all',
                      'parameters':len(names),'value_probes':len(probes)}),flush=True)
    del checkpoint
    # The official refinement merge drops already computed tracker masks on
    # uncached frames (early return before merging refined_obj_id_to_mask).
    # Preserve those raw masks; no neural prediction/threshold changes.
    original_merge = predictor.model._build_sam2_output
    merge_counts = {'recovered_frames': 0}
    def merge_compat(state, frame_idx, refined_obj_id_to_mask=None):
        if frame_idx not in state['cached_frame_outputs'] and refined_obj_id_to_mask:
            merge_counts['recovered_frames'] += 1
            return refined_obj_id_to_mask.copy()
        return original_merge(state, frame_idx, refined_obj_id_to_mask)
    predictor.model._build_sam2_output = merge_compat
    done = {r['id'] for r in map(json.loads, open(a.out))} if Path(a.out).exists() else set()
    visual = Path(a.visual_dir) if a.visual_dir else None
    if visual: visual.mkdir(parents=True, exist_ok=True)
    try:
        with open(a.out, 'a') as out, torch.inference_mode():
            for j in map(json.loads, open(a.jobs)):
                if j['id'] in done: continue
                merge_counts['recovered_frames'] = 0
                frames = j['frames']; assert frames == sorted(set(frames))
                tracking_frames=list(range(j['prompt_frame'],frames[-1]+1))
                selected_indices={f:k for k,f in enumerate(frames)}
                assert len(frames) == len(j['boxes']) and len(frames) > 0
                rec = dict(id=j['id'], frames=frames, boxes=[None]*len(frames),
                           reasons=['missing_model_prediction']*len(frames),
                           model='facebook/sam3.1', box_mode='prefix_initial_actual_foreground_component_pixel',
                           prompt_mode='official_semantic_book_and_initial_box')
                rec['tracking_frames']=tracking_frames;rec['prompt_frame']=j['prompt_frame'];rec['semantic_point_prompts']=j['semantic_point_prompts']
                sid = None
                with tempfile.TemporaryDirectory() as tmp:
                    cap = cv2.VideoCapture(j['video']); images = []
                    cap.set(cv2.CAP_PROP_POS_FRAMES, tracking_frames[0])
                    for k, f in enumerate(tracking_frames):
                        ok, img = cap.read()
                        if not ok: break
                        images.append(img)
                        assert cv2.imwrite(str(Path(tmp)/f'{k:05d}.jpg'), img,
                                           [cv2.IMWRITE_JPEG_QUALITY, 95])
                    cap.release()
                    if len(images) != len(tracking_frames):
                        rec['reasons'] = ['video_read_failure']*len(frames)
                    else:
                        try:
                            h, w = images[0].shape[:2]; x0,y0,x1,y1 = j['initial_box']
                            sid = predictor.handle_request(dict(type='start_session',
                                resource_path=tmp, offload_video_to_cpu=True))['session_id']
                            seed = predictor.handle_request(dict(type='add_prompt',
                                session_id=sid, frame_index=0, text=j['semantic_text'],
                                bounding_boxes=[[x0/w,y0/h,(x1-x0)/w,(y1-y0)/h]],
                                bounding_box_labels=[1]))
                            # Select identity from the initial RGB masks only. Never
                            # use later reference boxes, trajectory, v0 or gravity.
                            candidates=[]
                            seed_data=seed['outputs']
                            for oi,oid in enumerate(np.asarray(seed_data['out_obj_ids'])):
                                mask=np.asarray(seed_data['out_binary_masks'])[oi].squeeze().astype(bool)
                                pos=[bool(mask[q['xy'][1],q['xy'][0]]) for q in j['semantic_point_prompts'] if q['label']==1]
                                neg=[bool(mask[q['xy'][1],q['xy'][0]]) for q in j['semantic_point_prompts'] if q['label']==0]
                                if a.mask_dir:
                                    mp=Path(a.mask_dir);mp.mkdir(parents=True,exist_ok=True)
                                    stem=hashlib.sha256(j['id'].encode()).hexdigest()[:12]
                                    np.savez_compressed(str(mp/f'{stem}_seed_candidate_{int(oid)}.npz'),mask=mask)
                                if visual:
                                    seed_rgb=images[0].copy()
                                    contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                                    cv2.drawContours(seed_rgb,contours,-1,(0,255,0),1)
                                    for q in j['semantic_point_prompts']:cv2.circle(seed_rgb,tuple(q['xy']),2,(255,0,0) if q['label']==1 else (0,0,255),-1)
                                    stem=hashlib.sha256(j['id'].encode()).hexdigest()[:12]
                                    cv2.imwrite(str(visual/f'{stem}_seed_candidate_{int(oid)}.jpg'),seed_rgb)
                                bbox=pixel_box(mask)
                                if bbox is None:continue
                                xa,ya,xb,yb=bbox
                                inter=max(0,min(xb,x1)-max(xa,x0))*max(0,min(yb,y1)-max(ya,y0))
                                union=(xb-xa)*(yb-ya)+(x1-x0)*(y1-y0)-inter
                                candidates.append(dict(obj_id=int(oid),positive_membership=pos,
                                    negative_membership=neg,initial_box_iou=inter/union if union else 0.,area=int(mask.sum())))
                            rec['initial_candidates']=candidates
                            valid=[z for z in candidates if z['positive_membership'] and all(z['positive_membership']) and not any(z['negative_membership'])]
                            if not valid:
                                # The declared rectangle can have a background
                                # corner. Recover identity from a unique initial
                                # *actual* semantic mask, never later motion.
                                by_id={int(oid):np.asarray(seed_data['out_binary_masks'])[oi].squeeze().astype(np.uint8)
                                    for oi,oid in enumerate(np.asarray(seed_data['out_obj_ids']))}
                                exclusive=np.zeros((h,w),dtype=np.uint8)
                                exclusive[max(0,int(np.ceil(y0))):min(h,int(np.floor(y1))),
                                    max(0,int(np.ceil(x0))):min(w,int(np.floor(x1)))]=1
                                for name,bb in j['scene_boxes'].items():
                                    if name==j['target_name']:continue
                                    ax,ay,bx,by=bb
                                    exclusive[max(0,int(np.floor(ay))):min(h,int(np.ceil(by))),
                                        max(0,int(np.floor(ax))):min(w,int(np.ceil(bx)))]=0
                                grounded=[]
                                for candidate in candidates:
                                    if any(candidate['negative_membership']) or candidate['initial_box_iou']<.5:continue
                                    actual=by_id[candidate['obj_id']]
                                    visible=actual&exclusive
                                    if not visible.any():continue
                                    bb=pixel_box(actual);xa,ya,xb,yb=bb
                                    scene_ious=[]
                                    for name,(ax,ay,bx,by) in j['scene_boxes'].items():
                                        inter=max(0,min(xb,bx)-max(xa,ax))*max(0,min(yb,by)-max(ya,ay))
                                        union=(xb-xa)*(yb-ya)+(bx-ax)*(by-ay)-inter
                                        scene_ious.append((inter/union if union else 0.,name))
                                    if max(scene_ious)[1]!=j['target_name']:continue
                                    distance=cv2.distanceTransform(visible,cv2.DIST_L2,3)
                                    py,px=np.unravel_index(int(np.argmax(distance)),distance.shape)
                                    candidate['initial_actual_interior_point']=[int(px),int(py)]
                                    candidate['exclusive_initial_foreground_pixels']=int(visible.sum())
                                    grounded.append(candidate)
                                # Multiple plausible targets remain ambiguous;
                                # no best-error or future-reference selection.
                                if len(grounded)==1:
                                    valid=grounded
                                    rec['initial_identity_repair']='unique_initial_semantic_foreground_matches_declared_target_box'
                            assert valid, 'No unambiguous initial target identity from actual masks'
                            selected=max(valid,key=lambda z:(z['initial_box_iou'],-z['obj_id']))
                            target_id=selected['obj_id'];rec['selected_initial_obj_id']=target_id
                            rec['semantic_text']=j['semantic_text']
                            def record(response):
                                context_index=int(response['frame_index'])
                                actual_frame=tracking_frames[context_index]
                                if actual_frame not in selected_indices:return
                                k=selected_indices[actual_frame];data=response['outputs']
                                ids = np.asarray(data['out_obj_ids'])
                                where = np.flatnonzero(ids == target_id)
                                if not len(where): return
                                mask = np.asarray(data['out_binary_masks'])[where[0]].squeeze()
                                assert mask.shape == (h,w)
                                if a.mask_dir:
                                    mp=Path(a.mask_dir);mp.mkdir(parents=True,exist_ok=True)
                                    stem=hashlib.sha256(j['id'].encode()).hexdigest()[:12]
                                    np.savez_compressed(str(mp/f'{stem}_{frames[k]}.npz'),mask=mask)
                                b = pixel_box(mask)
                                rec['boxes'][k] = b
                                rec['reasons'][k] = 'sam31_raw_mask' if b else 'empty_model_mask'
                                if visual:
                                    img = images[context_index].copy()
                                    contours,_ = cv2.findContours(mask.astype(np.uint8),
                                        cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                                    cv2.drawContours(img,contours,-1,(0,255,0),1)
                                    if b is not None:
                                        cv2.rectangle(img, tuple(map(int,b[:2])),
                                            tuple(map(int,b[2:])), (0,0,255),1)
                                    stem = hashlib.sha256(j['id'].encode()).hexdigest()[:12]
                                    cv2.imwrite(str(visual/f'{stem}_{frames[k]}.jpg'),img)
                            if a.mask_dir:
                                seed_ids=np.asarray(seed['outputs']['out_obj_ids']);seed_where=np.flatnonzero(seed_ids==target_id)
                                if len(seed_where):
                                    sm=np.asarray(seed['outputs']['out_binary_masks'])[seed_where[0]].squeeze()
                                    sp=Path(a.mask_dir);sp.mkdir(parents=True,exist_ok=True)
                                    stem=hashlib.sha256(j['id'].encode()).hexdigest()[:12]
                                    np.savez_compressed(str(sp/f'{stem}_{j["prompt_frame"]}_seed.npz'),mask=sm)
                                    if visual:
                                        im=images[0].copy();contours,_=cv2.findContours(sm.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                                        cv2.drawContours(im,contours,-1,(0,255,0),1)
                                        for q in j['semantic_point_prompts']:cv2.circle(im,tuple(q['xy']),2,(255,0,0) if q['label']==1 else (0,0,255),-1)
                                        cv2.imwrite(str(visual/f'{stem}_seed.jpg'),im)
                            record(seed)
                            for response in predictor.handle_stream_request(dict(
                                type='propagate_in_video',session_id=sid,
                                propagation_direction='forward',start_frame_index=0,
                                max_frame_num_to_track=len(tracking_frames))):
                                record(response)
                        except Exception as e:
                            rec['exception'] = type(e).__name__ + ': ' + str(e)
                            rec['reasons'] = [('model_exception' if b is None else r)
                                for b,r in zip(rec['boxes'],rec['reasons'])]
                        finally:
                            if sid is not None:
                                predictor.handle_request(dict(type='close_session',session_id=sid))
                rec['api_cache_merge_recovered_frames'] = merge_counts['recovered_frames']
                out.write(json.dumps(rec)+'\n'); out.flush(); done.add(j['id'])
                print(json.dumps({'id':j['id'],'frames':len(frames),
                    'measured':sum(b is not None for b in rec['boxes']),
                    'exception':rec.get('exception')}),flush=True)
    finally:
        predictor.shutdown()


if __name__ == '__main__': main()
