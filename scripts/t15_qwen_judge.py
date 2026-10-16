"""Bounded local Qwen event diagnostic. Inputs contain no expected outcomes."""
import argparse,hashlib,json,os,re,subprocess,time
from pathlib import Path

PROMPT='''Assess ONLY visible evidence in this video. The target is the gray CLOSED LAPTOP initially on the far-right part of the wooden table, to the right of the green book. Track this SAME target. Decide whether it falls off the table during the shown interval. A fall requires visible loss of tabletop support followed by downward motion toward the floor. Camera motion, changing appearance, disappearance, or an object being replaced is not proof of falling. Use fall=0 only if the original target can be followed sufficiently to establish no fall; use null if evidence is insufficient. Do not infer an event from how physics ought to work. Judge only this target event; a video can have quality defects and still have an assessable fall outcome.
Return only JSON with exactly these keys:
{"target_description":"visible target", "fall":0 or 1 or null, "assessable":true or false, "reason":"brief visible evidence", "evidence":[{"sample_index":0,"time_s":0.0,"description":"observation"}], "quality_flags":["camera_motion", "target_identity_ambiguous", "target_deformation", "scene_discontinuity"]}
quality_flags may be empty; include only visible problems. Cite at least two different supplied sample indices for an assessable judgement, with the exact times from the supplied anchors. Do not state a fall just because the target is absent in a later frame.'''

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def validate(raw,times):
    match=re.search(r'\{.*\}',raw,re.S)
    if not match:raise ValueError('no JSON')
    d=json.loads(match.group())
    if set(d)!={'target_description','fall','assessable','reason','evidence','quality_flags'}:raise ValueError('schema keys')
    if d['fall'] is not None and (type(d['fall']) is not int or d['fall'] not in (0,1)):raise ValueError('fall not 0/1/null')
    if type(d['assessable']) is not bool or d['assessable']!=(d['fall'] is not None):raise ValueError('assessability mismatch')
    if not isinstance(d['reason'],str) or not d['reason'].strip():raise ValueError('missing evidence reason')
    indices=[]
    for e in d['evidence']:
        idx=e['sample_index']
        if type(idx) is not int or not 0<=idx<len(times):raise ValueError('invalid sample index')
        if type(e['time_s']) not in (int,float) or abs(e['time_s']-times[idx])>.011:raise ValueError('time does not match consumed sample')
        indices.append(idx)
    if d['assessable'] and len(set(indices))<2:raise ValueError('insufficient temporal evidence')
    return d

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--gpu',type=int,required=True)
    p.add_argument('--model',required=True);a=p.parse_args()
    root=Path(a.root);out=root/'results.jsonl'
    if out.exists():raise FileExistsError(out)
    query=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    gpu=next([int(v.strip()) for v in ln.split(',')] for ln in query.splitlines() if int(ln.split(',')[0])==a.gpu)
    if gpu[1]<22500 or gpu[2]>35:raise RuntimeError('insufficient shared GPU capacity')
    os.environ['CUDA_VISIBLE_DEVICES']=str(a.gpu);os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import cv2,numpy as np,torch,transformers
    from transformers import AutoModelForMultimodalLM,AutoProcessor
    from transformers.video_utils import VideoMetadata
    torch.set_num_threads(2);cv2.setNumThreads(1)
    (root/'prompt.txt').write_text(PROMPT)
    files=[p for p in Path(a.model).iterdir() if p.is_file() and p.suffix in ('.json','.safetensors')]
    receipt=dict(model=a.model,torch=torch.__version__,transformers=transformers.__version__,gpu=a.gpu,
                 source_sha256=sha(__file__),prompt_sha256=sha(root/'prompt.txt'),manifest_sha256=sha(root/'inputs.jsonl'),
                 model_files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files},
                 decoding='greedy, nonthinking',max_new_tokens=512,sampling='26 evenly spaced frames spanning each registered duration; no hidden resampling',
                 processor_total_pixel_budget=26*262144,scope='five-video development diagnostic; not independent human validation')
    (root/'receipt.json').write_text(json.dumps(receipt,indent=2))
    print('Loading registered local Qwen',flush=True)
    model=AutoModelForMultimodalLM.from_pretrained(a.model,torch_dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa',local_files_only=True).eval()
    processor=AutoProcessor.from_pretrained(a.model,local_files_only=True)
    rows=[json.loads(l) for l in (root/'inputs.jsonl').read_text().splitlines()]
    if len(rows)>6:raise ValueError('bounded diagnostic')
    with out.open('x') as f:
        for row in rows:
            start=time.time();record=dict(sample_id=row['sample_id'],video_sha256=row['sha256'])
            try:
                path=root/row['video']
                if sha(path)!=row['sha256']:raise ValueError('video hash mismatch')
                cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                end=row['start_frame']+round(row['duration_s']*fps)
                if end>=count:raise ValueError('insufficient native horizon')
                indices=np.linspace(row['start_frame'],end,26).round().astype(int).tolist();frames=[]
                for idx in indices:
                    cap.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,frame=cap.read()
                    if not ok:raise ValueError('frame decode failure')
                    frames.append(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
                cap.release();relative=[idx-row['start_frame'] for idx in indices];times=[idx/fps for idx in relative]
                record.update(native_fps=fps,native_frame_count=count,consumed_frame_indices=indices,consumed_times_s=times)
                anchors='\nSamples (index: seconds): '+', '.join(f'{i}: {t:.3f}' for i,t in enumerate(times))
                messages=[{'role':'user','content':[{'type':'video','video':str(path)},{'type':'text','text':PROMPT+anchors}]}]
                text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                meta=VideoMetadata(total_num_frames=end-row['start_frame']+1,fps=fps,width=frames[0].shape[1],height=frames[0].shape[0],
                                   duration=row['duration_s'],video_backend='opencv_explicit_frames',frames_indices=relative)
                inputs=processor(text=[text],videos=[np.stack(frames)],video_metadata=[meta],do_sample_frames=False,
                                 size={'longest_edge':26*262144,'shortest_edge':4096},return_tensors='pt').to(model.device)
                record['processor_shapes']={k:list(v.shape) for k,v in inputs.items() if hasattr(v,'shape')}
                record['video_grid_thw']=inputs['video_grid_thw'].tolist()
                assert record['video_grid_thw'][0][0]==13 and min(record['video_grid_thw'][0][1:])>=20, 'unexpected processor resolution'
                with torch.inference_mode():
                    generated=model.generate(**inputs,max_new_tokens=512,do_sample=False)
                raw=processor.batch_decode(generated[:,inputs['input_ids'].shape[1]:],skip_special_tokens=True)[0]
                record['raw']=raw
                record.update(judgement=validate(raw,times),status='ok')
                del inputs,generated
            except Exception as exc:record.update(status='failed',error=type(exc).__name__+': '+str(exc))
            record['elapsed_s']=time.time()-start
            f.write(json.dumps(record)+'\n');f.flush();torch.cuda.empty_cache()
            print(row['sample_id'],record['status'],round(record['elapsed_s'],1),flush=True)

if __name__=='__main__':main()
