"""Run on p25: package, atomically commit, then freshly verify audited metadata."""
from pathlib import Path
import collections,gzip,hashlib,json,os,shutil,sys,zipfile
ROOT=Path('/data_cached/wangzijun_p25/prompt_numeric_publish_20261102_4a88a7a4')
STAGE=ROOT/'stage'; BASE='096d3d1fe9d78c57d2fe80de3636cbac04950e65'; REPO='phy2/phydataset'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def rows(p):
 with gzip.open(p,'rt') as f:yield from map(json.loads,f)
def prepare():
 report=json.loads((STAGE/'releases/physedit/checks/PROMPT_NUMERIC_AUDIT_20261102.json').read_text());assert report['status']=='PASS' and report['issues']==0
 old=ROOT/'current/releases/physedit/downloads/physedit_metadata.zip'
 status=json.loads((STAGE/'release_status.json').read_text());assert sha(old)==status['offline_metadata_sha256']
 dest=STAGE/'releases/physedit/downloads/physedit_metadata.zip';dest.parent.mkdir(parents=True,exist_ok=True)
 replacements={p.relative_to(STAGE/'releases').as_posix():p for p in (STAGE/'releases/physedit').rglob('*') if p.is_file() and p!=dest}
 unchanged=0; replaced=0; added=0; frozen=0
 with zipfile.ZipFile(old) as src,zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
  names=set(src.namelist())
  for info in src.infolist():
   p=replacements.get(info.filename)
   if p:
    out.write(p,info.filename);replaced+=1
   else:
    with src.open(info) as a,out.open(info,'w',force_zip64=True) as b:shutil.copyfileobj(a,b,4*1024*1024)
    unchanged+=1
  for name,p in replacements.items():
   if name not in names:out.write(p,name);added+=1
 with zipfile.ZipFile(old) as src,zipfile.ZipFile(dest) as out:
  assert out.testzip() is None
  for name,p in replacements.items():assert hashlib.sha256(out.read(name)).hexdigest()==sha(p),name
  for info in src.infolist():
   if info.filename not in replacements:
    a=out.getinfo(info.filename);assert (a.CRC,a.file_size)==(info.CRC,info.file_size)
    if 'core100' in info.filename.lower():
     assert hashlib.sha256(src.read(info)).digest()==hashlib.sha256(out.read(info.filename)).digest();frozen+=1
 status['offline_metadata_sha256']=sha(dest);status['offline_metadata_bytes']=dest.stat().st_size;dump(STAGE/'release_status.json',status)
 plan=[]
 for p in sorted(STAGE.rglob('*')):
  if not p.is_file():continue
  path=p.relative_to(STAGE).as_posix()
  assert path in ['README.md','release_status.json'] or path.startswith(('releases/physedit/catalog/','releases/physedit/prompts/','releases/physedit/checks/','releases/physedit/docs/','releases/physedit/downloads/')) or path=='releases/physedit/README.md',path
  assert not any(x in path.lower() for x in ['core100','provenance','config_bindings']),path
  plan.append(dict(path=path,size=p.stat().st_size,sha256=sha(p)))
 receipt=dict(base_revision=BASE,files=plan,offline=dict(unchanged_members=unchanged,replaced_members=replaced,added_members=added,frozen_core100_members_verified=frozen,sha256=status['offline_metadata_sha256']))
 dump(ROOT/'UPLOAD_PLAN.json',receipt);print(json.dumps({'prepared_files':len(plan),'offline':receipt['offline']}),flush=True)
def api():
 for key in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:os.environ[key]=sys.argv[2]
 os.environ['HF_HUB_DISABLE_XET']='1';os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
 from huggingface_hub import HfApi
 return HfApi()
def publish():
 a=api();head=a.repo_info(REPO,repo_type='dataset').sha;assert head==BASE,('HEAD_CHANGED',head)
 from huggingface_hub import CommitOperationAdd
 plan=json.loads((ROOT/'UPLOAD_PLAN.json').read_text())
 for x in plan['files']:assert sha(STAGE/x['path'])==x['sha256']
 result=a.create_commit(repo_id=REPO,repo_type='dataset',parent_commit=BASE,
  operations=[CommitOperationAdd(path_in_repo=x['path'],path_or_fileobj=str(STAGE/x['path'])) for x in plan['files']],
  commit_message='Replace current English prompts after full numeric/configuration audit',
  commit_description='Synchronize all 72000 current videos and 216000 prompt bindings across catalog, training, scenes, Parquet and offline metadata. Preserve video/config bytes, split assignments, original Isaac T14 and frozen Core100 generation inputs.')
 receipt=dict(commit=result.oid,url=result.commit_url,base=BASE,files=len(plan['files']));dump(ROOT/'PUBLISHED.json',receipt);print(json.dumps(receipt),flush=True)
