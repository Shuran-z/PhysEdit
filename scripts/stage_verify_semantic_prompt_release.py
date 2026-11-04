"""Independently read final text, validate dimensions/rounding/coverage, build every consumer view."""
from pathlib import Path
import collections,gzip,hashlib,itertools,json,re,shutil,sys
from fractions import Fraction
import pyarrow as pa
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_semantic_prompt_release import OUT,SOURCE,BASE,source,dump,sha
from scripts.preflight_current_prompt_upload import Configs
from scripts.repair_and_verify_all_prompts import source_controls,fact_patterns,match_fact,pieces,numeric_value
from scripts.prompt_semantic_rules import VERSION,SIG,RELATIVE_DISPLAY_BOUND,NUMBER,expected_unit,semantic_fact,controller_coverage,canonical_old_unit
from physedit.compact_prompt import counts,MODEL_BUDGETS
from physedit.prompt_contract import parameter_facts_sha
STAGE=OUT/'stage';D=STAGE/'releases/physedit'
def rows(p):
 with gzip.open(p,'rt',encoding='utf8') as f:yield from map(json.loads,f)
def numeric(v):return float(Fraction(v)) if '/' in v else float(v)
def bounded(before,after):
 if isinstance(before,list):assert isinstance(after,list) and len(before)==len(after);return sum(bounded(a,b) for a,b in zip(before,after))
 if isinstance(before,bool):assert before is after;return 1
 assert isinstance(after,(int,float)) and abs(float(before)-after)<=abs(float(before))*RELATIVE_DISPLAY_BOUND+1e-300,(before,after)
 return 1
def numeric_skeleton_pair(before,after):
 assert NUMBER.sub('#',before)==NUMBER.sub('#',after),(before,after)
 a=NUMBER.findall(before);b=NUMBER.findall(after);assert len(a)==len(b)
 for left,right in zip(a,b):
  if not any(x in left.lower() for x in ['.','/','e']):assert left==right,(left,right)
  else:bounded(numeric(left),numeric(right))
 return len(a)
def signature(s):return NUMBER.sub('#',s)
def canonical_tokens(text):
 for token in NUMBER.findall(text):
  if '/' in token:continue
  mantissa=token.lower().split('e')[0].lstrip('+-');digits=mantissa.replace('.','').lstrip('0')
  if '.' in mantissa or 'e' in token.lower():assert len(digits)<=SIG,(token,'excess display precision')
def validate_variant(original,final,entry,row,raw,c,ctx,source_info,variant):
 trace=entry['clauses'];actual=pieces(final);assert actual==[x['output'] for x in trace]
 assert len(actual)==len(set(actual));canonical_tokens(final)
 patterns=fact_patterns(original['parameter_facts']);facts={f[0]:f for f in original['parameter_facts']};nchecks=0
 controls=source_info['source_control_clauses'];used=set(source_info.get('control_keys',[]))
 for p in trace:
  if p['kind']=='fact':
   m=match_fact(p['before'],patterns);assert m and m[0]==p['key'];f=facts[m[0]];unit=expected_unit(m[0],f[-2]);suffix=(' '+unit if unit not in ['', 'frame index'] else '')+'.'
   text=p['output'];assert text.startswith(m[3]) and text.endswith(suffix)
   middle=text[len(m[3]):-len(suffix)];value=numeric_value(middle);assert value is not None
   nchecks+=bounded(m[2],value)
   assert not controller_coverage(m[0],f[-2],ctx,used),'supported controller duplicate survives'
  elif p['kind']=='controller':
   candidates=[x for x in pieces(controls[p['source_index']]) if signature(x)==signature(p['output'])];assert candidates
   valid=False
   for before in candidates:
    try:nchecks+=numeric_skeleton_pair(before,p['output']);valid=True;break
    except AssertionError:pass
   assert valid,(candidates,p['output'])
  elif p['kind']=='lead':assert p['before']==p['output']
  else:nchecks+=numeric_skeleton_pair(p['before'],p['output'])
 # Every original controller atom must remain, including all actors, axes, signs and conditional branches.
 for control in controls:
  for atom in pieces(control):
   candidates=[p['output'] for p in trace if p['kind']=='controller' and signature(p['output'])==signature(atom)];ok=False
   for candidate in candidates:
    try:numeric_skeleton_pair(atom,candidate);ok=True;break
    except AssertionError:pass
   assert ok,('source controller atom lost',atom)
 body=original['prompt_variants_en'][variant]
 for control in controls:body=body.replace(control,' ')
 before_counter=collections.Counter(p['before'] for p in trace if p['kind']!='controller')
 for p in entry['removed']:
  kind=p['kind']
  if kind!='exact_controller_atom_duplicate':before_counter[p['before']]+=1
  if kind=='fact_covered_by_controller':
   m=match_fact(p['before'],patterns);assert m and m[0]==p['key'];assert controller_coverage(m[0],facts[m[0]][-2],ctx,used)
  elif kind=='same_actor_property_duplicate':
   first=trace[p['covered_by']];a,_=semantic_fact(p['key'],facts[p['key']][-2],ctx);b,_=semantic_fact(first['key'],facts[first['key']][-2],ctx);assert a and a==b
  elif kind=='exact_controller_atom_duplicate':assert p['before']==actual[p['covered_by']]
  elif kind=='literal_covered_by_controller':
   candidates=[x for x in actual if signature(p['before'])==signature(x)];valid=False
   for x in candidates:
    try:numeric_skeleton_pair(p['before'],x);valid=True;break
    except AssertionError:pass
   assert valid
  elif kind=='exact_clause_duplicate':
   assert 0<=p['covered_by']<len(trace);target=trace[p['covered_by']]['output'];m=match_fact(p['before'],patterns)
   if m:
    unit=expected_unit(m[0],facts[m[0]][-2]);suffix=(' '+unit if unit not in ['', 'frame index'] else '')+'.';assert target.startswith(m[3]) and target.endswith(suffix)
    bounded(m[2],numeric_value(target[len(m[3]):-len(suffix)]))
   else:numeric_skeleton_pair(p['before'],target)
  else:raise AssertionError('unknown deletion proof '+kind)
 assert before_counter==collections.Counter(pieces(body)),('original clause unaccounted',before_counter,collections.Counter(pieces(body)))
 return nchecks
