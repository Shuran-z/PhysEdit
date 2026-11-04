"""P25 packaging/publication/readback with local-backup-scoped quota recovery."""
from pathlib import Path
import collections,gzip,hashlib,json,os,shutil,sys,time,zipfile
R=Path('/data_cached/wangzijun_p25/prompt_semantic_repair_20261102');STAGE=R/'stage';BASE='7af77078d39270a3c6ca7633bd373f357483b5f0';REPO='phy2/phydataset'
CURRENT=Path('/data_cached/wangzijun_p25/prompt_numeric_publish_20261102_4a88a7a4/fresh_7af77078d3')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
def rows(p):
 with gzip.open(p,'rt') as f:yield from map(json.loads,f)
def api():
 for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:os.environ[k]=sys.argv[2]
 os.environ['HF_HUB_DISABLE_XET']='1';os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
 from huggingface_hub import HfApi
 return HfApi()
def prepare():
 report=json.loads((STAGE/'releases/physedit/checks/PROMPT_SEMANTIC_AUDIT_20261102.json').read_text());assert report['status']=='PASS' and report['issues']==0
 backup=json.loads((R/'LOCAL_BASE_BACKUP_VERIFIED.json').read_text());assert backup['status']=='PASS' and backup['revision']==BASE and backup['files']==60
 status=json.loads((STAGE/'release_status.json').read_text());old=CURRENT/'releases/physedit/downloads/physedit_metadata.zip';assert sha(old)==status['offline_metadata_sha256']
 target=STAGE/'releases/physedit/downloads/physedit_metadata.zip';target.parent.mkdir(parents=True,exist_ok=True)
 replace={p.relative_to(STAGE/'releases').as_posix():p for p in (STAGE/'releases/physedit').rglob('*') if p.is_file() and p!=target}
 protected=[];unchanged=0;changed=0;added=0
 with zipfile.ZipFile(old) as src,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as dst:
  names=set(src.namelist())
  for info in src.infolist():
   if info.filename in replace:dst.write(replace[info.filename],info.filename);changed+=1
   else:
    with src.open(info) as a,dst.open(info,'w',force_zip64=True) as b:shutil.copyfileobj(a,b,8<<20)
    unchanged+=1
  for name,p in replace.items():
   if name not in names:dst.write(p,name);added+=1
 with zipfile.ZipFile(old) as src,zipfile.ZipFile(target) as dst:
  assert dst.testzip() is None
  for name,p in replace.items():assert hashlib.sha256(dst.read(name)).hexdigest()==sha(p),name
  for info in src.infolist():
   if info.filename not in replace:
    after=dst.getinfo(info.filename);assert (after.CRC,after.file_size)==(info.CRC,info.file_size)
    if 'core100' in info.filename.lower() or 'provenance' in info.filename.lower():
     h=hashlib.sha256(src.read(info)).hexdigest();assert hashlib.sha256(dst.read(info.filename)).hexdigest()==h;protected.append(dict(path=info.filename,sha256=h))
 status['offline_metadata_sha256']=sha(target);status['offline_metadata_bytes']=target.stat().st_size;dump(STAGE/'release_status.json',status)
 files=[]
 for p in sorted(STAGE.rglob('*')):
  if not p.is_file():continue
  name=p.relative_to(STAGE).as_posix()
  assert name in ['README.md','release_status.json','releases/physedit/README.md'] or name.startswith(('releases/physedit/catalog/','releases/physedit/prompts/','releases/physedit/checks/','releases/physedit/docs/','releases/physedit/downloads/'))
  assert not any(x in name.lower() for x in ['core100','provenance','config_bindings'])
  files.append(dict(path=name,size=p.stat().st_size,sha256=sha(p)))
 plan=dict(base_revision=BASE,files=files,offline_metadata_sha256=status['offline_metadata_sha256'],offline_unchanged_members=unchanged,offline_replaced_members=changed,offline_added_members=added,protected_offline_members_verified=protected)
 dump(R/'UPLOAD_PLAN.json',plan);print(json.dumps(dict(prepared_files=len(files),bytes=sum(x['size'] for x in files),unchanged_offline_members=unchanged,protected_members_verified=len(protected))),flush=True)
