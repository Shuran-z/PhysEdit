"""Two-case image grounding diagnostic. Separate calls never inherit model prose."""
import argparse, hashlib, json, os, re, subprocess, time
from pathlib import Path

PROMPTS = {
 'locate': '''Image 0 is the initial frame identifying a closed laptop on the tabletop to the right of the green book. Image 1 is the final frame of the same fixed crop. Locate that target in IMAGE 1 ONLY. Do not assess falling or support. Track object appearance through rotation but do not invent an object. Return JSON only: {"visibility":"visible / partially_visible / not_visible / uncertain", "bbox_xyxy":null, "reason":"visible shape and location"}. For a visible target return its tight box [xmin,ymin,xmax,ymax] in normalized integer coordinates 0-1000 relative to IMAGE 1. If not visible or uncertain, use null. Do not return a box for the green book, table, sofa or floor object.''',
 'continuity': '''These ordered images show the same fixed crop. Image 0 is the initial target reference: the closed laptop to the right of the green book. The remaining images are labeled by native frame ID and time. A candidate target box is drawn ONLY on the final image; it is a location hint, not proof of identity. Independently determine whether the candidate is the same object as in preceding frames and the initial reference. Inspect contour, pose and spatial continuity. Do not assess falling or support, and do not assume continuity merely because a box is drawn. Return JSON only: {"same_object":"yes / no / uncertain", "boxes":[{"image_index":1,"bbox_xyxy":[0,0,1,1]}], "reason":"specific continuity or contradiction evidence"}. Return a tight target box for EACH non-reference image using normalized integer xyxy coordinates 0-1000, or null where uncertain. image_index refers to the supplied image list, not a frame ID. Do not copy placeholder coordinates.''',
 'event': '''Inspect the ordered fixed-crop images and their frame IDs/times. The target is the closed laptop initially on the tabletop to the right of the green book. Boxes are location hints only, NOT evidence of support loss. Independently judge the visible support and motion; no previous model explanation or verdict is supplied. A target can rotate or extend below the tabletop while support/contact remains uncertain. Being visible below the edge alone is insufficient to prove complete detachment. Clear support loss and descent can establish falling without seeing landing. Do not infer falling from absence. Return JSON only: {"support_state":"supported / detached_descending / edge_contact_uncertain / unobservable", "fall":null, "event_gate":"usable / review", "evidence_image_indices":[0,1], "reason":"specific visible contact and motion evidence"}. Use fall=1 only for clear support loss and descent, 0 only if clearly supported throughout the provided sequence; otherwise null and review. Choose one enum value, cite at least two valid image indices. Do not treat the question as an instruction that falling must occur.'''
}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def box_ok(b):
    return b is None or (isinstance(b,list) and len(b)==4 and all(type(x) is int and 0<=x<=1000 for x in b) and b[0]<b[2] and b[1]<b[3])