def replace():
 a=api();assert a.repo_info(REPO,repo_type='dataset').sha==BASE
 plan=json.loads((ROOT/'UPLOAD_PLAN.json').read_text());quota=json.loads((ROOT/'QUOTA_REPLACEMENT_PLAN.json').read_text())
 assert quota['head_unchanged']==BASE
 for x in plan['files']:assert sha(STAGE/x['path'])==x['sha256'],x['path']
 for x in quota['backed_up_files']:
  p=Path(x['backup']);assert p.stat().st_size==x['size'] and sha(p)==x['sha256'],x['path']
 objects={x['oid']:x for x in quota['replaceable_old_metadata_lfs_objects']}
 assert len(objects)==49
 paths=[x['path'] for x in quota['replaceable_old_metadata_lfs_objects']]
 infos={x.path:x for x in a.get_paths_info(REPO,paths,repo_type='dataset',revision=BASE)}
 for x in quota['replaceable_old_metadata_lfs_objects']:
  assert x['path'].startswith('releases/physedit/') and not any(s in x['path'].lower() for s in ['core100','provenance','config_bindings'])
  assert infos[x['path']].lfs.sha256==x['oid'] and infos[x['path']].size==x['size']
 receipt=dict(base=BASE,objects=list(objects.values()),unique_objects=len(objects),bytes=sum(x['size'] for x in objects.values()),rewrite_history=False,local_backup_receipt='LOCAL_BACKUP_VERIFIED.json',authorization='User requested local backup, then explicitly requested replacing the online release after backup verification.')
 dump(ROOT/'SCOPED_METADATA_CLEANUP_REQUEST.json',receipt)
 from types import SimpleNamespace
 a.permanently_delete_lfs_files(REPO,[SimpleNamespace(file_oid=h) for h in objects],rewrite_history=False,repo_type='dataset')
 receipt['cleanup_request_completed']=True;dump(ROOT/'SCOPED_METADATA_CLEANUP_RECEIPT.json',receipt)
 print(json.dumps({'phase':'scoped_old_metadata_cleanup_completed','objects':len(objects),'bytes':receipt['bytes']}),flush=True)
 publish()