def scoped_quota_cleanup(a,plan):
 existing=json.loads((R/'BASE_BACKUP_MANIFEST.json').read_text());backup={x['path']:x for x in existing['files']};paths=[x['path'] for x in plan['files'] if x['path'] in backup]
 selected={}
 for info in a.get_paths_info(REPO,paths,repo_type='dataset',revision=BASE):
  if info.lfs:
   item=backup[info.path];assert info.lfs.sha256==item['sha256'];assert sha(CURRENT/info.path)==item['sha256'];selected[info.lfs.sha256]=dict(path=info.path,sha256=info.lfs.sha256,size=info.size)
 assert selected and all(not any(x in v['path'].lower() for x in ['core100','provenance','config_bindings']) for v in selected.values())
 receipt=dict(base_revision=BASE,only_backed_up_replaced_metadata=True,objects=list(selected.values()),bytes=sum(x['size'] for x in selected.values()),rewrite_history=False)
 dump(R/'SCOPED_METADATA_CLEANUP_REQUEST.json',receipt)
 from types import SimpleNamespace
 a.permanently_delete_lfs_files(REPO,[SimpleNamespace(file_oid=h) for h in selected],rewrite_history=False,repo_type='dataset')
 receipt['completed']=True;dump(R/'SCOPED_METADATA_CLEANUP_RECEIPT.json',receipt)
def publish():
 a=api();assert a.repo_info(REPO,repo_type='dataset').sha==BASE
 plan=json.loads((R/'UPLOAD_PLAN.json').read_text());assert json.loads((R/'LOCAL_BASE_BACKUP_VERIFIED.json').read_text())['status']=='PASS'
 for x in plan['files']:assert sha(STAGE/x['path'])==x['sha256']
 from huggingface_hub import CommitOperationAdd
 cleaned=(R/'SCOPED_METADATA_CLEANUP_RECEIPT.json').exists()
 for attempt in range(8):
  try:
   result=a.create_commit(repo_id=REPO,repo_type='dataset',parent_commit=BASE,operations=[CommitOperationAdd(path_in_repo=x['path'],path_or_fileobj=str(STAGE/x['path'])) for x in plan['files']],commit_message='Repair prompt dimensions, bounded numeric display and source-proven duplicate clauses',commit_description='All 72000 videos / 216000 prompt bindings independently rechecked. Preserve exact parameter values, current video/config bytes, splits and frozen Core100. Synchronize catalogs, Parquet, text exports and offline metadata. H3 uses the newly pinned revision in a separate cache/run.')
   receipt=dict(commit=result.oid,url=result.commit_url,base=BASE,files=len(plan['files']));dump(R/'PUBLISHED.json',receipt);print(json.dumps(receipt),flush=True);return
  except Exception as exc:
   status=getattr(getattr(exc,'response',None),'status_code',None)
   if status!=403 or 'Private storage limit' not in str(exc):raise
   if not cleaned:scoped_quota_cleanup(a,plan);cleaned=True
   if attempt==7:raise
   time.sleep(min(45,15+attempt*5))