def parse(raw,stage,n):
    m=re.search(r'\{.*\}',raw,re.S)
    if not m:raise ValueError('no JSON')
    d=json.loads(m.group())
    if not d.get('reason'):raise ValueError('reason')
    if stage=='locate':
        if d.get('visibility') not in ('visible','partially_visible','not_visible','uncertain') or not box_ok(d.get('bbox_xyxy')):raise ValueError('location schema')
        if d['visibility'] in ('visible','partially_visible') and d.get('bbox_xyxy') is None:raise ValueError('visible without box')
    elif stage=='continuity':
        if d.get('same_object') not in ('yes','no','uncertain'):raise ValueError('continuity enum')
        boxes=d.get('boxes',[])
        if len(boxes)!=n-1 or {b['image_index'] for b in boxes}!=set(range(1,n)):raise ValueError('one box per non-reference frame')
        if not all(box_ok(b.get('bbox_xyxy')) for b in boxes):raise ValueError('bbox')
    else:
        if d.get('support_state') not in ('supported','detached_descending','edge_contact_uncertain','unobservable'):raise ValueError('support')
        if d.get('event_gate') not in ('usable','review'):raise ValueError('event gate')
        if d.get('fall') is not None and (type(d['fall']) is not int or d['fall'] not in (0,1)):raise ValueError('fall')
        if (d['event_gate']=='usable') != (d.get('fall') is not None):raise ValueError('gate/label mismatch')
        ev=d.get('evidence_image_indices',[])
        if len(set(ev))<2 or not all(type(x) is int and 0<=x<n for x in ev):raise ValueError('evidence indices')
    return d

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--stage',choices=PROMPTS,required=True);a=p.parse_args()
    root=Path(a.root);stage=a.stage;output=root/f'{stage}_results.jsonl'
    if output.exists():raise FileExistsError(output)
    if stage!='locate':
        approval=json.loads((root/'verified_boxes.json').read_text())
    else:approval={}
    query=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    if any(int(l.split(',')[1])<16500 or int(l.split(',')[2])>35 for l in query.splitlines() if int(l.split(',')[0]) in (3,5)):raise RuntimeError('shared GPU capacity unavailable')
    os.environ['CUDA_VISIBLE_DEVICES']='3,5';os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import cv2,numpy as np,torch,transformers
    from PIL import Image
    from transformers import AutoProcessor,AutoModelForMultimodalLM
    torch.set_num_threads(2);cv2.setNumThreads(1)
    model_path='/data1/zhangshuran/models/Qwen3.5-9B'
    (root/f'{stage}_prompt.txt').write_text(PROMPTS[stage])
    receipt=dict(stage=stage,source_sha256=sha(__file__),prompt_sha256=sha(root/f'{stage}_prompt.txt'),model=model_path,
        model_weight_fingerprints_reference='/data2/wangzijun_p25/liyuhan/qwen35_presence_zoom_20261016/receipt.json',
        note='Previously hashed same deployed model; weights not rehashed for each diagnostic stage',torch=torch.__version__,transformers=transformers.__version__,
        decoding='greedy nonthinking BF16',max_new_tokens=768,roi=[430,40,630,240],resize=[512,512],approval_sha256=sha(root/'verified_boxes.json') if approval else None)
    (root/f'{stage}_receipt.json').write_text(json.dumps(receipt,indent=2))
    model=AutoModelForMultimodalLM.from_pretrained(model_path,torch_dtype=torch.bfloat16,device_map='auto',max_memory={0:'12GiB',1:'12GiB','cpu':'32GiB'},attn_implementation='sdpa',local_files_only=True).eval()
    processor=AutoProcessor.from_pretrained(model_path,local_files_only=True)
    rows=[json.loads(l) for l in (root/'inputs.jsonl').read_text().splitlines() if l.strip()]
    with output.open('x') as stream:
        for row in rows:
            sid=row['sample_id'];start=time.time();r=dict(sample_id=sid,stage=stage)
            if stage!='locate' and not approval.get(sid,{}).get('location_confirmed'):continue
            if stage=='event' and not approval[sid].get('continuity_confirmed'):continue
            try:
                path=root/row['video'];assert sha(path)==row['sha256']
                cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);end=round(row['duration_s']*fps)
                # Initial identity anchor plus temporal neighborhood and wider pose transition.
                ids=[0,end] if stage=='locate' else [0,round(end*.6),round(end*.8),end-6,end-3,end]
                if stage=='event':ids=np.linspace(0,end,13).round().astype(int).tolist()
                imgs=[];hashes=[]
                for i,idx in enumerate(ids):
                    cap.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,f=cap.read();assert ok
                    f=cv2.cvtColor(cv2.resize(f[40:240,430:630],(512,512),interpolation=cv2.INTER_CUBIC),cv2.COLOR_BGR2RGB)
                    hashes.append(hashlib.sha256(f.tobytes()).hexdigest())
                    if stage!='locate' and idx==end:
                        b=approval[sid]['bbox_xyxy'];x1,y1,x2,y2=[round(x*512/1000) for x in b]
                        cv2.rectangle(f,(x1,y1),(x2,y2),(255,0,0),2)
                    imgs.append(Image.fromarray(f))
                cap.release()
                anchors='\nImages in order: '+', '.join(f'image {i}: native frame {idx}, {idx/fps:.3f}s' for i,idx in enumerate(ids))
                content=[{'type':'image','image':img} for img in imgs]+[{'type':'text','text':PROMPTS[stage]+anchors}]
                text=processor.apply_chat_template([{'role':'user','content':content}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
                inputs=processor(text=[text],images=imgs,return_tensors='pt').to(model.device)
                r.update(video_sha256=sha(path),frame_indices=ids,times_s=[i/fps for i in ids],unmarked_array_sha256=hashes,
                         input_array_sha256=[hashlib.sha256(np.array(im).tobytes()).hexdigest() for im in imgs],image_grid_thw=inputs['image_grid_thw'].tolist(),text_sha256=hashlib.sha256((PROMPTS[stage]+anchors).encode()).hexdigest())
                with torch.inference_mode():g=model.generate(**inputs,max_new_tokens=768,do_sample=False)
                raw=processor.batch_decode(g[:,inputs['input_ids'].shape[1]:],skip_special_tokens=True)[0]
                r['raw']=raw;r.update(judgement=parse(raw,stage,len(ids)),status='ok')
                del inputs,g
            except Exception as exc:r.update(status='failed',error=type(exc).__name__+': '+str(exc))
            r['elapsed_s']=time.time()-start;stream.write(json.dumps(r)+'\n');stream.flush();torch.cuda.empty_cache()
            print(sid,stage,r['status'],round(r['elapsed_s'],1),flush=True)

if __name__=='__main__':main()
