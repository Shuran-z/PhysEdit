"""Freeze a single revised judge prompt; retain prior crop inputs and decoding."""
from pathlib import Path
import shutil

base = Path(__file__).resolve().parents[1]
old = base / 'review/qwen35_view_ablation_20261016'
out = base / 'review/qwen35_crop_prompt_v2_20261016'
out.mkdir(exist_ok=True)
prompt = '''You are screening a generated video for measurement usability, not aesthetic quality or correct physics. Track the SAME closed laptop initially on the table to the right of the green book. This is a fixed spatial crop: leaving this crop is not proof of disappearance from the world. No reference outcome is supplied.
First inspect the target over time. A rotating laptop can become a narrow dark edge or expose a differently colored underside. Color or apparent shape changes alone do not prove replacement. Search near and below the table edge before deciding it is absent. Describe only visible evidence; do not invent a camera motion or an object to explain uncertainty.
Distinguish these observable conditions:
- hanging: target remains at/against the edge, tilted or partly below the tabletop, with support/contact uncertain. Tilting or lowering alone does not establish complete support loss.
- occluded: a visible surface plausibly hides part/all of the target; continuity may remain uncertain. Occlusion is not identity destruction.
- out_of_crop: target may have left the visible region; this is not identity destruction.
- trackable: target can be followed, including rotation or downward motion.
- identity_loss: positive visible evidence of fusion into background, disintegration, or discontinuous replacement that prevents following the original target. Mere absence in later frames is insufficient.
- uncertain: evidence cannot distinguish the above.
Return independent decisions:
identity: maintained / lost / uncertain. Use lost only with positive identity_loss evidence. When absence could be occlusion, rotation or leaving the crop, use uncertain rather than lost.
event_gate: usable / reject / review. Usable requires sufficient evidence for fall=0 or fall=1 within this observation window. Reject requires definite identity destruction or definite scene corruption that prevents event measurement. Otherwise review. Hanging with uncertain support must be review, fall=null; do not call it identity loss. An observable physically wrong result is still usable.
fall: 1 only when the tracked target clearly loses tabletop support and moves down; 0 only when the observed sequence clearly shows it remains supported throughout the window. Use null for hanging, unresolved occlusion, unclear support, or identity loss. Do not infer fall from disappearance or requested physics.
inversion_gate: candidate only for a visibly trackable contact-free falling segment with sufficiently stable camera; reject for definite corruption/identity loss or clearly absent free fall; review when contact, visibility or camera is uncertain. Candidate is NOT a validated gravity fit.
Use review when the evidence is insufficient, but do not send clear trackable falls or definite visible identity destruction to review by default. Cite at least TWO distinct sampled indices at the supplied anchor times; include the last confidently visible target and the later decisive or ambiguous observation. If choosing lost/reject, describe the positive corruption evidence and why mere occlusion or leaving the crop does not explain it.
Return JSON only: {"observation":"trackable / hanging / occluded / out_of_crop / identity_loss / uncertain", "identity":"maintained / lost / uncertain", "event_gate":"usable / reject / review", "inversion_gate":"candidate / reject / review", "fall":null, "reason":"specific visible observations and uncertainty", "evidence":[{"sample_index":0,"time_s":0.0,"description":"specific observation"},{"sample_index":25,"time_s":0.0,"description":"specific later observation"}]}. Choose one value per field, not a list. Do not copy placeholder observations.'''
source = (old / 'judge.py').read_text(encoding='utf-8')
start = source.index('PROMPT=')
end = source.index('\n\ndef sha', start)
source = source[:start] + 'PROMPT=' + repr(prompt) + source[end:]
source = source.replace("for view in ('full','crop','both')", "for view in ('crop',)")
source = source.replace("scope='18 calls: six clips x full/crop/both; development only'", "scope='6 calls: same crop inputs, revised prompt v2; development only'")
source = source.replace("view_order=['full','crop','both']", "view_order=['crop']")
source = source.replace("budget_note='same per-view pixel cap; both has more visual tokens'", "budget_note='identical crop arrays and decoding to prior crop arm; prompt changed'")
(out / 'judge.py').write_text(source, encoding='utf-8')
(out / 'prompt.txt').write_text(prompt, encoding='utf-8')
for name in ('inputs.jsonl', 'local_mapping.json'):
    shutil.copyfile(old / name, out / name)
print(out)
