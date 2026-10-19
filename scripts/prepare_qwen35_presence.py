import json
from pathlib import Path

base=Path(__file__).resolve().parents[1]
old=base/'review/qwen35_crop_prompt_v2_20261016'
out=base/'review/qwen35_presence_zoom_20261016'
out.mkdir(exist_ok=True)
presence='''Inspect the same closed laptop initially on the tabletop to the right of the green book. This is a fixed enlarged view of the table edge and area below. Only assess whether the original target remains visible and trackable, NOT whether it falls. Follow its contour through rotation; a dark thin edge or underside can be the same object, but do not assume every dark line is the laptop. Check the final frame carefully. Distinguish visible target, partial occlusion, outside crop, definite visible fusion/replacement, and uncertainty. Mere absence is not destruction. Do not invent observations or assume an expected answer.
Return JSON only: {"target_at_end":"visible / partially_visible / not_visible / uncertain", "identity":"maintained / lost / uncertain", "last_visible_sample":null, "reason":"visible position, contour and continuity evidence", "evidence":[{"sample_index":0,"description":"observation"},{"sample_index":25,"description":"observation"}]}. Choose one enum value. last_visible_sample is an integer 0-25 or null. Cite at least two distinct actual sampled indices, including the final sample. Output frame indices only; the program maps them to timestamps.'''
fall='''Assess whether the original closed laptop initially to the right of the green book loses tabletop support and moves downward during this fixed cropped video. A prior visibility-only observation is supplied below as a fallible aid, NOT ground truth; verify it against the video. Visibility alone does not imply support or falling. Rotation, tilting, or a thin dark shape beside/below the table edge can leave support uncertain. Distinguish clearly supported throughout, clear support loss with descent, and ambiguous edge/contact state. Landing is not required for a clear fall. Do not infer disappearance from color changes or falling from absence. Do not assume the question implies a fall should happen.
Return JSON only: {"support_state":"supported / detached_descending / edge_contact_uncertain / unobservable", "fall":null, "event_gate":"usable / review / reject", "reason":"visible support and motion evidence", "evidence":[{"sample_index":0,"description":"observation"},{"sample_index":25,"description":"observation"}]}. Choose one enum value. fall=1 only for clear support loss and descent, fall=0 only for clearly supported throughout, otherwise null and review. Reject only for definite visible identity destruction preventing measurement. Cite at least two distinct actual sampled indices; output indices only, no invented timestamps.'''
src=(old/'judge.py').read_text(encoding='utf-8')
start=src.index('PROMPT=');end=src.index('\n\ndef sha',start)
src=src[:start]+'PROMPT='+repr(presence)+'\nFALL_PROMPT='+repr(fall)+src[end:]
start=src.index('def validate(');end=src.index('\ndef main',start)
src=src[:start]+'''def validate(raw,times):
    match=re.search(r'\{.*\}',raw,re.S)
    if not match:raise ValueError('no JSON')
    d=json.loads(match.group())
    if not d.get('reason'):raise ValueError('reason required')
    if 'target_at_end' in d:
        if d['target_at_end'] not in ('visible','partially_visible','not_visible','uncertain'):raise ValueError('visibility')
        if d.get('identity') not in ('maintained','lost','uncertain'):raise ValueError('identity')
        last=d.get('last_visible_sample')
        if last is not None and (type(last) is not int or not 0<=last<len(times)):raise ValueError('last_visible_sample')
    else:
        if d.get('support_state') not in ('supported','detached_descending','edge_contact_uncertain','unobservable'):raise ValueError('support')
        if d.get('event_gate') not in ('usable','review','reject'):raise ValueError('gate')
        if d.get('fall') is not None and (type(d['fall']) is not int or d['fall'] not in (0,1)):raise ValueError('fall')
        if d['event_gate']=='usable' and d.get('fall') is None:raise ValueError('usable without label')
    indices=[]
    for e in d['evidence']:
        idx=e['sample_index']
        if type(idx) is not int or not 0<=idx<len(times):raise ValueError('sample index')
        if not e.get('description'):raise ValueError('description')
        e['mapped_time_s']=times[idx]
        indices.append(idx)
    if len(set(indices))<2:raise ValueError('two evidence frames required')
    if 'target_at_end' in d and len(times)-1 not in indices:raise ValueError('final frame evidence required')
    return d
''' + src[end:]
src=src.replace("(root/'prompt.txt').write_text(PROMPT)","(root/'prompt.txt').write_text(PROMPT)\n    (root/'fall_prompt.txt').write_text(FALL_PROMPT)")
src=src.replace("scope='6 calls: same crop inputs, revised prompt v2; development only'", "scope='two clips x presence then fall; fixed tighter crop; development only',fall_prompt_sha256=sha(root/'fall_prompt.txt')")
src=src.replace('roi_xyxy=[350,70,710,430]','roi_xyxy=[430,40,630,240]')
src=src.replace("view_order=['crop']", "view_order=['presence','fall']")
src=src.replace("budget_note='identical crop arrays and decoding to prior crop arm; prompt changed'", "budget_note='200px ROI enlarged to 512; stage tasks changed; not a pure scale ablation'")
src=src.replace("if len(rows)!=6:raise ValueError('six fixed clips required')", "if len(rows)!=2:raise ValueError('two fixed clips required')")
src=src.replace("rows=[dict(row,view=view) for view in ('crop',) for row in rows]", "rows=[dict(row,view=view) for view in ('presence','fall') for row in rows]\n    visibility={}")
src=src.replace("start=time.time();record=", "prompt=PROMPT if row['view']=='presence' else FALL_PROMPT+'\\nPrior visibility observation: '+json.dumps(visibility.get(row['sample_id'],{'status':'unavailable'}))\n            start=time.time();record=")
src=src.replace('f[70:430,350:710]','f[40:240,430:630]')
src=src.replace("views=[full] if row['view']=='full' else [crop] if row['view']=='crop' else [full,crop]", "views=[crop]")
src=src.replace('(PROMPT+anchors)','(prompt+anchors)').replace("'text':PROMPT+anchors","'text':prompt+anchors")
src=src.replace("record['elapsed_s']=time.time()-start", "if row['view']=='presence':visibility[row['sample_id']]=record.get('judgement',{'status':'evaluator_failure'})\n            record['elapsed_s']=time.time()-start")
(out/'judge.py').write_text(src,encoding='utf-8')
compile(src,str(out/'judge.py'),'exec')
rows=[json.loads(l) for l in (old/'inputs.jsonl').read_text().splitlines() if l.strip()]
(out/'inputs.jsonl').write_text('\n'.join(json.dumps(r) for r in rows if r['sample_id'] in ('clip03','clip06'))+'\n')
(out/'prompt.txt').write_text(presence,encoding='utf-8')
(out/'fall_prompt.txt').write_text(fall,encoding='utf-8')
print('Prepared two-stage tight crop experiment')
