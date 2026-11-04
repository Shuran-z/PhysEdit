"""Repair every current row, recording source-level evidence before publication."""
from pathlib import Path
import collections,copy,gzip,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import full_prompt_config_audit as audit
from scripts.preflight_current_prompt_upload import Configs
from scripts.build_current_prompt_publication import current_context,resolve_current
from scripts.repair_and_verify_all_prompts import source_controls,fact_patterns,texts_hash
from scripts.prompt_semantic_rules import *
from physedit.compact_prompt import counts,MODEL_BUDGETS
from physedit.prompt_contract import parameter_facts_sha
OUT=ROOT/'review/prompt_semantic_repair_20261102';SOURCE=ROOT/'review/h3_prompt_retrain_20261102/videos.jsonl.gz'
BASE='7af77078d39270a3c6ca7633bd373f357483b5f0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
def source(row,cfg):
 d=row.get('config_download') or {};vid=row['canonical_video_id']
 if d:raw,_=cfg.get(d['path'],d['member'],d['sha256'])
 else:raw=audit.HEADERS[vid]['header']
 if row['engine']=='genesis' and row['scene']=='T19' and row['sha256'] not in audit.T19:
  old=(row.get('current_render') or {}).get('encoding_compatibility',{}).get('source_sha256')
  if old in audit.T19:audit.T19[row['sha256']]=audit.T19[old]
 return raw,current_context(row,raw)
def main():
 OUT.mkdir(exist_ok=True);cfg=Configs();stats=collections.Counter();issues=[];unit_keys={};examples=[]
 with gzip.open(SOURCE,'rt',encoding='utf8') as src,gzip.open(OUT/'repaired_videos.jsonl.gz','wt',encoding='utf8',compresslevel=9) as dst,gzip.open(OUT/'SEMANTIC_CHANGE_LEDGER.jsonl.gz','wt',encoding='utf8',compresslevel=9) as ledger:
  for line in src:
   original=json.loads(line);row=copy.deepcopy(original);vid=row['canonical_video_id'];raw,ctx=source(original,cfg)
   for f in original['parameter_facts']:
    value,path=resolve_current(f[0],f[-2],raw,ctx,original);assert value is not None and audit.equal(value,f[-2]),(vid,f[0],path,value,f[-2]);stats['source_numeric_field_checks']+=1
   n,c,clock=source_controls(original,raw,ctx);assert n['source_control_clauses']==original['prompt_revision']['source_control_clauses']
   patterns=fact_patterns(original['parameter_facts']);texts=[];variants=[];unit_changes=[]
   for text in original['prompt_variants_en']:
    new,proof=repair_variant(text,original,raw,c,ctx,n,patterns);texts.append(new);variants.append(proof)
    stats['removed_duplicate_clauses']+=len(proof['removed']);stats['numeric_literals_reformatted']+=len(proof['numeric_changes']);stats['validated_retained_clauses']+=len(proof['clauses'])
   assert len(set(texts))==3
   for f in row['parameter_facts']:
    unit=expected_unit(f[0],f[-2]);unit_keys[f[0]]=unit;stats['dimension_checks']+=1
    if f[-1]!=unit:
     dimensional=canonical_old_unit(f[-1])!=unit
     unit_changes.append(dict(key=f[0],before=f[-1],after=unit,dimensional=dimensional));stats['dimensional_unit_corrections' if dimensional else 'unit_alias_normalizations']+=1;f[-1]=unit
   row['prompt_variants_en']=texts;row['prompt_en']=texts[0];row['prompt_variant_sha256']=texts_hash(texts);row['prompt_sha256']=row['prompt_variant_sha256'][0]
   row['prompt_variant_token_counts']=[counts(t) for t in texts];row['prompt_token_counts']=row['prompt_variant_token_counts'][0]
   assert all(all(tc[m]<=cap for m,cap in MODEL_BUDGETS.items()) for tc in row['prompt_variant_token_counts']),(vid,'token_budget',row['prompt_variant_token_counts'])
   row['parameter_facts_sha256']=parameter_facts_sha(row['parameter_facts']);row['prompt_policy']=VERSION
   row['prompt_revision']['source_control_clauses_exact']=n['source_control_clauses'];row['prompt_revision']['source_control_clauses']=[format_numbers(x) for x in n['source_control_clauses']];row['prompt_revision']['version']=VERSION
   row['full_numeric_audit']['semantic_repair']=dict(version=VERSION,unit_checks=len(row['parameter_facts']),source_values_unchanged=True,display_significant_digits=SIG,maximum_relative_display_error=RELATIVE_DISPLAY_BOUND,dedup_removed=sum(len(x['removed']) for x in variants),ledger_video_id=vid)
   proof=row['prompt_binding_evidence'];row['superseded_prompt_binding_evidence']=proof;row['prompt_binding_evidence']={**proof,'base_revision':BASE,'binding_method':'source_numeric_dimensional_bounded_display_semantic_dedup','parameter_facts_sha256':row['parameter_facts_sha256'],'prompt_sha256':row['prompt_variant_sha256']};row['prompt_binding_method']=row['prompt_binding_evidence']['binding_method']
   entry=dict(video_id=vid,units=unit_changes,variants=variants,old_prompt_sha256=original['prompt_variant_sha256'],new_prompt_sha256=row['prompt_variant_sha256'])
   ledger.write(json.dumps(entry,ensure_ascii=False,separators=(',',':'))+'\n');dst.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
   stats['videos']+=1;stats['variants']+=3
   if row['split']=='train_final':stats['training_videos']+=1
   if texts!=original['prompt_variants_en']:stats['text_changed_videos']+=1
   if any(x['dimensional'] for x in unit_changes):stats['dimensionally_corrected_videos']+=1
   if len(examples)<8 and (unit_changes or any(x['removed'] for x in variants)):
    examples.append(dict(id=vid,before=original['prompt_variants_en'][0],after=texts[0],unit_changes=unit_changes,removed=variants[0]['removed']))
   if stats['videos']%12000==0:print(json.dumps(dict(stats)),flush=True)
 assert stats['videos']==72000 and stats['training_videos']==45165
 dump(OUT/'UNIT_DIMENSION_REGISTRY.json',dict(policy=VERSION,keys=unit_keys,coverage=len(unit_keys),unknown_keys=0))
 dump(OUT/'GENERATION_REPORT.json',dict(status='GENERATED_PENDING_INDEPENDENT_VERIFICATION',base_revision=BASE,counts=dict(stats),issues=issues,examples=examples,manifest_sha256=sha(OUT/'repaired_videos.jsonl.gz'),ledger_sha256=sha(OUT/'SEMANTIC_CHANGE_LEDGER.jsonl.gz'),numeric_display_policy=dict(significant_digits=SIG,maximum_relative_error=RELATIVE_DISPLAY_BOUND,source_values_in_metadata_unchanged=True)))
 print(json.dumps(dict(stats)),flush=True)
if __name__=='__main__':main()
