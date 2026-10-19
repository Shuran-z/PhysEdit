import json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1];old=root/'review/qwen35_dual_20261017';out=root/'review/qwen35_six_triage_20261017';out.mkdir(exist_ok=True)
s=(old/'judge.py').read_text();a=s.index('BASE_PROMPT=');b=s.index('\ndef main():',a)
prompt='''Inspect TARGET_DESCRIPTION. Each numbered frame has synchronized full view and crop. Boxes are SAM2 hints, NOT proof of identity or support. Judge only supplied pixels, not expected physics. Be concise.
Task 1 quality: measurable, unmeasurable, or uncertain. Definite fusion/disintegration/identity replacement preventing event measurement is unmeasurable. Ordinary occlusion, rotation, leaving crop or camera view is NOT identity loss. Use full view to resolve crop absence. Visible physical errors like interpenetration are not automatically unmeasurable. Cite at least two frame indices for rejecting corruption.
Task 2 independent events: departure=complete loss of initial table support; descent=downward motion after complete detachment, no landing required; landing=contact with FLOOR, not tabletop. Overhang, downward rotation with possible edge contact is uncertain. Give confidence for EACH event, evidence integer FRAME indices and brief reason. For descent yes cite two distinct times with target visible descending. For no cite early and late evidence and ensure no contradictory middle event. If landing is not seen, use not_observed, not no. Do not extrapolate after disappearance or clip end. No overall frame-by-frame table is required.
Return compact JSON ONLY: {"quality":{"status":"measurable","failure":"none","confidence":0.0,"evidence":[0,12],"reason":"specific evidence"},"events":{"departure":{"label":"uncertain","relation":"uncertain","confidence":0.0,"evidence":[0,12],"reason":"specific evidence"},"descent":{"label":"uncertain","relation":"uncertain","confidence":0.0,"evidence":[0,12],"reason":"specific evidence"},"landing":{"label":"not_observed","relation":"unobservable","confidence":0.0,"evidence":[0,12],"reason":"specific evidence"}}}.
Allowed status measurable/unmeasurable/uncertain; failure none/fusion/identity_loss/severe_corruption/uncertain. Event label yes/no/not_observed/uncertain; relation supported/detached/floor_contact/uncertain/unobservable. Numbers shown are placeholders, not answers. Confidence is uncalibrated confidence in your observation, not event probability. When quality is unmeasurable events may be uncertain. Use integer evidence indices, put explanation only in reason.'''
s=s[:a]+'BASE_PROMPT='+repr(prompt)+'\nfrom boundary_window import select_frames\nfrom boundary_triage import route as route_dual\n'+s[b:]
s=s.replace('max_new_tokens=2400','max_new_tokens=1300')
(out/'judge.py').write_text(s)
for name in ('boundary_window','boundary_triage'):shutil.copyfile(root/f'physedit/{name}.py',out/f'{name}.py')
shutil.copyfile(old/'launch_when_available.py',out/'launch_when_available.py')
rows=[json.loads(l) for l in (root/'review/qwen35_sam2_six_20261016/inputs.jsonl').read_text().splitlines()]
for r in rows:r.update(roi=[430,40,630,240],target='the closed laptop initially on the tabletop to the right of the green book',window='original full generated video')
(out/'inputs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
