"""Frozen image-only SAM3.1 repair on the exact 1038-case denominator.

Select semantic versus prompted-instance by initial grounding and actual empty-track failure only.
Recover missing book fragments from current RGB and the immediately preceding
actual SAM mask, then apply identical colour cleanup to every valid window.
This program never reads a target gravity, physical trajectory or fitted value.
"""
import argparse
import copy
import hashlib
import inspect
import json
import sys
import tempfile
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    args = ap.parse_args()
    root = Path(args.root)
    import cv2
    import numpy as np
    from repair_sam31_static_attachment import repair
    from track_sam31_whole_book_control import pixel_box
    cv2.setNumThreads(1)
    protocol = json.loads((root/'sam31_integrated_full30_protocol.json').read_text())
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == protocol['runner_sha256']
    assert hashlib.sha256((root/'repair_sam31_static_attachment.py').read_bytes()).hexdigest() == protocol['rgb_policy_sha256']
    jobs = {}; instance = {}; semantic = {}; instance_dirs = {}; semantic_dirs = {}
    for w in (0, 1):
        js = list(map(json.loads, (root/f'sam31_identity_full30_w{w}_jobs.jsonl').read_text().splitlines()))
        ts = list(map(json.loads, (root/f'runs/sam31_identity_full30_w{w}_tracks.jsonl').read_text().splitlines()))
        assert len(js) == len(ts) == 519 and {j['id'] for j in js} == {t['id'] for t in ts}
        for original_job in js:
            # Remove even dormant per-frame oracle boxes from repair inputs.
            # Only identifiers, exact frame numbers and declared initial
            # identity/class information are needed by this image-only pass.
            j={k:original_job[k] for k in ['id','video','frames','prompt_frame','semantic_point_prompts','target_name']}
            jobs[j['id']] = j
            instance_dirs[j['id']] = root/f'runs/sam31_identity_full30_w{w}_masks'
        instance.update({t['id']:t for t in ts})
        sj = list(map(json.loads, (root/f'sam31_semantic_books_full30_w{w}_jobs.jsonl').read_text().splitlines()))
        st = list(map(json.loads, (root/f'runs/sam31_semantic_books_full30_w{w}_tracks.jsonl').read_text().splitlines()))
        assert len(sj) == len(st) and {j['id'] for j in sj} == {t['id'] for t in st}
        semantic.update({t['id']:t for t in st})
        for j in sj: semantic_dirs[j['id']] = root/f'runs/sam31_semantic_books_full30_w{w}_masks'
    assert len(jobs) == len(instance) == 1038 and len(semantic) == 365
    assert set(semantic) == {id for id,j in jobs.items() if 'book' in j['target_name']}
    assert sum(len(j['frames']) for j in jobs.values()) == 13918
    assert sum(j['frames'][-1]-j['prompt_frame']+1 for j in jobs.values()) == 79687
    out = root/'runs/sam31_integrated_full30_tracks.jsonl'
    mask_out = root/'runs/sam31_integrated_full30_masks'; mask_out.mkdir(exist_ok=True)
    crop_out = root/'runs/sam31_integrated_full30_crop_masks'; crop_out.mkdir(exist_ok=True)
    audit_out = root/'runs/sam31_integrated_full30_audit.jsonl'
    done = {}
    if out.exists():
        for t in map(json.loads, out.read_text().splitlines()):
            assert t['integrated_runner_sha256'] == protocol['runner_sha256']
            assert t['rgb_policy_sha256'] == protocol['rgb_policy_sha256']
            assert t['id'] not in done
            done[t['id']] = t
        assert set(done) <= set(jobs)
    predictor = None

    def model():
        nonlocal predictor
        if predictor is not None: return predictor
        import torch
        sys.path.insert(0, str(root/'sam31_official'))
        from sam3.model_builder import build_sam3_multiplex_video_predictor
        torch.manual_seed(20261010)
        predictor = build_sam3_multiplex_video_predictor(
            checkpoint_path=str(root/'weights/sam3.1/sam3.1_multiplex.pt'),
            use_fa3=False,use_rope_real=False,compile=False,warm_up=False,
            async_loading_frames=False)
        old = predictor.model.init_state
        if 'offload_state_to_cpu' not in inspect.signature(old).parameters:
            def init_compat(*a, offload_state_to_cpu=False, **kw):
                assert offload_state_to_cpu is False
                return old(*a, **kw)
            predictor.model.init_state = init_compat
        state = torch.load(root/'weights/sam3.1/sam3.1_multiplex.pt',
                           map_location='cpu',weights_only=True,mmap=True)
        if 'model' in state: state = state['model']
        ps = dict(predictor.model.named_parameters())
        assert all(n in state and p.shape == state[n].shape for n,p in ps.items())
        names = sorted(ps)
        for n in names[::max(1,len(names)//12)]:
            assert torch.equal(ps[n].detach().flatten()[:64].cpu(),state[n].flatten()[:64]), n
        del state
        print(json.dumps({'checkpoint_parameter_coverage':'all','parameters':len(names)}),flush=True)
        return predictor

    def recover(rgb, prior, id, frame):
        # This is an additional real neural observation of the CURRENT frame.
        # It does not extrapolate or interpolate any physical/image position.
        b = pixel_box(prior)
        if b is None: return None, {'status':'no_previous_actual_mask'}
        h,w = prior.shape; x,y,x1,y1 = b
        rx=max(0,x-32); ry=max(0,y-32); rx1=min(w,x1+32); ry1=min(h,y1+32)
        up=cv2.resize(rgb[ry:ry1,rx:rx1],None,fx=8,fy=8,interpolation=cv2.INTER_NEAREST)
        p = model(); sid = None; candidates = []; masks = []
        import torch
        try:
            with torch.inference_mode(), tempfile.TemporaryDirectory() as tmp:
                assert cv2.imwrite(str(Path(tmp)/'00000.jpg'),up,[cv2.IMWRITE_JPEG_QUALITY,95])
                sid=p.handle_request(dict(type='start_session',resource_path=tmp,offload_video_to_cpu=True))['session_id']
                result=p.handle_request(dict(type='add_prompt',session_id=sid,frame_index=0,text='book',
                    bounding_boxes=[[(x-rx)/(rx1-rx),(y-ry)/(ry1-ry),(x1-x)/(rx1-rx),(y1-y)/(ry1-ry)]],
                    bounding_box_labels=[1]))['outputs']
                for k,oid in enumerate(np.asarray(result['out_obj_ids'])):
                    m=np.asarray(result['out_binary_masks'])[k].squeeze().astype(bool)
                    assert m.shape == up.shape[:2]
                    small=m.reshape(ry1-ry,8,rx1-rx,8).sum(axis=(1,3))>=32
                    full=np.zeros_like(prior,dtype=np.uint8);full[ry:ry1,rx:rx1]=small
                    bbox=pixel_box(full)
                    if bbox is None: continue
                    xa,ya,xb,yb=bbox
                    inter=max(0,min(xb,x1)-max(xa,x))*max(0,min(yb,y1)-max(ya,y))
                    union=(xb-xa)*(yb-ya)+(x1-x)*(y1-y)-inter
                    iou=inter/union if union else 0.
                    candidates.append(dict(obj_id=int(oid),box=bbox,previous_observed_box_iou=iou))
                    if iou>0: masks.append((iou,-int(oid),full))
                if not masks:
                    return None,dict(status='no_overlapping_model_candidate',candidates=candidates,roi=[rx,ry,rx1,ry1])
                _,_,selected=max(masks,key=lambda z:(z[0],z[1]))
                stem=hashlib.sha256(id.encode()).hexdigest()[:12]
                path=crop_out/f'{stem}_{frame}.npz';np.savez_compressed(path,mask=selected)
                return selected,dict(status='current_rgb_crop_prediction',candidates=candidates,
                    previous_observed_box=b,roi=[rx,ry,rx1,ry1],scale=8,mask_file=str(path))
        except Exception as e:
            return None,dict(status='crop_model_exception',exception=type(e).__name__+': '+str(e))
        finally:
            if sid is not None: p.handle_request(dict(type='close_session',session_id=sid))

    try:
        with out.open('a') as writer, audit_out.open('a') as aw:
            for id,j in jobs.items():
                if id in done: continue
                t=copy.deepcopy(instance[id]); source_dir=instance_dirs[id]
                route='declared_non_book_prompted_instance'
                s=semantic.get(id)
                if s is not None:
                    if 'selected_initial_obj_id' in s and not s.get('exception') and all(b is None for b in s['boxes']):
                        # An initially grounded semantic identity can disappear
                        # during the long static RGB prefix. No actual requested
                        # mask exists; retain the independently seeded SAME
                        # SAM3.1 instance measurements, never switch to a newly
                        # detected ID or inspect a gravity estimate.
                        route='semantic_entire_requested_track_absent_use_prompted_instance'
                        t['semantic_tracking_failure']=dict(
                            selected_initial_obj_id=s['selected_initial_obj_id'],
                            initial_candidates=s.get('initial_candidates',[]),
                            missing_frames=s['frames'],reasons=s['reasons'])
                    elif 'selected_initial_obj_id' in s:
                        t=copy.deepcopy(s);source_dir=semantic_dirs[id];route='initial_semantic_target_identified'
                    elif s.get('exception')=='AssertionError: No unambiguous initial target identity from actual masks':
                        route='initial_semantic_no_target_use_prompted_instance'
                        t['initial_semantic_failure']=dict(exception=s['exception'],candidates=s.get('initial_candidates',[]))
                    else:
                        # An I/O/model exception remains a failure. Do not mask
                        # it by selecting the other route after looking at g.
                        t=copy.deepcopy(s);source_dir=semantic_dirs[id];route='semantic_exception_retained'
                assert t['frames']==j['frames']
                assert t['tracking_frames']==list(range(j['prompt_frame'],j['frames'][-1]+1))
                assert t['semantic_point_prompts']==j['semantic_point_prompts']
                t['source_box_mode']=t['box_mode'];t['initial_routing_reason']=route
                t['box_mode']='prefix_initial_grounded_crop_rgb_component_pixel'
                t['integrated_runner_sha256']=protocol['runner_sha256'];t['rgb_policy_sha256']=protocol['rgb_policy_sha256']
                stem=hashlib.sha256(id.encode()).hexdigest()[:12]
                masks=[];images=[];valid=[];cropped=[];cap=cv2.VideoCapture(j['video']);next_frame=None
                last_actual=None;last_frame=None
                for k,f in enumerate(t['frames']):
                    if next_frame!=f:cap.set(cv2.CAP_PROP_POS_FRAMES,f)
                    ok,rgb=cap.read();next_frame=f+1
                    if not ok:raise RuntimeError('Actual source RGB read failure: '+id)
                    m=None
                    if t['boxes'][k] is not None:
                        mp=source_dir/f'{stem}_{f}.npz';assert mp.exists(),str(mp)
                        raw=np.load(mp)['mask'].astype(np.uint8)
                        n,l,stats,_=cv2.connectedComponentsWithStats(raw,connectivity=8);assert n>1
                        m=(l==1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))).astype(np.uint8)
                    elif 'book' in j['target_name'] and last_frame==f-1 and last_actual is not None:
                        m,z=recover(rgb,last_actual,id,f);z['frame']=f;cropped.append(z)
                        if m is not None:
                            t['boxes'][k]=pixel_box(m);t['reasons'][k]='sam31_current_rgb_integer_crop'
                    if m is not None:
                        n,l,stats,_=cv2.connectedComponentsWithStats(m.astype(np.uint8),connectivity=8)
                        assert n>1
                        m=(l==1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))).astype(np.uint8)
                        masks.append(m);images.append(rgb);valid.append(k)
                        last_actual=m;last_frame=f
                cap.release()
                if len(valid)>=4: fixed,colour_audit=repair(images,masks)
                else: fixed=masks;colour_audit=[]
                for n,(index,m) in enumerate(zip(valid,fixed)):
                    np.savez_compressed(mask_out/f'{stem}_{t["frames"][index]}.npz',mask=m)
                    b=pixel_box(m)
                    if colour_audit:
                        colour_audit[n].update(frame=t['frames'][index],before_box=t['boxes'][index],after_box=b)
                    t['boxes'][index]=b
                assert len(t['boxes'])==len(t['frames'])==len(j['frames'])
                assert all(b is None or all(isinstance(x,int) for x in b) for b in t['boxes'])
                t['crop_repair_records']=cropped;t['rgb_repair_records']=colour_audit
                record=dict(id=id,initial_route=route,selected_frames=len(j['frames']),
                    missing_before=sum(b is None for b in (s if route in ['initial_semantic_target_identified','semantic_exception_retained'] else instance[id])['boxes']),
                    missing_after=sum(b is None for b in t['boxes']),raw_semantic_missing_frames=[f for f,b in zip(s['frames'],s['boxes']) if b is None] if s is not None else [],crop_attempts=cropped,colour_audit=colour_audit)
                writer.write(json.dumps(t)+'\n');writer.flush();aw.write(json.dumps(record)+'\n');aw.flush()
                done[id]=t;print(json.dumps({k:v for k,v in record.items() if k not in ['crop_attempts','colour_audit']}),flush=True)
    finally:
        if predictor is not None: predictor.shutdown()


if __name__=='__main__': main()
