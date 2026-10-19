import json,shutil
from pathlib import Path
base=Path(__file__).resolve().parents[1]
old=base/'review/qwen35_sam2_event_20261016'
out=base/'review/qwen35_sam2_observation_20261016';out.mkdir(exist_ok=True)
src=(old/'qwen_sam2_event.py').read_text(encoding='utf-8')
prompt='''Inspect these time-ordered frames of the closed laptop initially to the right of the green book. Red boxes are SAM2 location hints, not proof of motion or contact; thin parts of the object may extend outside a box. Use actual pixels to inspect target continuity and the target-table relationship. Do not use the box top crossing the tabletop as proof of detachment. Rotation or downward movement alone does not establish complete loss of tabletop support. Do not require landing if detachment and downward movement are clearly visible. Do not assume a desired result.
Return JSON only with primary observations, NOT scores or routing fields:
{"target_at_end":"visible / partially_visible / not_visible / uncertain", "support_state":"supported / detached_descending / edge_contact_uncertain / unobservable", "evidence_image_indices":[0,12], "detachment_evidence_indices":[], "descent_evidence_indices":[], "reason":"describe the visible upper contour/contact relation, motion, and any uncertainty"}.
Choose one enum value. supported means visibly supported throughout the observed sequence; detached_descending requires visible complete detachment and downward displacement. edge_contact_uncertain means rotation/descent occurs near the edge but continued contact cannot be resolved. unobservable means target/support evidence cannot be read. Cite at least two evidence images. For detached_descending cite at least one image visibly showing detachment and two images showing descent. Leave detachment_evidence_indices empty if separation cannot be established. Image indices refer to this list; timestamps are assigned by code. Do not output fall or event_gate; the program derives them. No previous model verdict is supplied.'''
src=src.replace('def sha(p):','PROMPTS["event"]='+repr(prompt)+'\n\nfrom boundary_event_judge import normalize_observation\n\ndef sha(p):')
start=src.index('    else:\n        if d.get(\'support_state\')',src.index('def parse('))
end=src.index('    return d',start)
src=src[:start]+"    else:\n        normalize_observation(d,n)\n"+src[end:]
src=src.replace("with output.open('x') as stream:","rows=[dict(row,repetition=rep) for rep in (1,2) for row in rows]\n    with output.open('x') as stream:")
src=src.replace("r=dict(sample_id=sid,stage=stage)","r=dict(sample_id=sid,stage=stage,repetition=row['repetition'])")
src=src.replace("r.update(judgement=parse(raw,stage,len(ids)),status='ok')", "r.update(judgement=parse(raw,stage,len(ids)),status='ok')\n                r['normalized']=normalize_observation(r['judgement'],len(ids))")
(out/'judge.py').write_text(src,encoding='utf-8');compile(src,'judge.py','exec')
for name in ('inputs.jsonl','verified_boxes.json'):shutil.copyfile(old/name,out/name)
shutil.copyfile(base/'physedit/boundary_event_judge.py',out/'boundary_event_judge.py')
(out/'prompt.txt').write_text(prompt,encoding='utf-8')
print('Prepared 4 calls: 2 cases x 2 identical greedy repetitions; no posthoc retries')