def quota_plan():
 a=api();assert a.repo_info(REPO,repo_type='dataset').sha==BASE
 plan=json.loads((ROOT/'UPLOAD_PLAN.json').read_text());paths=[x['path'] for x in plan['files']]
 infos={x.path:x for x in a.get_paths_info(REPO,paths,repo_type='dataset',revision=BASE)}
 backup=ROOT/('backup_'+BASE);backup.mkdir(exist_ok=True);oldzip=ROOT/'current/releases/physedit/downloads/physedit_metadata.zip';objects=[];saved=[]
 with zipfile.ZipFile(oldzip) as z:
  for path,info in infos.items():
   p=backup/path;p.parent.mkdir(parents=True,exist_ok=True)
   source=ROOT/'current'/path
   if source.exists():shutil.copyfile(source,p)
   else:
    name=path.removeprefix('releases/')
    with z.open(name) as src,p.open('wb') as dst:shutil.copyfileobj(src,dst,4*1024*1024)
   h=sha(p);assert p.stat().st_size==info.size
   if info.lfs:
    assert h==info.lfs.sha256,path
    objects.append(dict(path=path,oid=h,size=info.size,backup=str(p)))
   else:assert info.blob_id==hashlib.sha1(b'blob '+str(info.size).encode()+b'\0'+p.read_bytes()).hexdigest(),path
   saved.append(dict(path=path,sha256=h,size=info.size,backup=str(p)))
 unique={x['oid']:x for x in objects}
 result=dict(status='AWAITING_USER_DECISION',error='403 Private storage limit reached for org phy2',head_unchanged=BASE,
  backed_up_files=saved,replaceable_old_metadata_lfs_objects=objects,old_object_bytes=sum(x['size'] for x in unique.values()),unique_old_objects=len(unique),
  new_upload_bytes=sum(x['size'] for x in plan['files']),deletion_performed=False,
  consequence='Deleting old LFS objects would affect old revisions that reference these exact metadata objects; video/config/Core100 objects are excluded.')
 dump(ROOT/'QUOTA_REPLACEMENT_PLAN.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['backed_up_files','replaceable_old_metadata_lfs_objects']}),flush=True)
def compress():
 records=[]
 for p in sorted(STAGE.rglob('*.gz')):
  before=sha(p);old_size=p.stat().st_size;raw_hash=hashlib.sha256();temp=p.with_suffix(p.suffix+'.compressing')
  with gzip.open(p,'rb') as src,gzip.open(temp,'wb',compresslevel=9) as dst:
   for b in iter(lambda:src.read(4*1024*1024),b''):raw_hash.update(b);dst.write(b)
  check=hashlib.sha256()
  with gzip.open(temp,'rb') as f:
   for b in iter(lambda:f.read(4*1024*1024),b''):check.update(b)
  assert check.digest()==raw_hash.digest();temp.replace(p)
  records.append(dict(path=p.relative_to(STAGE).as_posix(),old_sha256=before,new_sha256=sha(p),uncompressed_sha256=check.hexdigest(),old_bytes=old_size,new_bytes=p.stat().st_size))
 d=STAGE/'releases/physedit';report=json.loads((d/'checks/PROMPT_NUMERIC_AUDIT_20261102.json').read_text());report.update(manifest_sha256=sha(d/'catalog/videos.jsonl.gz'),bindings_sha256=sha(d/'prompts/video_prompt_bindings.jsonl.gz'),lossless_storage_compression=True)
 dump(d/'checks/PROMPT_NUMERIC_AUDIT_20261102.json',report)
 manifest=json.loads((d/'prompts/PROMPT_MANIFEST.json').read_text());manifest['current_video_prompt_bindings_sha256']=report['bindings_sha256'];dump(d/'prompts/PROMPT_MANIFEST.json',manifest)
 receipt=dict(status='PASS',all_uncompressed_bytes_identical=True,files=records,old_bytes=sum(r['old_bytes'] for r in records),new_bytes=sum(r['new_bytes'] for r in records));dump(d/'checks/PROMPT_LOSSLESS_STORAGE_COMPRESSION_20261102.json',receipt)
 status=json.loads((STAGE/'release_status.json').read_text());status['offline_metadata_sha256']=json.loads((ROOT/'current/release_status.json').read_text())['offline_metadata_sha256'];dump(STAGE/'release_status.json',status)
 prepare();print(json.dumps({k:v for k,v in receipt.items() if k!='files'}),flush=True)
def verify():
 a=api();pub=json.loads((ROOT/'PUBLISHED.json').read_text());revision=pub['commit'];plan=json.loads((ROOT/'UPLOAD_PLAN.json').read_text());paths=[x['path'] for x in plan['files']]
 infos={x.path:x for x in a.get_paths_info(REPO,paths,repo_type='dataset',revision=revision)}
 for x in plan['files']:
  info=infos[x['path']];p=STAGE/x['path'];assert info.size==x['size']
  if info.lfs:assert info.lfs.sha256==x['sha256'],x['path']
  else:assert info.blob_id==hashlib.sha1(b'blob '+str(p.stat().st_size).encode()+b'\0'+p.read_bytes()).hexdigest(),x['path']
 protected=['catalog/active_core100_conditions.json','releases/physedit/provenance/configs.zip','releases/t14_original_isaac_20261101/provenance.zip','releases/physedit/catalog/config_bindings.jsonl.gz']
 before={x.path:(x.blob_id,x.size) for x in a.get_paths_info(REPO,protected,repo_type='dataset',revision=BASE)}
 after={x.path:(x.blob_id,x.size) for x in a.get_paths_info(REPO,protected,repo_type='dataset',revision=revision)};assert before==after
 from huggingface_hub import hf_hub_download
 fresh=ROOT/('fresh_'+revision[:10]);downloads={}
 for path in paths:
  p=Path(hf_hub_download(REPO,path,repo_type='dataset',revision=revision,local_dir=fresh,force_download=True));assert sha(p)==next(x['sha256'] for x in plan['files'] if x['path']==path),path;downloads[path]=p
 d=fresh/'releases/physedit';counts=collections.Counter();index={}
 for old,r in zip(rows(ROOT/'current/releases/physedit/catalog/videos.jsonl.gz'),rows(d/'catalog/videos.jsonl.gz')):
  for key in ['canonical_video_id','sha256','download','config_download','split','source_group_id','current_render','physical_qa','quality_admission_status']:assert old.get(key)==r.get(key),(r['canonical_video_id'],key)
  assert len(r['prompt_variants_en'])==3
  assert [hashlib.sha256(t.encode()).hexdigest() for t in r['prompt_variants_en']]==r['prompt_variant_sha256']
  index[r['canonical_video_id']]=(r['sha256'],r['prompt_variant_sha256']);counts['videos']+=1;counts['bindings']+=3
  if r['engine']=='isaac' and r['scene']=='T14':counts['isaac_T14']+=1
  assert r['scene']!='T14S'
 assert counts['videos']==72000 and counts['isaac_T14']==960
 train=list(rows(d/'catalog/train_final.jsonl.gz'));assert len(train)==45165
 pool={r['sha256']:r['prompt'] for r in rows(d/'prompts/prompt_texts.jsonl.gz')}
 bound=0
 for r in rows(d/'prompts/video_prompt_bindings.jsonl.gz'):
  assert (r['video_sha256'],r['prompt_sha256'])==index[r['video_id']]
  for h in r['prompt_sha256']:assert hashlib.sha256(pool[h].encode()).hexdigest()==h;bound+=1
 assert bound==216000
 status=json.loads((fresh/'release_status.json').read_text());assert sha(d/'downloads/physedit_metadata.zip')==status['offline_metadata_sha256']
 with zipfile.ZipFile(d/'downloads/physedit_metadata.zip') as z:
  for name in ['catalog/videos.jsonl.gz','catalog/train_final.jsonl.gz','prompts/video_prompt_bindings.jsonl.gz','prompts/prompt_texts.jsonl.gz']:
   assert hashlib.sha256(z.read('physedit/'+name)).hexdigest()==sha(d/name)
 result=dict(status='PASS',revision=revision,url=pub['url'],files_freshly_downloaded_and_hash_verified=len(paths),counts=dict(counts),training_videos=len(train),protected_paths_unchanged=protected,offline_zip_synchronized=True)
 dump(ROOT/'FRESH_VERIFIED.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
