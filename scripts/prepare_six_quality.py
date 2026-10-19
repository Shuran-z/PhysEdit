from pathlib import Path
import shutil,json,ast
root=Path(__file__).resolve().parents[1];old=root/'review/qwen35_six_triage_20261017';out=root/'review/qwen35_six_quality_20261017';out.mkdir(exist_ok=True)
s=(old/'judge.py').read_text();a=s.index('BASE_PROMPT=');b=s.index('\ndef main():',a)
prompt='''Quality-only inspection of TARGET_DESCRIPTION. Do NOT decide falling, landing, or whether the physics is correct. Ignore any inferred outcome. Inspect actual pixels across full frames and enlarged crops. Boxes are SAM2 guesses and may follow background after the target disappears.
Check (1) target identity and shape continuity; (2) whether the supporting table geometry remains interpretable for contact measurements. Definite fusion into background, disintegration, replacement, or severe scene geometry/texture collapse that prevents reliable target/support measurement is unmeasurable. Do not rationalize melting table or fused target as normal camera movement. Ordinary rotation, partial occlusion, leaving the crop/view, or a cleanly visible physically wrong motion is NOT by itself corruption. If unclear use uncertain. A similar patch at the end is not proof of identity; require temporal continuity.
Return JSON only {"quality":{"status":"measurable|unmeasurable|uncertain","failure":"none|fusion|identity_loss|severe_corruption|uncertain","confidence":0.0,"evidence":[0,12],"reason":"specific visible continuity/corruption evidence","target_integrity":"intact|corrupted|uncertain","support_integrity":"intact|corrupted|uncertain"}}. Select one value per enum. Confidence is self-report, not a correctness guarantee. Cite actual integer FRAME indices, at least two distinct times for definite corruption. Do not output events. All numerical examples are placeholders.'''
s=s[:a]+'BASE_PROMPT='+repr(prompt)+'\nfrom boundary_window import select_frames\nfrom boundary_triage import route as route_dual\n'+s[b:]
s=s.replace('max_new_tokens=1300','max_new_tokens=600')
original=ast.parse((old/'judge.py').read_text())
event_prompt=next(ast.literal_eval(n.value) for n in original.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BASE_PROMPT' for t in n.targets))
s=s.replace('def main():','EVENT_PROMPT='+repr(event_prompt)+'\n\ndef main():')
s=s.replace("PROMPTS[stage]=BASE_PROMPT.replace('TARGET_DESCRIPTION',row['target'])","PROMPTS[stage]=(EVENT_PROMPT if row.get('task')=='event_retry' else BASE_PROMPT).replace('TARGET_DESCRIPTION',row['target'])")
s=s.replace('max_new_tokens=600,do_sample=False',"max_new_tokens=(1600 if row.get('task')=='event_retry' else 600),do_sample=False")
(out/'judge.py').write_text(s)
for f in ('inputs.jsonl','boundary_triage.py','boundary_window.py','launch_when_available.py'):shutil.copyfile(old/f,out/f)
rows=[json.loads(l) for l in (out/'inputs.jsonl').read_text().splitlines()]
r=dict(next(r for r in rows if r['sample_id']=='clip04'));r.update(sample_id='clip04_event_retry',tracking_id='clip04',task='event_retry');rows.append(r)
(out/'inputs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
