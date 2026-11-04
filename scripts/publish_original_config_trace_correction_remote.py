"""Correct metadata-derived T04 adapters mislabeled as original input bytes; preserve training."""
import collections,gzip,hashlib,itertools,json,re,shutil,zipfile
from pathlib import Path
from huggingface_hub import HfApi,CommitOperationAdd
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'remaining2241';OLD=R/'remaining6767/stage/releases/physedit';STAGE=O/'stage';D=STAGE/'releases/physedit';REPO='phy2/phydataset';BASE='720bee3be736b2a74859ea8b503fd7e423602624'
def load(p):return list(map(json.loads,gzip.open(p,'rt')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def gz(p,rows):
 with gzip.open(p,'wt',encoding='utf8') as f:
  for x in rows:f.write(json.dumps(x,ensure_ascii=False)+'\n')
api=HfApi();assert api.repo_info(REPO,repo_type='dataset').sha==BASE;assert not STAGE.exists();shutil.copytree(OLD,D,ignore=shutil.ignore_patterns('downloads'))
oldchecks=json.loads((OLD/'checks/FILES_SHA256.json').read_text());assert all(sha(OLD/x['path'])==x['sha256'] for x in oldchecks['files'])
bindings=load(D/'catalog/config_bindings.jsonl.gz');before={x['canonical_video_id']:json.loads(json.dumps(x)) for x in bindings};corrected=[]
with zipfile.ZipFile(D/'provenance/configs.zip') as z:
 for b in bindings:
  if b['engine']!='genesis' or b['scene']!='T04' or b['status']!='VERIFIED':continue
  raw=z.read(b['archive_member']);assert hashlib.sha256(raw).hexdigest()==b['config_sha256'];c=json.loads(raw)
  if c.get('dataset_version')!='hf_staging_normalized_v1':continue
  provenance=c['source_provenance'];assert '/metadata/' in provenance['hf_path']
  aux={k:b[k] for k in ['config_sha256','archive_member','download','source_evidence']};aux['document_type']='metadata_derived_config';aux['download']['document_type']='metadata_derived_config';aux['source_provenance']=provenance
  for k in ['config_sha256','archive_member','download','source_evidence']:b.pop(k,None)
  b.update(status='UNRESOLVED',reason='Only a later metadata-derived adapter is preserved; original Genesis input bytes not recovered',auxiliary_config=aux,method='original_config_claim_corrected_after_provenance_audit');corrected.append(b['canonical_video_id'])
assert len(corrected)==399
byid={x['canonical_video_id']:x for x in bindings};pending=load(OLD/'checks/unresolved_configs.jsonl.gz');tasks={x['canonical_video_id']:x for x in load(R/'TASKS.jsonl.gz')};audit=load(O/'EXECUTION_AUDIT.jsonl.gz');groupaudit={x['native_sample_id']:x['execution_evidence'] for x in audit};source_trace=[]
for b in pending+[byid[c] for c in corrected]:
 cid=b['canonical_video_id'];t=tasks[cid];b['native_sample_id']=t['native_sample_id'];b['camera']=t['camera'];b['original_execution_evidence']=groupaudit[t['native_sample_id']];b['original_config_bytes_recovered']=False
 source_trace.append(dict(canonical_video_id=cid,video_sha256=t['video_sha256'],native_sample_id=t['native_sample_id'],scene=t['scene'],camera=t['camera'],execution_evidence=groupaudit[t['native_sample_id']],status='ORIGINAL_CONFIG_BYTES_UNRESOLVED'))
assert len(pending)+len(corrected)==2640;pending+= [byid[c] for c in corrected]
gz(D/'catalog/config_bindings.jsonl.gz',bindings);gz(D/'checks/unresolved_configs.jsonl.gz',pending);gz(D/'checks/CONFIG_SOURCE_TRACE.jsonl.gz',source_trace)
summary=json.loads((O/'EXECUTION_AUDIT_SUMMARY.json').read_text());summary.update(videos=2640,by_scene={'T04':2628,'T01':12},corrected_derived_config_claims=399,original_config_bindings_recovered=0,original_upload_tree_audit=json.loads((O/'UPLOAD_TREE_AUDIT.json').read_text()),cached_config_blobs_scanned=5361,expanded_config_candidates=3768,expanded_candidate_source_types={'metadata_derived_T04_adapters':3753,'T04_pilot_files_not_matching_actual_inputs':3,'T01_retained_files_not_matching_actual_inputs':12})
dump(D/'checks/CONFIG_SOURCE_TRACE_SUMMARY.json',summary);shutil.copyfile(O/'T01_VERSION_DIFFERENCES.json',D/'checks/T01_CONFIG_VERSION_DIFFERENCES.json')
checked=[];excluded={'config_binding_status','config_download','config_sha256'}
for p in sorted((D/'catalog').rglob('*.jsonl.gz')):
 if p.name in ['config_bindings.jsonl.gz','content_groups.jsonl.gz','content_identity.jsonl.gz']:continue
 out=p.with_suffix('.writing');n=0
 with gzip.open(p,'rt') as src,gzip.open(out,'wt') as dst:
  for line in src:
   row=json.loads(line);b=byid[row['canonical_video_id']];original={k:v for k,v in row.items() if k not in excluded};row.update(config_binding_status=b['status'],config_download=b.get('download'),config_sha256=b.get('config_sha256'));assert original=={k:v for k,v in row.items() if k not in excluded};dst.write(json.dumps(row,ensure_ascii=False)+'\n');n+=1
 out.replace(p);checked.append(dict(path=p.relative_to(D).as_posix(),rows=n))
# Independent whole-artifact comparison after writing, excluding only three config-binding fields.
for rec in checked:
 with gzip.open(OLD/rec['path'],'rt') as src,gzip.open(D/rec['path'],'rt') as dst:
  for l,r in itertools.zip_longest(src,dst):
   assert l and r;x=json.loads(l);y=json.loads(r);assert {k:v for k,v in x.items() if k not in excluded}=={k:v for k,v in y.items() if k not in excluded}
preserved=[]
for path in ['catalog/split_assignments.csv','prompts/prompt_texts.jsonl.gz','prompts/video_prompt_bindings.jsonl.gz']:
 assert sha(OLD/path)==sha(D/path);preserved.append(dict(path=path,sha256=sha(D/path),unchanged=True))
train=load(D/'catalog/train_final.jsonl.gz');assert len(train)==45357
counts=dict(collections.Counter(x['status'] for x in bindings));assert counts=={'VERIFIED':69360,'UNRESOLVED':2640}
for path in ['docs/QUICKSTART_ZH.md','docs/DOWNLOAD.md']:
 p=D/path;s=p.read_text();s=s.replace('69,759','69,360').replace('2,241','2,640');s+='\n本次追溯纠正了399条T04的来源类型：它们只有元数据转换副本，单列在配置绑定表的 `auxiliary_config` 中，不算原始配置已找回。原始配置缺口为T04 2,628条、T01 12条；视频及训练资格不受影响。原日志与回执的哈希及来源逐条见 `physedit/checks/CONFIG_SOURCE_TRACE.jsonl.gz`。\n';p.write_text(s)
configcheck=json.loads((D/'checks/CONFIG_BINDINGS.json').read_text());configcheck.update(base_revision=BASE,counts=counts,newly_recovered=0,corrected_derived_config_claims=399,auxiliary_config_bindings=399,unique_configs=len({x['config_sha256'] for x in bindings if x['status']=='VERIFIED'}));dump(D/'checks/CONFIG_BINDINGS.json',configcheck)
records=[dict(path=p.relative_to(D).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(D.rglob('*')) if p.is_file() and p!=D/'checks/FILES_SHA256.json'];dump(D/'checks/FILES_SHA256.json',dict(algorithm='SHA-256',scope='Metadata package excluding this file and downloads.',files=records))
(D/'downloads').mkdir();archive=D/'downloads/physedit_metadata.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(D.rglob('*')):
  if p.is_file() and p.relative_to(D).parts[0]!='downloads':z.write(p,'physedit/'+p.relative_to(D).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for r in records:assert hashlib.sha256(z.read('physedit/'+r['path'])).hexdigest()==r['sha256']
status=json.loads((R/'remaining6767/stage/release_status.json').read_text());status.update(offline_metadata_sha256=sha(archive),config_bindings_verified=69360,config_bindings_unresolved=2640);dump(STAGE/'release_status.json',status)
receipt=dict(base_revision=BASE,counts=counts,original_configs_recovered=0,corrected_derived_config_claims=399,training_membership_unchanged=True,training_videos=len(train),all_scientific_fields_unchanged=True,prompt_and_split_files=preserved,metadata_zip_sha256=sha(archive),config_zip_sha256_unchanged=sha(D/'provenance/configs.zip'),checked_catalogs=checked);dump(O/'PREPARED.json',receipt)
prior={x['path']:x['sha256'] for x in oldchecks['files']};files=[D/x['path'] for x in records if prior.get(x['path'])!=x['sha256']]+[D/'checks/FILES_SHA256.json',archive,STAGE/'release_status.json'];print(json.dumps({'phase':'AUDIT_PREPARED','files':len(files),'counts':counts}),flush=True)
assert api.repo_info(REPO,repo_type='dataset').sha==BASE
result=api.create_commit(REPO,repo_type='dataset',parent_commit=BASE,commit_message='Correct T04 derived-config provenance and attach original execution evidence; preserve training',operations=[CommitOperationAdd(path_in_repo=p.relative_to(STAGE).as_posix(),path_or_fileobj=str(p)) for p in files])
remote={x.path:x for x in api.get_paths_info(REPO,[p.relative_to(STAGE).as_posix() for p in files],repo_type='dataset',revision=result.oid)}
for p in files:
 x=remote[p.relative_to(STAGE).as_posix()];raw=p.read_bytes();assert x.size==len(raw)
 if x.lfs:assert x.lfs.sha256==hashlib.sha256(raw).hexdigest()
 else:assert x.blob_id==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
receipt.update(revision=result.oid,files_uploaded=len(files),all_remote_hashes_verified=True);dump(O/'PUBLISHED.json',receipt);print(json.dumps({k:v for k,v in receipt.items() if k!='checked_catalogs'}),flush=True)
