"""Create a reproducible development runner from the retained v1 diagnostic."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
old=root/'review/other_scene_window_probe_20261016'
out=root/'review/qwen35_window_v2_20261016';out.mkdir(exist_ok=True)
s=(old/'judge.py').read_text()
start=s.index('def parse(');end=s.index('\nBASE_PROMPT=',start)
s=s[:start]+'''def parse(raw,stage,n):
    m=re.search(r'\\{.*\\}',raw,re.S)
    if not m:raise ValueError('no JSON')
    return json.loads(m.group())
'''+s[end:]
start=s.index('BASE_PROMPT=');end=s.index('\ndef main():',start)
prompt='''Inspect TARGET_DESCRIPTION in the supplied chronological frame pairs. For EACH numbered frame, the full view and the crop show the SAME instant. The red SAM2 box is only a fallible location hint. Use visible pixels, not the box alone. First identify the target at frame 0, then follow its shape through motion. A cup or carton can rotate. Leaving the field of view is not identity corruption. Do NOT assume the object stays on the table merely because it started there.
Classify the target location separately at every supplied frame: tabletop (still supported by the initial table), airborne (visibly separated from table AND floor), ground (visibly contacting the floor), occluded, out_of_view, uncertain. Edge overhang with unclear contact must be uncertain, not airborne. Ground is the FLOOR, never the tabletop. If support/contact or identity cannot be resolved, use uncertain; do not guess. No landing is required to observe airborne motion. Do not infer future events after the final frame. Do not output a global verdict or score.
Return JSON with exactly one row per frame index, in order, using integer indices, e.g. {"frames":[{"index":0,"location":"tabletop","identity":"same"}],"reason":"brief specific visual evidence and any unresolved ambiguity"}. location must be one of the seven listed values (tabletop, airborne, ground, occluded, out_of_view, uncertain); identity must be same, uncertain, or lost. The example is only the format, not an answer; include all supplied frame indices.'''
s=s[:start]+'BASE_PROMPT='+repr(prompt)+'\nfrom boundary_window import select_frames, route_observations\n'+s[end:]
s=s.replace("if stage=='event':ids=np.linspace(0,end,13).round().astype(int).tolist()", "if stage=='event':ids=np.linspace(0,end,13).round().astype(int).tolist()")
s=s.replace("boxes={x['frame']:x['bbox_xyxy'] for x in tracking['frames']}","boxes={x['frame']:x['bbox_xyxy'] for x in tracking['frames']}\n                ids,selection=select_frames(tracking['frames'],end)\n                r['selection']=selection")
s=s.replace("content=[{'type':'image','image':img} for img in imgs]+[{'type':'text','text':PROMPTS[stage]+anchors}]", "content=[{'type':'text','text':PROMPTS[stage]}]\n                for k,idx in enumerate(ids):\n                    content += [{'type':'text','text':f'FRAME INDEX {k}, native frame {idx}, time {idx/fps:.3f}s. FULL VIEW:'},{'type':'image','image':imgs[2*k]},{'type':'text','text':f'FRAME INDEX {k}, SAME TIME, ENLARGED CROP:'},{'type':'image','image':imgs[2*k+1]}]")
s=s.replace('max_new_tokens=768','max_new_tokens=1536').replace('max_new_tokens=768','max_new_tokens=1536')
s=s.replace("roi=[430,40,630,240]","roi='per input manifest'")
s=s.replace("r['window']=row['window']","r['window']=row['window']\n                r['routing']=route_observations(r['judgement'],ids,boxes)")
s=s.replace("text_sha256=hashlib.sha256((PROMPTS[stage]+anchors).encode()).hexdigest()","text_sha256=hashlib.sha256(text.encode()).hexdigest()")
s=s.replace("'model_weight_fingerprints_reference'", "'model_weight_fingerprints_reference'")
(out/'judge.py').write_text(s,encoding='utf-8')
shutil.copyfile(root/'physedit/boundary_window.py',out/'boundary_window.py')
shutil.copyfile(old/'judge_inputs.jsonl',out/'inputs.jsonl')
shutil.copyfile(old/'launch_when_available.py',out/'launch_when_available.py')
print(out)