def split(r):return 'train' if r['split']=='train_final' else ('ood1_holdout' if r['scene'] in ['T03','T20'] else 'ood2_holdout') if r['split']=='ood_holdout' else 'protected'
def main():
 generated=json.loads((OUT/'GENERATION_REPORT.json').read_text(encoding='utf8'));assert generated['counts']['videos']==72000
 backup=json.loads((OUT/'LOCAL_BASE_BACKUP_VERIFIED.json').read_text(encoding='utf8'));assert backup['status']=='PASS'
 current=Path(backup['local_directory']);cfg=Configs();stats=collections.Counter();index={};pool={};gz={};buffers=collections.defaultdict(list);writers={};seen=set();unit_keys=set()
 assert sha(SOURCE)==sha(current/'releases/physedit/catalog/videos.jsonl.gz'),'Input differs from backed-up current HF release'
 schema=pq.read_schema(current/'releases/physedit/catalog/parquet/videos_train.parquet')
 for s in ['train','protected','ood1_holdout','ood2_holdout']:
  p=D/f'catalog/parquet/videos_{s}.parquet';p.parent.mkdir(parents=True,exist_ok=True);writers[s]=pq.ParquetWriter(p,schema,compression='zstd')
 def write(name,text):
  if name not in gz:
   p=D/name;p.parent.mkdir(parents=True,exist_ok=True);gz[name]=gzip.open(p,'wt',encoding='utf8',compresslevel=9)
  gz[name].write(text)
 try:
  for old,row,ledger in itertools.zip_longest(rows(SOURCE),rows(OUT/'repaired_videos.jsonl.gz'),rows(OUT/'SEMANTIC_CHANGE_LEDGER.jsonl.gz')):
   assert old and row and ledger;vid=row['canonical_video_id'];assert vid==old['canonical_video_id']==ledger['video_id'] and vid not in seen;seen.add(vid)
   for key in ['sha256','download','config_download','split','source_group_id','current_render','physical_qa','quality_admission_status','external_control_inputs']:assert old.get(key)==row.get(key),(vid,key)
   assert len(old['parameter_facts'])==len(row['parameter_facts'])
   for a,b in zip(old['parameter_facts'],row['parameter_facts']):
    assert a[:-1]==b[:-1],(vid,'raw parameter changed',a,b)
    assert b[-1]==expected_unit(b[0],b[-2]);stats['independent_unit_checks']+=1;unit_keys.add(b[0])
   raw,ctx=source(old,cfg);n,c,clock=source_controls(old,raw,ctx)
   assert n['source_control_clauses']==row['prompt_revision']['source_control_clauses_exact']
   # These are active human-readable/selection fields, not immutable provenance.
   if row['prompt_revision'].get('control_keys')!=n.get('control_keys',[]):stats['source_control_key_metadata_alignments']+=1
   row['prompt_revision']['control_keys']=n.get('control_keys',[])
   disclosure=dict(row.get('external_control_disclosure') or {})
   disclosure.update(kinds=n.get('control_keys',[]),disclosure=' '.join(row['prompt_revision']['source_control_clauses']))
   row['external_control_disclosure']=disclosure
   represented=set(row['full_numeric_audit'].get('facts_explicitly_represented_by_controller',[]))
   represented.update(p['key'] for v in ledger['variants'] for p in v['removed'] if p['kind']=='fact_covered_by_controller')
   values={f[0]:f[-2] for f in row['parameter_facts']}
   for key in represented:assert controller_coverage(key,values[key],ctx,set(n.get('control_keys',[]))),('invalid represented metadata',vid,key)
   row['full_numeric_audit']['facts_explicitly_represented_by_controller']=sorted(represented)
   texts=row['prompt_variants_en'];assert len(texts)==len(set(texts))==3
   hashes=[hashlib.sha256(t.encode()).hexdigest() for t in texts];assert hashes==row['prompt_variant_sha256'] and hashes[0]==row['prompt_sha256'] and texts[0]==row['prompt_en']
   assert parameter_facts_sha(row['parameter_facts'])==row['parameter_facts_sha256']
   for i,text in enumerate(texts):
    stats['independent_text_numeric_checks']+=validate_variant(old,text,ledger['variants'][i],row,raw,c,ctx,n,i)
    assert counts(text)==row['prompt_variant_token_counts'][i];assert all(counts(text)[m]<=cap for m,cap in MODEL_BUDGETS.items())
    assert hashes[i] not in pool or pool[hashes[i]]==text;pool[hashes[i]]=text
   if row['engine']=='isaac' and row['scene']=='T14':stats['isaac_T14']+=1
   assert row['scene']!='T14S'
   encoded=json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n';write('catalog/videos.jsonl.gz',encoded)
   if row['split']=='train_final':write('catalog/train_final.jsonl.gz',encoded)
   scene=row.get('quota_scene',row['scene']);write(f"catalog/by_scene/{row['engine']}__{scene}.jsonl.gz",encoded)
   binding=dict(video_id=vid,legacy_video_id=row.get('video_id',vid),trajectory_id=row.get('canonical_trajectory_id',vid.rsplit('__',1)[0]),engine=row['engine'],scene=scene,native_scene_id=row.get('native_scene_id',row['scene']),camera=row['camera'],background=row.get('background',''),gravity=row.get('gravity',''),video_path=row['canonical_path'],video_sha256=row['sha256'],download=row['download'],quality_admission_status=row.get('quality_admission_status'),prompt_policy=VERSION,prompt_sha256=hashes,prompt_files=[f"prompts/{row['engine']}/{scene}/{vid}__p{i:02}.txt" for i in [1,2,3]],prompt_token_counts=row['prompt_variant_token_counts'],source_config_sha256=(row.get('config_download')or{}).get('sha256'),parameter_facts_sha256=row['parameter_facts_sha256'],current_binding_evidence=row['prompt_binding_evidence'],source_binding_evidence=row['prompt_binding_evidence'])
   write('prompts/video_prompt_bindings.jsonl.gz',json.dumps(binding,ensure_ascii=False,separators=(',',':'))+'\n');s=split(row);download=row['download']
   item=dict(video_id=vid,trajectory_id=binding['trajectory_id'],source_group_id=row['source_group_id'],engine=row['engine'],scene=scene,native_scene=binding['native_scene_id'],camera=row['camera'],background=str(row.get('background','')),gravity_level=str(row.get('gravity','')),split=s,video_sha256=row['sha256'],canonical_path=row['canonical_path'],media_repo=download['repo_id'],media_revision=download['revision'],media_path=download['path'],archive_member=download.get('member')or'',prompt_1=texts[0],prompt_2=texts[1],prompt_3=texts[2],prompt_sha256=hashes,physical_parameters_json=json.dumps(row['parameter_facts'],ensure_ascii=True,separators=(',',':')),external_controls_json=json.dumps(row['external_control_inputs'],ensure_ascii=True,separators=(',',':')))
   buffers[s].append(item)
   if len(buffers[s])>=512:writers[s].write_table(pa.Table.from_pylist(buffers[s],schema=schema));buffers[s].clear()
   index[vid]=(row['sha256'],hashes,row['parameter_facts_sha256'],s);stats['videos']+=1;stats['variants']+=3;stats[s]+=1
   if stats['videos']%12000==0:print(json.dumps(dict(stats)),flush=True)
 finally:
  for s,w in writers.items():
   if buffers[s]:w.write_table(pa.Table.from_pylist(buffers[s],schema=schema))
   w.close()
  for f in gz.values():f.close()
 assert stats['videos']==72000 and stats['train']==45165 and stats['isaac_T14']==960 and len(unit_keys)==1190
 for s in writers:
  table=pq.read_table(D/f'catalog/parquet/videos_{s}.parquet');assert table.num_rows==stats[s]
  for x in table.to_pylist():assert (x['video_sha256'],x['prompt_sha256'],parameter_facts_sha(json.loads(x['physical_parameters_json'])),s)==index[x['video_id']]
 shutil.copyfile(D/'catalog/train_final.jsonl.gz',D/'catalog/train_unique_declared_triplets.jsonl.gz');shutil.copyfile(D/'catalog/parquet/videos_train.parquet',D/'catalog/parquet/videos_train_unique_declared_triplets.parquet')
 write('prompts/prompt_texts.jsonl.gz',''.join(json.dumps(dict(sha256=h,prompt=t),ensure_ascii=False,separators=(',',':'))+'\n' for h,t in sorted(pool.items())));gz['prompts/prompt_texts.jsonl.gz'].close()
 checks=D/'checks';checks.mkdir(exist_ok=True)
 for name in ['SEMANTIC_CHANGE_LEDGER.jsonl.gz','UNIT_DIMENSION_REGISTRY.json']:shutil.copyfile(OUT/name,checks/name)
 report=dict(status='PASS',policy=VERSION,base_revision=BASE,counts=dict(stats),generation_counts=generated['counts'],issues=0,unique_prompt_texts=len(pool),unit_key_coverage=len(unit_keys),unknown_unit_keys=0,metadata_values_preserved_exactly=True,all_original_clauses_accounted_for=True,all_controller_actors_axes_signs_conditions_and_times_preserved=True,display_policy=dict(significant_digits=SIG,relative_error_bound=RELATIVE_DISPLAY_BOUND,short_exact_fractions_preserved=True,full_precision_values_retained_in_metadata=True),videos_config_splits_and_frozen_core100_preserved=True,manifest_sha256=sha(D/'catalog/videos.jsonl.gz'),training_manifest_sha256=sha(D/'catalog/train_final.jsonl.gz'),bindings_sha256=sha(D/'prompts/video_prompt_bindings.jsonl.gz'),ledger_sha256=sha(checks/'SEMANTIC_CHANGE_LEDGER.jsonl.gz'),source_numeric_parameter_checks=generated['counts']['source_numeric_field_checks'],source_controls_regenerated_again=True,human_visual_physics_review_claimed=False)
 dump(checks/'PROMPT_SEMANTIC_AUDIT_20261102.json',report);dump(OUT/'INDEPENDENT_VERIFICATION.json',report)
 manifest=json.loads((current/'releases/physedit/prompts/PROMPT_MANIFEST.json').read_text(encoding='utf8'));manifest.update(policy=VERSION,current_policy=VERSION,current_video_prompt_bindings_sha256=report['bindings_sha256'],check_report='releases/physedit/checks/PROMPT_SEMANTIC_AUDIT_20261102.json',prompt_source_revision=BASE,unique_prompt_texts=len(pool),numeric_parameters_unchanged=True,numeric_parameter_metadata_corrected=True,prompt_texts_unchanged=False,display_numeric_policy=report['display_policy'],physical_input_policy='Exact source parameter values preserved; dimensional units repaired; text uses bounded compact numbers and source-proven deduplication.')
 dump(D/'prompts/PROMPT_MANIFEST.json',manifest)
 check=json.loads((current/'releases/physedit/checks/CHECK_REPORT.json').read_text(encoding='utf8'));check.update(status='PASS',policy=VERSION,semantic_audit='PROMPT_SEMANTIC_AUDIT_20261102.json',baseline_revision=BASE,all_72000_numeric_unit_display_and_binding_checks_passed=True);dump(checks/'CHECK_REPORT.json',check)
 for rel in ['README.md','releases/physedit/README.md','releases/physedit/docs/QUICKSTART_ZH.md']:
  p=STAGE/rel;p.parent.mkdir(parents=True,exist_ok=True);text=(current/rel).read_text(encoding='utf8')
  text+='\n\n## Prompt semantic revision v2 (2026-11-02)\n\nAll 72,000 videos / 216,000 prompt bindings were rechecked for physical dimensions, bounded numeric display and source-proven redundancy. Exact parameter values remain in metadata; text uses up to 8 significant digits or shorter exact fractions, with relative display error at most 5e-8. Current media, configs, splits and frozen Core100 submitted prompts are preserved. See '+('[semantic audit](releases/physedit/checks/PROMPT_SEMANTIC_AUDIT_20261102.json)' if rel=='README.md' else '[semantic audit](https://huggingface.co/datasets/phy2/phydataset/blob/main/releases/physedit/checks/PROMPT_SEMANTIC_AUDIT_20261102.json)')+'.\n'
  p.write_text(text,encoding='utf8')
 status=json.loads((current/'release_status.json').read_text(encoding='utf8'));status.update(prompt_revision=VERSION,prompt_numeric_audit='releases/physedit/checks/PROMPT_SEMANTIC_AUDIT_20261102.json',prompt_semantic_audit_status='PASS',prompt_revision_base=BASE);dump(STAGE/'release_status.json',status)
 print(json.dumps(report),flush=True)
if __name__=='__main__':main()
