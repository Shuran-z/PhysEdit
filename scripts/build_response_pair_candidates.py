"""Enumerate same-seed/prompt candidates; never certify from selected facts alone."""
import csv,gzip,hashlib,itertools,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'review/response_cohorts_20261030'
tasks=json.loads(gzip.decompress((O/'live_tasks.json.gz').read_bytes()))
sources=[json.loads(l) for l in (R/'review/prompt_length_natural_20261030/audit/source_inputs_only.jsonl').open(encoding='utf8')]
def facts(s):
 f=s['selected_facts']
 return {v['label']:v['value'] for v in f} if isinstance(f,list) else f
def save(name,rows):
 if not rows:return
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
slots={(t['payload']['model'],t['payload']['clip_id'],t['payload']['prompt_variant'],t['payload']['seed']):t for t in tasks}
models=sorted({t['payload']['model'] for t in tasks});combinations=sorted({(t['payload']['prompt_variant'],t['payload']['seed']) for t in tasks})
pairs=[];outputs=[]
for a,b in itertools.combinations(sources,2):
 if a['clip_id'][:3]!=b['clip_id'][:3]:continue
 fa,fb=facts(a),facts(b);different=[k for k in fa.keys()|fb.keys() if fa.get(k)!=fb.get(k)]
 if len(different)!=1:continue
 k=different[0];pid=a['clip_id']+'__'+b['clip_id']
 context_equal=a['objects']==b['objects'] and a['declared_control_inputs']==b['declared_control_inputs']
 pairs.append({'pair_id':pid,'case_a':a['clip_id'],'case_b':b['clip_id'],'changed_selected_fact':k,'value_a':json.dumps(fa.get(k)),'value_b':json.dumps(fb.get(k)),'object_and_control_snapshot_equal':context_equal,'full_config_control_certified':False,'blocker':'Full source configuration/camera/solver/timing and exact submitted text differences require certification; selected facts alone insufficient.'})
 for m in models:
  for variant,seed in combinations:
   ta=slots.get((m,a['clip_id'],variant,seed));tb=slots.get((m,b['clip_id'],variant,seed))
   outputs.append({'pair_id':pid,'model':m,'prompt_variant':variant,'seed':seed,'task_a':ta['id'] if ta else '', 'task_b':tb['id'] if tb else '', 'both_present':bool(ta and tb),'missing_case_ids':'|'.join(x for x,t in [(a['clip_id'],ta),(b['clip_id'],tb)] if not t),'source_control_certified':False})
save('single_selected_fact_candidates.csv',pairs);save('candidate_output_coverage.csv',outputs)
summary={'candidate_pairs':len(pairs),'snapshot_equal_pairs':sum(x['object_and_control_snapshot_equal'] for x in pairs),'complete_same_seed_prompt_output_pairs':sum(x['both_present'] for x in outputs),'model_seed_prompt_slots':len(outputs),'formal_controlled_pairs_certified':0,'source_snapshot_sha256':hashlib.sha256((R/'review/prompt_length_natural_20261030/audit/source_inputs_only.jsonl').read_bytes()).hexdigest()}
(O/'parameter_candidates_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