def verify():
 a=api();pub=json.loads((R/'PUBLISHED.json').read_text());revision=pub['commit'];plan=json.loads((R/'UPLOAD_PLAN.json').read_text());paths=[x['path'] for x in plan['files']]
 infos={x.path:x for x in a.get_paths_info(REPO,paths,repo_type='dataset',revision=revision)}
 for item in plan['files']:
  info=infos[item['path']];assert info.size==item['size']
  if info.lfs:assert info.lfs.sha256==item['sha256']
  else:
   p=STAGE/item['path'];assert info.blob_id==hashlib.sha1(b'blob '+str(p.stat().st_size).encode()+bytes([0])+p.read_bytes()).hexdigest()
 protected=['catalog/active_core100_conditions.json','releases/physedit/provenance/configs.zip','releases/t14_original_isaac_20261101/provenance.zip','releases/physedit/catalog/config_bindings.jsonl.gz']
 before={x.path:(x.blob_id,x.size) for x in a.get_paths_info(REPO,protected,repo_type='dataset',revision=BASE)};after={x.path:(x.blob_id,x.size) for x in a.get_paths_info(REPO,protected,repo_type='dataset',revision=revision)};assert before==after
 from huggingface_hub import hf_hub_download
 fresh=R/('fresh_'+revision[:10])
 for item in plan['files']:
  p=fresh/item['path']
  if not p.exists() or sha(p)!=item['sha256']:p=Path(hf_hub_download(REPO,item['path'],repo_type='dataset',revision=revision,local_dir=fresh,force_download=True))
  assert sha(p)==item['sha256']
 d=fresh/'releases/physedit';index={};counts=collections.Counter()
 import itertools
 for old,row in itertools.zip_longest(rows(CURRENT/'releases/physedit/catalog/videos.jsonl.gz'),rows(d/'catalog/videos.jsonl.gz')):
  assert old and row
  for k in ['canonical_video_id','sha256','download','config_download','split','source_group_id','current_render','physical_qa','quality_admission_status','external_control_inputs']:assert old.get(k)==row.get(k),(row['canonical_video_id'],k)
  for left,right in zip(old['parameter_facts'],row['parameter_facts']):assert left[:-1]==right[:-1]
  texts=row['prompt_variants_en'];assert len(texts)==3 and [hashlib.sha256(t.encode()).hexdigest() for t in texts]==row['prompt_variant_sha256']
  index[row['canonical_video_id']]=(row['sha256'],row['prompt_variant_sha256']);counts['videos']+=1;counts['bindings']+=3
  if row['engine']=='isaac' and row['scene']=='T14':counts['isaac_T14']+=1
  assert row['scene']!='T14S'
 assert counts['videos']==72000 and counts['isaac_T14']==960
 train_count=0
 for x in rows(d/'catalog/train_final.jsonl.gz'):assert index[x['canonical_video_id']]==(x['sha256'],x['prompt_variant_sha256']);train_count+=1
 assert train_count==45165
 pool={x['sha256']:x['prompt'] for x in rows(d/'prompts/prompt_texts.jsonl.gz')};binding_count=0
 for x in rows(d/'prompts/video_prompt_bindings.jsonl.gz'):
  assert index[x['video_id']]==(x['video_sha256'],x['prompt_sha256'])
  for h in x['prompt_sha256']:assert hashlib.sha256(pool[h].encode()).hexdigest()==h;binding_count+=1
 assert binding_count==216000
 status=json.loads((fresh/'release_status.json').read_text());assert sha(d/'downloads/physedit_metadata.zip')==status['offline_metadata_sha256']
 with zipfile.ZipFile(d/'downloads/physedit_metadata.zip') as z:
  for item in plan['files']:
   path=item['path']
   if path.startswith('releases/physedit/') and '/downloads/' not in path:assert hashlib.sha256(z.read(path.removeprefix('releases/'))).hexdigest()==item['sha256']
  for item in plan['protected_offline_members_verified']:assert hashlib.sha256(z.read(item['path'])).hexdigest()==item['sha256']
 info=a.repo_info(REPO,repo_type='dataset');assert info.private is True and info.card_data.get('license')=='other'
 # Concurrent unrelated releases may advance main; every repaired and protected path must still match.
 main_infos={x.path:(x.blob_id,x.size) for x in a.get_paths_info(REPO,paths+protected,repo_type='dataset',revision=info.sha)}
 compatible_additions=[]
 for p in paths:
  if main_infos[p]==(infos[p].blob_id,infos[p].size):continue
  assert p=='releases/physedit/prompts/PROMPT_MANIFEST.json',p
  current_path=Path(hf_hub_download(REPO,p,repo_type='dataset',revision=info.sha,local_dir=R/'main_metadata_check',force_download=True))
  original=json.loads((fresh/p).read_text());current=json.loads(current_path.read_text())
  assert all(current.get(k)==v for k,v in original.items()),'Published manifest fields changed'
  assert set(current)-set(original)=={'finalization'}
  assert current['finalization']['previous_revision']==revision
  assert current['finalization']['catalog_path']=='releases/physedit/catalog/videos.jsonl.gz'
  compatible_additions.append(dict(path=p,added_keys=['finalization'],published_fields_unchanged=True))
 assert all(main_infos[p]==after[p] for p in protected)
 result=dict(status='PASS',revision=revision,url=pub['url'],current_main_verified=True,files_freshly_downloaded_and_hash_verified=len(paths),counts=dict(counts),training_videos=train_count,protected_paths_unchanged=protected,offline_zip_synchronized=True,protected_offline_member_hashes_verified=len(plan['protected_offline_members_verified']))
 result['current_main_revision']=info.sha
 result['current_main_published_contents_preserved']=True
 result['compatible_concurrent_metadata_additions']=compatible_additions
 dump(R/'FRESH_VERIFIED.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
