"""Correct only selected-parameter registration for 15 protected references."""
import collections,gzip,hashlib,json,shutil,zipfile
from pathlib import Path
from huggingface_hub import HfApi,CommitOperationAdd
import pyarrow.parquet as pq
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');OLD=R/'remaining2241/stage/releases/physedit';O=R/'prompt_registration15';STAGE=O/'stage';D=STAGE/'releases/physedit';BASE='88f8fde1d1c240cec2cc0c201a4310cd8d4c5cbc';REPO='phy2/phydataset'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return list(map(json.loads,gzip.open(p,'rt')))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
api=HfApi();assert api.repo_info(REPO,repo_type='dataset').sha==BASE;assert not STAGE.exists();O.mkdir(exist_ok=True);shutil.copytree(OLD,D,ignore=shutil.ignore_patterns('downloads'));issues=json.loads(Path('/tmp/prompt_registration15.json').read_text());fix={x['canonical_video_id']:x for x in issues};assert len(fix)==15
checks=json.loads((OLD/'checks/FILES_SHA256.json').read_text());assert all(sha(OLD/x['path'])==x['sha256'] for x in checks['files'])
train=load(OLD/'catalog/train_final.jsonl.gz');assert not set(fix)&{x['canonical_video_id'] for x in train};rows={x['canonical_video_id']:x for x in load(OLD/'catalog/videos.jsonl.gz') if x['canonical_video_id'] in fix};registry=[];desired={}
for cid,v in rows.items():
 assert v['split']=='protected_core100_reserve80_lineage';before=v['selected_parameter_keys'];assert 't04v3_stack_book_bottom.mass' in before and 't04v3_removable_support_bar.friction' not in before
 after=[x for x in before if x!='t04v3_stack_book_bottom.mass'];after.insert(after.index('gravity')+1,'t04v3_removable_support_bar.friction');assert set(after)==set(fix[cid]['resolved_selected_parameter_keys']);desired[cid]=after
 assert all('Removable support bar material friction 0.22.' in text and 'Stack book bottom mass' not in text for text in v['prompt_variants_en'])
 assert [hashlib.sha256(x.encode()).hexdigest() for x in v['prompt_variants_en']]==v['prompt_variant_sha256']
 registry.append(dict(canonical_video_id=cid,clip_id=v['core100_anchor_clip_id'],camera=v['camera'],video_sha256=v['sha256'],prompt_variant_sha256=v['prompt_variant_sha256'],parameter_facts_sha256=hashlib.sha256(json.dumps(v['parameter_facts'],ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()).hexdigest(),previous_selected_parameter_keys=before,selected_parameter_keys=after,actual_prompt_text_changed=False,physical_parameter_values_changed=False,training_membership_changed=False,evaluation_results_changed=False))
changed=[];counts={}
for p in sorted((D/'catalog').rglob('*.jsonl.gz')):
 if p.name.startswith('train') or p.name in ['config_bindings.jsonl.gz','content_groups.jsonl.gz','content_identity.jsonl.gz']:continue
 temp=p.with_suffix('.writing');n=0
 with gzip.open(p,'rt') as src,gzip.open(temp,'wt') as dst:
  for line in src:
   x=json.loads(line);cid=x.get('canonical_video_id')
   if cid in desired and 'selected_parameter_keys' in x:
    old=json.loads(line);assert x['selected_parameter_keys']==rows[cid]['selected_parameter_keys'];x['selected_parameter_keys']=desired[cid];assert {k:v for k,v in old.items() if k!='selected_parameter_keys'}=={k:v for k,v in x.items() if k!='selected_parameter_keys'};line=json.dumps(x,ensure_ascii=False)+'\n';n+=1
   dst.write(line)
 if n:temp.replace(p);changed.append(p.relative_to(D).as_posix());counts[changed[-1]]=n
 else:temp.unlink()
assert len(changed)==2 and set(counts.values())=={15},counts
# Parquet stores prompt text and physical values, but no selected-key registration column.
for p in (D/'catalog/parquet').glob('*.parquet'):assert 'selected_parameter_keys' not in pq.read_schema(p).names;assert sha(p)==sha(OLD/p.relative_to(D))
protected=['catalog/train_final.jsonl.gz','catalog/train_unique_declared_triplets.jsonl.gz','catalog/split_assignments.csv','prompts/prompt_texts.jsonl.gz','prompts/video_prompt_bindings.jsonl.gz'];preserved=[]
for rel in protected:assert sha(D/rel)==sha(OLD/rel);preserved.append(dict(path=rel,sha256=sha(D/rel),unchanged=True))
registration=dict(schema='prompt-parameter-selection-registration-v1',catalog_base_revision=BASE,affected_videos=15,affected_reference_cases=5,scope='selected_parameter_keys metadata only',prompt_texts_unchanged=True,physical_parameter_values_unchanged=True,training_manifest_unchanged=True,evaluation_results_unchanged=True,records=sorted(registry,key=lambda x:x['canonical_video_id']))
dump(D/'checks/PROMPT_PARAMETER_SELECTION_FIX.json',registration);dump(O/'REGISTRATION.json',registration)
newrecords=[dict(path=p.relative_to(D).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(D.rglob('*')) if p.is_file() and p!=D/'checks/FILES_SHA256.json'];oldhash={x['path']:x['sha256'] for x in checks['files']};changedpaths=[x['path'] for x in newrecords if oldhash.get(x['path'])!=x['sha256']];assert set(changedpaths)==set(changed)|{'checks/PROMPT_PARAMETER_SELECTION_FIX.json'},changedpaths
for rec in newrecords:
 if rec['path'] not in changedpaths:assert oldhash[rec['path']]==rec['sha256']
dump(D/'checks/FILES_SHA256.json',dict(algorithm='SHA-256',scope='Metadata package excluding this file and downloads.',files=newrecords));(D/'downloads').mkdir();archive=D/'downloads/physedit_metadata.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(D.rglob('*')):
  if p.is_file() and p.relative_to(D).parts[0]!='downloads':z.write(p,'physedit/'+p.relative_to(D).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for rec in newrecords:assert hashlib.sha256(z.read('physedit/'+rec['path'])).hexdigest()==rec['sha256']
status=json.loads((R/'remaining2241/stage/release_status.json').read_text());oldstatus=json.loads(json.dumps(status));status['offline_metadata_sha256']=sha(archive);assert {k:v for k,v in status.items() if k!='offline_metadata_sha256'}=={k:v for k,v in oldstatus.items() if k!='offline_metadata_sha256'};dump(STAGE/'release_status.json',status)
receipt=dict(base_revision=BASE,changed_videos=15,changed_metadata_views=counts,registry_sha256=sha(O/'REGISTRATION.json'),protected_files=preserved,all_other_metadata_files_byte_identical=True,actual_prompt_physical_values_train_and_scores_unchanged=True,training_videos=len(train),metadata_zip_sha256=sha(archive));dump(O/'PREPARED.json',receipt);print(json.dumps({'phase':'PREPARED','changed_views':counts}),flush=True)
files=[D/p for p in changedpaths]+[D/'checks/FILES_SHA256.json',archive,STAGE/'release_status.json'];assert api.repo_info(REPO,repo_type='dataset').sha==BASE
commit=api.create_commit(REPO,repo_type='dataset',parent_commit=BASE,commit_message='Correct selected-parameter registration for 15 T04 reference videos; preserve prompts, physics, training and scores',operations=[CommitOperationAdd(path_in_repo=p.relative_to(STAGE).as_posix(),path_or_fileobj=str(p)) for p in files]);remote={x.path:x for x in api.get_paths_info(REPO,[p.relative_to(STAGE).as_posix() for p in files],repo_type='dataset',revision=commit.oid)}
for p in files:
 x=remote[p.relative_to(STAGE).as_posix()];b=p.read_bytes();assert x.size==len(b)
 if x.lfs:assert x.lfs.sha256==hashlib.sha256(b).hexdigest()
 else:assert x.blob_id==hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
receipt.update(revision=commit.oid,files_uploaded=len(files),all_remote_content_hashes_verified=True);dump(O/'PUBLISHED.json',receipt);print(json.dumps(receipt),flush=True)
