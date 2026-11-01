"""Small evidence-first VLM pixel review, advisory only, no acceptance writes."""
import pathlib,json,subprocess,os,fcntl,time,hashlib
ROOT=pathlib.Path(__file__).resolve().parent
snap=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free,utilization.gpu','--format=csv,noheader,nounits'],universal_newlines=True)
leases=[];chosen=[]
for idx,free,util in sorted([tuple(map(int,l.split(','))) for l in snap.splitlines()],key=lambda x:-x[1]):
    if free<18000 or util>80:continue
    lease=open('/tmp/phy2-vlm200-gpu-%d.lock'%idx,'a')
    try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:lease.close();continue
    leases.append(lease);chosen.append((idx,free,util))
    if len(chosen)==2:break
if len(chosen)!=2:raise RuntimeError('No two sufficiently free GPUs; no model loaded')
os.environ.update(CUDA_VISIBLE_DEVICES=','.join(str(r[0]) for r in chosen),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2')
import torch
from PIL import Image
from transformers import AutoProcessor,AutoModelForMultimodalLM
MODEL='/data1/zhangshuran/models/Qwen3.5-9B'
model=AutoModelForMultimodalLM.from_pretrained(MODEL,local_files_only=True,torch_dtype=torch.bfloat16,device_map='sequential',max_memory={i:str((v[1]-5000)//1024)+'GiB' for i,v in enumerate(chosen)}).eval()
assert not any(str(v) in ['cpu','disk'] for v in model.hf_device_map.values())
processor=AutoProcessor.from_pretrained(MODEL,local_files_only=True)
prompt='''Inspect the actual ordered frames of one simulated reference video. Frame indices are provided. This is a quality review, not a prediction of the desired event outcome. Check original object identity/shape, interpretable support geometry, severe visible penetration, unexplained teleportation, and whether relevant motion remains visible. Ordinary occlusion, rotation, leaving the field of view, and an event not occurring are not themselves corrupted physics. Prescribed externally controlled motion can exist; do not call it impossible without the control metadata. Do not infer collision-free physics from sparse frames. Separate directly visible evidence from unresolved concerns. Return JSON only with keys: identity (preserved|lost|uncertain), geometry (interpretable|corrupted|uncertain), visible_physics (no_obvious_issue|suspected_issue|uncertain), event_visibility (sufficient|limited|uncertain), evidence (list of objects with frames, observation, concern), recommendation (review_candidate|reject_candidate|no_obvious_visual_defect). Every suspected defect requires specific frame evidence. No confidence number can grant formal acceptance.'''
receipt=dict(gpus=chosen,model=MODEL,prompt=prompt,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),sampling='22 frames at 0,10,...,200,209 of 210; sparse diagnostic only',formal_acceptance=False)
(ROOT/'receipt.json').write_text(json.dumps(receipt,indent=2))
for p in sorted((ROOT/'inputs').glob('*.jpg')):
    sheet=Image.open(p).convert('RGB');frames=[];content=[{'type':'text','text':prompt}]
    for i,frame_id in enumerate(list(range(0,210,10))+[209]):
        im=sheet.crop(((i%4)*384,(i//4)*216,(i%4+1)*384,(i//4+1)*216));frames.append(im)
        content.extend([{'type':'text','text':'Frame '+str(frame_id)},{'type':'image','image':im}])
    text=processor.apply_chat_template([{'role':'user','content':content}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
    inputs=processor(text=[text],images=frames,return_tensors='pt').to(model.device);start=time.time()
    with torch.inference_mode():g=model.generate(**inputs,max_new_tokens=700,do_sample=False)
    raw=processor.batch_decode(g[:,inputs['input_ids'].shape[1]:],skip_special_tokens=True)[0]
    record=dict(sample_camera=p.stem,raw=raw,seconds=time.time()-start,sheet_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),formal_acceptance=False)
    with (ROOT/'results.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
    print(p.stem,round(record['seconds'],1),flush=True)
(ROOT/'complete.json').write_text(json.dumps(dict(videos=6,formal_acceptance=False)))
