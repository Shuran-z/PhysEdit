from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1];old=root/'review/qwen35_window_v2_20261016'
out=root/'review/qwen35_dual_20261017';out.mkdir(exist_ok=True)
s=(old/'judge.py').read_text();start=s.index('BASE_PROMPT=');end=s.index('\ndef main():',start)
prompt='''Inspect TARGET_DESCRIPTION. Each indexed full image and crop are the SAME time. SAM2 boxes are fallible location hints, not identity or contact truth. Two tasks:
QUALITY: determine whether target events can be measured. Disappearance by fusion, replacement or disintegration is unmeasurable. Ordinary occlusion, rotation and leaving view are not corruption. Visible interpenetration is a physical anomaly, not automatically unmeasurable. If unsure use uncertain.
EVENTS: independently observe departure from initial table support, descent after departure, and landing on FLOOR. A tilt or overhang is not proven departure. Landing is unnecessary for descent. Not seeing landing is not proof it never happens. No reference outcome is supplied; judge only this time window.
First classify EACH indexed frame: location tabletop/airborne/ground/occluded/out_of_view/uncertain; identity same/uncertain/lost. Then provide each event's own label, self-confidence 0..1, evidence FRAME INDICES (integers, not image indices or timestamps), and concrete reason. Confidence is confidence in your stated label, not probability of the event occurring. If uncertain use uncertain and do not guess. Cite at least two distinct times. Keep JSON compact.
Return {"frames":[{"index":0,"location":"tabletop","identity":"same"}],"quality":{"status":"measurable|unmeasurable|uncertain","failure":"none|identity_loss|fusion|severe_corruption|uncertain","confidence":0.0,"evidence":[],"reason":"...","physical_anomalies":[]},"events":{"departure":{"label":"yes|no|not_observed|uncertain","confidence":0.0,"evidence":[],"reason":"..."},"descent":{"label":"yes|no|not_observed|uncertain","confidence":0.0,"evidence":[],"reason":"..."},"landing":{"label":"yes|no|not_observed|uncertain","confidence":0.0,"evidence":[],"reason":"..."}}}. Replace alternatives by a single value. Include every frame index, not just example row. A no label applies only within the observed window and requires evidence; prefer not_observed if landing cannot be resolved.'''
s=s[:start]+'BASE_PROMPT='+repr(prompt)+'\nfrom boundary_window import select_frames\nfrom boundary_dual_judge import route_dual\n'+s[end:]
s=s.replace("route_observations(r['judgement'],ids,boxes)","route_dual(r['judgement'],ids,boxes)").replace('max_new_tokens=1536','max_new_tokens=2400')
(out/'judge.py').write_text(s)
shutil.copyfile(root/'physedit/boundary_window.py',out/'boundary_window.py')
d=(root/'physedit/boundary_dual_judge.py').read_text().replace('from physedit.boundary_window','from boundary_window')
(out/'boundary_dual_judge.py').write_text(d)
for f in ('inputs.jsonl','launch_when_available.py'):shutil.copyfile(old/f,out/f)
