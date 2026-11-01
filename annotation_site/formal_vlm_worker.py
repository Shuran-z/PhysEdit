"""Resumable VLM preassessment. Videos exist only briefly in Linux RAM (/dev/shm).

No human labels, reference outcomes, boundary answers or HF token are sent to the model.
Scoped callback key permits machine-only writes for formal3600_v1.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
SITE='https://label.yeegoods.cn/physics'
MODEL='/data1/zhangshuran/models/Qwen3.5-9B'


def dump(p,obj):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));tmp.replace(p)


def post(path,data,key):
    raw=json.dumps(data,ensure_ascii=False).encode()
    req=urllib.request.Request(SITE+path,data=raw,headers={'Content-Type':'application/json',
        'Origin':'https://label.yeegoods.cn','Authorization':'Bearer '+key})
    return json.load(urllib.request.urlopen(req,timeout=50))


def main():
    os.chdir(ROOT);deadline=time.monotonic()+72*3600
    key=json.loads((ROOT/'credentials.private.json').read_text())['worker_key']
    manifest=json.loads((ROOT/'formal_manifest.json').read_text());tasks=manifest['tasks']
    completed=set()
    if (ROOT/'results.jsonl').exists():
        for line in (ROOT/'results.jsonl').read_text().splitlines():
            result=json.loads(line);post('/api/worker/result',result,key);completed.add(result['task_id'])
    # Mix members and scenes so the first completed tranche reaches all seven people.
    if not manifest.get('preserve_processing_order'):tasks.sort(key=lambda t:(int(t['id'].rsplit('_',1)[-1])%100,t['primary_id'],t['id']))
    while True:
        q=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
        candidates=sorted([(int(a),int(b),int(c)) for a,b,c in (l.split(',') for l in q.splitlines()) if int(b)>=14000 and int(c)<=35],key=lambda r:r[1],reverse=True)
        if len(candidates)>=2 and candidates[0][1]+candidates[1][1]>=36000:break
        dump(ROOT/'status.json',{'status':'waiting_for_gpu_capacity','completed':len(completed),'total':len(tasks),'at':time.time()})
        if time.monotonic()>deadline:raise RuntimeError('GPU wait deadline exceeded')
        time.sleep(30)
    selected=candidates[:2];os.environ.update(CUDA_VISIBLE_DEVICES=','.join(str(x[0]) for x in selected),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2')
    import cv2,numpy as np,torch
    from PIL import Image
    from transformers import AutoProcessor,AutoModelForMultimodalLM
    from physedit.scene_quality import PROMPT,normalize_quality,scene_quality_route
    from physedit.qwen_boundary_judge import EVENTS
    from protocol_rules import derive_events
    from physedit.boundary_triage import parse_with_closing_brace_repair
    event_prompt='Evaluate only the supplied original-source event definitions in this generated video. Do not invent, rename or add events or thresholds. Track the original actors from the first frame. Physical errors do not by themselves imply poor visual quality. Return JSON {"events":{"REGISTERED_ID":{"label":"yes|no|uncertain","contradictions":[]}}}. Judge actual occurrence, not the expected outcome. Last-frame events concern only the last supplied frame. Numerical predicates require genuine calibrated measurements; do not convert guessed pixels or source dimensions into generated-video world coordinates. If unavailable use uncertain, unless a visibly false nonnumerical conjunct already disproves a conjunction. Optional calibrated measurement={unit,values,method,calibration_reference}; optional component_measurements and component_labels may record conjunction evidence. Do not output reference answers, invented timestamps or rationales. Include every supplied event ID and no others.'

    memory={i:str(min(19,(r[1]-2500)//1024))+'GiB' for i,r in enumerate(selected)}
    dump(ROOT/'status.json',{'status':'loading_model','completed':len(completed),'total':len(tasks),'gpus':[x[0] for x in selected],'at':time.time()})
    model=AutoModelForMultimodalLM.from_pretrained(MODEL,local_files_only=True,torch_dtype=torch.bfloat16,device_map='auto',max_memory=memory).eval()
    processor=AutoProcessor.from_pretrained(MODEL,local_files_only=True)
    source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'formal_vlm_worker.py',ROOT/'physedit/scene_quality.py',ROOT/'physedit/qwen_boundary_judge.py',ROOT/'protocol_rules.py']}
    receipt={'model':MODEL,'frames':13,'quality_prompt_sha256':hashlib.sha256(PROMPT.encode()).hexdigest(),
        'event_prompt_sha256':hashlib.sha256(event_prompt.encode()).hexdigest(),'source_hashes':source_hashes,'event_chunk_size':4,'observation_protocol':'per-task-original-contracts-v3.0-v3.2','event_definition_authority':'original generation configuration and registered protocol','auxiliary_events_sent':False,
        'manifest_sha256':hashlib.sha256((ROOT/'formal_manifest.json').read_bytes()).hexdigest(),
        'max_new_tokens':1600,'video_storage':'one temporary RAM file; no disk cache; browser plays from HF',
        'reference_answers_provided':False,'gpus':[x[0] for x in selected],'torch':torch.__version__}
    dump(ROOT/'RECEIPT.json',receipt)

    def judge(task,images,ids,times,stage,chunk=False):
        if stage=='events' and not chunk:
            primitive={k:v for k,v in task['protocol']['events'].items() if not v.get('derived_from')};merged={};parts=[]
            keys=list(primitive)
            for offset in range(0,len(keys),4):
                group={k:primitive[k] for k in keys[offset:offset+4]};sub={**task,'protocol':{**task['protocol'],'events':group}}
                part=judge(sub,images,ids,times,stage,True);parts.append(part)
                if part['status']!='ok':return {**part,'chunks':parts}
                merged.update(part['events'])
            return {'sample_id':task['id'],'video_sha256':task['video_sha256'],'frame_indices':ids,'times_s':times,'status':'ok','events':derive_events(merged,task['protocol']['events']),'chunks':parts,'elapsed_s':sum(p['elapsed_s'] for p in parts)}
        begin=time.time();prompt=PROMPT if stage=='quality' else event_prompt
        content=[{'type':'text','text':prompt+'\nTarget: '+task['protocol'].get('target_en',task['protocol']['target'])}]
        if stage=='events':
            def compact(d):
                out={k:d[k] for k in ('name','definition','actors','metric_rule','source_conjunction','source_boolean_expression','source_order','required_contact_pairs','time_semantics') if k in d}
                if d.get('component_definitions'):out['component_definitions']={k:compact(v) for k,v in d['component_definitions'].items()}
                return out
            content.append({'type':'text','text':'Original-source definitions: '+json.dumps({k:compact(d) for k,d in task['protocol']['events'].items()})})
        for index,(image,frame,stamp) in enumerate(zip(images,ids,times)):
            content.extend([{'type':'text','text':f'Sample {index}; native frame {frame}; time {stamp:.6f} seconds'},{'type':'image','image':image}])
        result={'sample_id':task['id'],'video_sha256':task['video_sha256'],'frame_indices':ids,'times_s':times,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
        try:
            text=processor.apply_chat_template([{'role':'user','content':content}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
            inputs=processor(text=[text],images=images,return_tensors='pt').to(model.device)
            with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=1600,do_sample=False)
            raw=processor.batch_decode(generated[:,inputs['input_ids'].shape[1]:],skip_special_tokens=True)[0]
            result['raw']=raw;d,repair=parse_with_closing_brace_repair(raw)
            if stage=='events' and isinstance(d,dict) and set(d)==set(task['protocol']['events']):
                d={'events':d};repair=(repair+'; ' if repair else '')+'wrapped_exact_registered_event_map'
            if not isinstance(d,dict) or not isinstance(d.get(stage),dict):raise ValueError('missing task output')
            if stage=='quality':d['quality']=normalize_quality(d['quality'],times)
            else:
                if set(d['events'])!=set(task['protocol']['events']):raise ValueError('incomplete registered events')
                for event_id,e in list(d['events'].items()):
                    # An exact registered label in compact JSON is a format
                    # variant, not an inferred event or fabricated evidence.
                    if isinstance(e,str) and e in ('yes','no','uncertain','not_observed'):
                        e={'label':e};d['events'][event_id]=e
                        repair=(repair+'; ' if repair else '')+'normalized_registered_label_string:'+event_id
                    if not isinstance(e,dict):raise ValueError('registered event output is not a label object')
                    if e.get('label') not in ('yes','no','uncertain','not_observed'):raise ValueError('invalid event label')
                    ev=e.get('evidence_times_s',[])
                    if not isinstance(ev,list) or any(type(t) not in (int,float) or not math.isfinite(t) or not any(abs(t-s)<=1e-5 for s in times) for t in ev):raise ValueError('evidence timestamp not supplied')
            result.update(status='ok',format_repair=repair,**{stage:d[stage]})
        except Exception as exc:
            result.update(status='evaluator_failure',error=type(exc).__name__+': '+str(exc)[:400])
        result['elapsed_s']=time.time()-begin
        return result

    failures=0
    with (ROOT/'results.jsonl').open('a',encoding='utf-8') as stream:
        for task in tasks:
            if task['id'] in completed:continue
            if time.monotonic()>deadline:raise RuntimeError('Run deadline exceeded; remaining tasks retained')
            dump(ROOT/'status.json',{'status':'running','completed':len(completed),'total':len(tasks),'current_task':task['id'],'at':time.time()})
            machine={'judge':'Qwen3.5-9B; scene-integrity-v2; 13 full-image supplied frames','receipt':receipt,'pipeline_status':'evaluator_failure'}
            try:
                location=post('/api/worker/media-url',{'task_id':task['id']},key)['url']
                with tempfile.TemporaryDirectory(prefix='phy2-vlm-',dir='/dev/shm') as temp:
                    path=Path(temp)/'video.mp4'
                    with urllib.request.urlopen(location,timeout=60) as response:
                        data=response.read(task['remote_media']['size']+1)
                    if len(data)!=task['remote_media']['size'] or hashlib.sha256(data).hexdigest()!=task['video_sha256']:raise ValueError('Downloaded pinned video identity mismatch')
                    path.write_bytes(data);del data
                    cap=cv2.VideoCapture(str(path));fps=cap.get(5);frames=int(cap.get(7))
                    if abs(fps-task['fps'])>.02 or frames!=task['frames']:raise ValueError('Native clock mismatch; task needs metadata audit')
                    end=min(frames-1,int(task['window_s']*fps+1e-6));ids=sorted(set(np.linspace(0,end,13).round().astype(int).tolist()));images=[];times=[]
                    for frame in ids:
                        cap.set(1,frame);ok,bgr=cap.read()
                        if not ok:raise ValueError('native frame decode failed')
                        images.append(Image.fromarray(cv2.cvtColor(cv2.resize(bgr,(768,432)),cv2.COLOR_BGR2RGB)));times.append(frame/fps)
                    cap.release()
                    machine['media_verified']={'sha256':task['video_sha256'],'frames':frames,'fps':fps,'size':task['remote_media']['size']}
                    cached=task.get('prior_quality_prediction');quality=cached if cached and cached.get('status')=='ok' and cached.get('video_sha256')==task['video_sha256'] else judge(task,images,ids,times,'quality');machine['quality_prediction']=quality
                    machine['quality_reused']=quality is cached
                    route=scene_quality_route(quality.get('quality',{}),task['window_s']) if quality['status']=='ok' else 'evaluator_failure';machine['quality_route']=route
                    if task['protocol']['events'] and route not in ('auto_rejected','evaluator_failure'):
                        machine['event_prediction']=judge(task,images,ids,times,'events')
                    else:
                        machine['event_prediction']={'status':'not_scheduled','video_sha256':task['video_sha256'],
                            'reason':'critical_event_contract_pending' if not task['protocol']['events'] else 'quality_blocked_or_evaluator_failure'}
                    machine['pipeline_status']='evaluator_failure' if quality['status']!='ok' or machine['event_prediction'].get('status')=='evaluator_failure' else 'blocked_quality' if route=='auto_rejected' else 'complete'
            except Exception as exc:
                # A network/identity failure is NOT a completed VLM attempt. Leave the task locked.
                dump(ROOT/'MEDIA_BLOCKED.json',{'task_id':task['id'],'error':type(exc).__name__,
                    'reason':'Media could not be hash/clock verified; no human task unlocked','at':time.time()})
                raise RuntimeError('Media verification/network unavailable; remaining tasks retained') from None
            result={'task_id':task['id'],'video_sha256':task['video_sha256'],'protocol_sha256':task['protocol_sha256'],'machine':machine}
            # Durable result before callback. On restart callbacks are idempotent.
            stream.write(json.dumps(result,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
            for attempt in range(8):
                try:post('/api/worker/result',result,key);break
                except Exception:
                    if attempt==7:raise RuntimeError('Site callback unavailable; result retained locally') from None
                    time.sleep(min(30,2**attempt))
            completed.add(task['id']);failures=failures+1 if machine['pipeline_status']=='evaluator_failure' else 0
            dump(ROOT/'status.json',{'status':'running','completed':len(completed),'total':len(tasks),'last_task':task['id'],'last_pipeline_status':machine['pipeline_status'],'at':time.time()})
            if failures>=3:raise RuntimeError('Three consecutive evaluator failures; remaining tasks retained, no automatic pass')
    dump(ROOT/'status.json',{'status':'complete','completed':len(completed),'total':len(tasks),'at':time.time()})


if __name__=='__main__':
    try:main()
    except Exception as exc:
        dump(ROOT/'STOPPED.json',{'error':type(exc).__name__+': '+str(exc)[:500],'at':time.time()})
        raise
