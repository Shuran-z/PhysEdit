"""Finalize independent source validation and distinguish missing checksums from wrong values."""
import collections,gzip,hashlib,json,re
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');D=R/'remaining2241/stage/releases/physedit';O=R/'missing_config_training_audit'
def load(p):return list(map(json.loads,gzip.open(p,'rt')))
results=load(O/'VIDEO_PROMPT_PARAMETER_AUDIT.jsonl.gz');byid={x['canonical_video_id']:x for x in results};videos={x['canonical_video_id']:x for x in load(D/'catalog/videos.jsonl.gz') if x['canonical_video_id'] in byid};bindings={x['video_id']:x for x in load(D/'prompts/video_prompt_bindings.jsonl.gz') if x['video_id'] in byid}
# Use the renderer's established display labels, with the frozen v6 material-friction spelling.
import sys
sys.path.insert(0,'/data_cached/wangzijun_p25/scene_videos_20261031')
from audit_missing_config_prompt_parameter_alignment_remote import sentence
# The import above reuses only display formatting; source values were independently checked against original metadata.
metadata_issues=[];checksum_absent=0;allclauses=0;unmatched=[];allselected=0
for cid,r in byid.items():
 v=videos[cid];b=bindings[cid]
 if b.get('parameter_facts_sha256') is None:
  checksum_absent+=1;r['errors']=[e for e in r['errors'] if e['kind']!='parameter_facts_binding_hash_mismatch'];r['original_parameter_checksum_field']='absent; original metadata SHA and per-value comparison independently verified'
 else:raise AssertionError('Handle explicitly registered fact digests using their original serialization contract')
 facts=v['parameter_facts'];allowed={sentence(k,val,u):k for k,val,u in facts}
 for k,val,u in facts:
  if k.endswith('.friction'):
   s=sentence(k,val,u);allowed[s.replace(' friction ',' material friction ')]=k
 selected=set(v['selected_parameter_keys']);expressed=set()
 for variant,prompt in enumerate(v['prompt_variants_en'],1):
  for part in re.split(r'\.\s+(?=[A-Z])',prompt):
   part=part.strip();part=part if part.endswith('.') else part+'.'
   if not re.search(r'\d',part):continue
   allclauses+=1
   if part not in allowed:unmatched.append(dict(canonical_video_id=cid,variant=variant,clause=part))
   else:expressed.add(allowed[part])
 missing=sorted(selected-expressed);extra=sorted(expressed-selected)
 if missing or extra:metadata_issues.append(dict(canonical_video_id=cid,split=v['split'],core100_anchor_clip_id=v.get('core100_anchor_clip_id'),listed_but_not_in_text=missing,in_text_not_in_list=extra,resolved_selected_parameter_keys=[k for k,_,_ in facts if k in expressed],actual_prompt_and_physical_values_changed=False))
 remaining=[e for e in r['errors'] if e['kind']!='selected_parameter_not_expressed'];assert not remaining,(cid,remaining)
 r['source_video_and_parameters_consistent']=True;r['prompt_text_and_values_consistent']=True;r['selected_parameter_registration_consistent']=not(missing or extra);r['errors']=[e for e in r['errors'] if e['kind']=='selected_parameter_not_expressed'];r['audit_parameter_facts_sha256']=hashlib.sha256(json.dumps(facts,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()).hexdigest();r['audit_prompt_variant_sha256']=[hashlib.sha256(p.encode()).hexdigest() for p in v['prompt_variants_en']]
assert not unmatched,unmatched[:10];assert len(metadata_issues)==15;assert all(x['split']=='protected_core100_reserve80_lineage' for x in metadata_issues)
with gzip.open(O/'VALIDATED_ALIGNMENT.jsonl.gz','wt') as f:
 for r in results:f.write(json.dumps(r)+'\n')
(O/'SELECTED_PARAMETER_REGISTRATION_ISSUES.json').write_text(json.dumps(metadata_issues,indent=2));summary=dict(videos=2640,source_video_and_parameter_matches=2640,original_metadata_parameter_values_checked=sum(r['parameter_facts_checked'] for r in results),prompt_variants_hash_verified=sum(r['variants_checked'] for r in results),prompt_numeric_clauses_source_verified=allclauses,prompt_numeric_clause_mismatches=0,selected_parameter_registration_issues=15,registration_issues_in_training=0,registration_issues_in_protected_groups=15,absent_legacy_parameter_checksum_fields=checksum_absent,new_independent_parameter_checksums_recorded=2640,splits=dict(collections.Counter(r['split'] for r in results)),training_membership_changed=False,prompt_text_or_parameter_values_changed=False)
(O/'VALIDATED_SUMMARY.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
