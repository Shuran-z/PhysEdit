"""Prepare a six-video, answer-blind screening diagnostic."""
from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parents[1]
O=R/'review/qwen35_screen_probe_20261016';O.mkdir(exist_ok=False);(O/'media').mkdir()
H=R/'review/h3_delivery_audit_20261016/t15_h3_b06b492_20261016/generated_preview'
sources=[(H/'case01_s41000.mp4',5.125),(R/'review/t15_qwen_judge_20261015/media/case01.mp4',6),
         (H/'case02_s41001.mp4',5.125),(H/'case02_s41000.mp4',5.125),
         (R/'review/t15_qwen_judge_20261015/media/case05.mp4',6),(H/'case01_s41001.mp4',5.125)]
rows=[];mapping=[]
for i,(p,d) in enumerate(sources,1):
 sid=f'clip{i:02d}';dest=O/'media'/f'{sid}.mp4';shutil.copy2(p,dest)
 rows.append(dict(sample_id=sid,video=f'media/{sid}.mp4',sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),start_frame=0,duration_s=d))
 mapping.append(dict(sample_id=sid,source=str(p)))
(O/'inputs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
(O/'local_mapping.json').write_text(json.dumps(mapping,indent=2),encoding='utf-8')
prompt='''You are screening a generated video for measurement usability, not aesthetic quality or correct physics. Track the SAME gray closed laptop initially on the table to the right of the green book. Do not confuse it with later objects. Give independent decisions:
identity: maintained / lost / uncertain. Lost means visible disappearance, fusion with background, or replacement prevents following the original target.
event_gate: usable / reject / review. Usable requires sufficient evidence to decide whether this target loses tabletop support and moves downward during the shown window. Reject only for definite identity loss or scene corruption preventing that decision. Review for ambiguity such as hanging at an edge, occlusion, or uncertain support. A physically wrong but observable event is usable. Camera movement alone is not automatic rejection.
inversion_gate: candidate / reject / review. Candidate requires a visibly trackable contact-free falling segment with sufficiently stable camera; this is visual triage only, NOT validated gravity identifiability. Reject for definite loss or absence of such motion; review when uncertain. Do not infer metric eligibility from the requested physics.
fall: 0 / 1 / null. Never label disappearance as a fall. If identity is lost, use null. Edge-hanging without clear support-loss evidence is null.
Return JSON only: {"identity":"...","event_gate":"...","inversion_gate":"...","fall":null,"reason":"specific visible observations","evidence":[{"sample_index":0,"time_s":0.0,"description":"specific observation"},{"sample_index":25,"time_s":0.0,"description":"specific later observation"}]}. Cite at least TWO distinct sampled indices with their actual anchor times. Do not copy placeholder observations. No reference outcomes are supplied.'''
s=(R/'review/t15_qwen_judge_20261015/corrected/judge.py').read_text(encoding='utf-8')
a=s.index("PROMPT='''");b=s.index('\ndef sha(',a);s=s[:a]+'PROMPT='+repr(prompt)+'\n'+s[b:]
a=s.index('    if set(d)!=');b=s.index('    indices=[]',a)
s=s[:a]+'''    if d.get('identity') not in ('maintained','lost','uncertain'):raise ValueError('identity')
    if d.get('event_gate') not in ('usable','reject','review'):raise ValueError('event_gate')
    if d.get('inversion_gate') not in ('candidate','reject','review'):raise ValueError('inversion_gate')
    if d.get('fall') is not None and (type(d['fall']) is not int or d['fall'] not in (0,1)):raise ValueError('fall')
    if not d.get('reason'):raise ValueError('reason')
'''+s[b:]
s=s.replace("if d['assessable'] and len(set(indices))<2:","if len(set(indices))<2:")
s=s.replace("if gpu[1]<22500 or gpu[2]>35:","if any(int(ln.split(',')[1])<16500 or int(ln.split(',')[2])>35 for ln in query.splitlines() if int(ln.split(',')[0]) in (3,5)):")
s=s.replace("str(a.gpu);os.environ", "'3,5';os.environ")
s=s.replace("device_map='cuda'", "device_map='auto',max_memory={0:'12GiB',1:'12GiB','cpu':'32GiB'}")
s=s.replace('max_new_tokens=512','max_new_tokens=768').replace('spanning exactly 0..6s','spanning each declared horizon')
s=s.replace('five-video development diagnostic','six-video screening development diagnostic')
s=s.replace('gpu=a.gpu,',"gpu=[3,5],device_map='auto; 12GiB per GPU; CPU fallback 32GiB',")
(O/'judge.py').write_text(s,encoding='utf-8')
print(O)
