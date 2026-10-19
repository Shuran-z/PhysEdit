"""Prepare bounded adaptive crop-to-full diagnostic without expected labels."""
import ast
import shutil
from pathlib import Path

base=Path(__file__).resolve().parents[1]
old=base/'review/qwen35_crop_prompt_v2_20261016'
out=base/'review/qwen35_cascade_20261016'
out.mkdir(exist_ok=True)
src=(old/'judge.py').read_text(encoding='utf-8')
full_prompt='''You are a second-stage video measurement screener. Inspect this FULL FRAME sequence independently. No reference outcome or previous verdict is provided. Track the closed laptop initially on the table to the right of the green book.
First check scene and target continuity across early, middle and late frames. Definite severe texture/geometry collapse, fusion into background, disintegration, or replacement that prevents tracking the target warrants REJECT immediately, even if the camera also moves. Do not explain away visible corruption as ordinary camera panning. Ordinary camera motion, perspective, rotation, shadows, or changing visible color alone are not corruption.
Next inspect the table edge and region below it. A rotated laptop can become a narrow dark strip with a different underside. Absence alone is NOT identity loss. If occlusion or leaving the visible image plausibly explains loss of visibility and there is no positive corruption evidence, use REVIEW. A laptop tilted or suspended against the table edge with uncertain support is HANGING: review, fall=null. Do not demand landing to identify a clear fall: visible support loss and downward motion suffice. Do not assume that being asked about a fall means one must occur.
Decide from visible evidence, not a desired outcome. An observable physically wrong result is usable. Usable requires clear fall=1 (tracked support loss and descent) or fall=0 (clearly supported throughout). Review only when unresolved evidence prevents deciding. Reject for definite scene corruption or identity destruction preventing measurement; explain the positive evidence, not merely the absence of the object. For a rejection cite an early/middle transition showing the corruption, not only the first and last frame. No aesthetic judgments.
Return JSON only with these fields:
observation: trackable / hanging / occluded / out_of_view / identity_loss / scene_corruption / uncertain;
identity: maintained / lost / uncertain;
event_gate: usable / reject / review;
inversion_gate: candidate / reject / review (candidate requires visibly trackable contact-free descent with a stable camera; reject for definite corruption or clearly absent free fall; review for uncertainty; candidate is not validated inversion);
fall: 0 / 1 / null (null for uncertain or rejected cases);
reason: concrete visible observations and why the selected decision follows;
evidence: at least TWO entries with distinct sample_index, actual time_s from supplied anchors, and description. Choose one enum value per field. Never invent objects, motion, or continuity to fill gaps.'''
src=src.replace('\n\ndef sha', '\n\nFULL_PROMPT='+repr(full_prompt)+'\n\ndef sha',1)
src=src.replace("(root/'prompt.txt').write_text(PROMPT)","(root/'prompt.txt').write_text(PROMPT)\n    (root/'full_prompt.txt').write_text(FULL_PROMPT)")
src=src.replace("scope='6 calls: same crop inputs, revised prompt v2; development only'", "scope='adaptive: six crop calls then full-frame recheck for uncertain cases; development only',full_prompt_sha256=sha(root/'full_prompt.txt')")
src=src.replace("view_order=['crop']", "view_order=['crop','conditional_full']")
src=src.replace("budget_note='identical crop arrays and decoding to prior crop arm; prompt changed'", "budget_note='crop prompt unchanged from v2; full review adds inference cost; no expected outcomes supplied'")
src=src.replace("start=time.time();record=", "prompt=PROMPT if row['view']=='crop' else FULL_PROMPT\n            start=time.time();record=")
src=src.replace('(PROMPT+anchors)', '(prompt+anchors)').replace("'text':PROMPT+anchors", "'text':prompt+anchors")
src=src.replace("record['elapsed_s']=time.time()-start", """# Explicit routing; invalid evaluator output is never a generation rejection.
            j=record.get('judgement',{})
            inconsistent=(j.get('event_gate')=='usable' and (j.get('fall') is None or j.get('identity')!='maintained'))
            uncertain=(record['status']!='ok' or j.get('event_gate')=='review' or j.get('identity')=='uncertain' or inconsistent)
            record['needs_full_review']=row['view']=='crop' and uncertain
            if record['needs_full_review']:
                rows.append(dict(row,view='full'))
            record['elapsed_s']=time.time()-start""")
(out/'judge.py').write_text(src,encoding='utf-8')
(out/'full_prompt.txt').write_text(full_prompt,encoding='utf-8')
for name in ('inputs.jsonl','local_mapping.json','prompt.txt'):
    shutil.copyfile(old/name,out/name)
compile(src,str(out/'judge.py'),'exec')
print('Prepared adaptive runner')
