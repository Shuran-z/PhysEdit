"""Replace historical holds with current recheck outcomes, preserving their provenance."""
import collections,gzip,hashlib,json,zipfile
from pathlib import Path
from huggingface_hub import HfApi,CommitOperationAdd
O=Path('/data_cached/wangzijun_p25/config_bindings_20261031/followup');S=O/'stage';D=S/'releases/physedit';REPO='phy2/phydataset'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
api=HfApi();receipt=json.loads((O/'PUBLISHED.json').read_text());base=receipt['revision'];assert api.repo_info(REPO,repo_type='dataset').sha==base
missing=load(D/'checks/unresolved_configs.jsonl.gz');reasons={}
for x in missing:
    v=x.get('source_recheck')
    if not v:continue
    x['previous_hold_reason']=x['reason']
    if v['compatible_hashes']>1:x['reason']='Multiple source config byte versions still match the recorded input and camera contract'
    elif v['source_metadata_objects']>0:x['reason']='Retained config candidates do not match the recorded source object, experiment or render inputs'
    else:x['reason']='Exact source-video or original metadata linkage remains unresolved'
    reasons[x['canonical_video_id']]=x['reason']
with gzip.open(D/'checks/unresolved_configs.jsonl.gz','wt') as f:
    for x in missing:f.write(json.dumps(x)+'\n')
bindings=load(D/'catalog/config_bindings.jsonl.gz')
for x in bindings:
    if x['canonical_video_id'] in reasons:
        x['previous_hold_reason']=x['reason'];x['reason']=reasons[x['canonical_video_id']]
with gzip.open(D/'catalog/config_bindings.jsonl.gz','wt') as f:
    for x in bindings:f.write(json.dumps(x)+'\n')
changes=[D/'checks/unresolved_configs.jsonl.gz',D/'catalog/config_bindings.jsonl.gz']
manifest=json.loads((D/'checks/FILES_SHA256.json').read_text())
for x in manifest['files']:
    p=D/x['path']
    if p in changes:x.update(bytes=p.stat().st_size,sha256=sha(p))
    else:assert sha(p)==x['sha256'],str(p)
dump(D/'checks/FILES_SHA256.json',manifest)
archive=D/'downloads/physedit_metadata.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(D.rglob('*')):
        if p.is_file() and p.relative_to(D).parts[0]!='downloads':z.write(p,'physedit/'+p.relative_to(D).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for x in manifest['files']:assert hashlib.sha256(z.read('physedit/'+x['path'])).hexdigest()==x['sha256']
status=json.loads((S/'release_status.json').read_text());status['offline_metadata_sha256']=sha(archive);dump(S/'release_status.json',status)
changes += [D/'checks/FILES_SHA256.json',archive,S/'release_status.json']
result=api.create_commit(REPO,repo_type='dataset',parent_commit=base,commit_message='Record resolved source checks and remaining exact config version conflicts',operations=[CommitOperationAdd(path_in_repo=p.relative_to(S).as_posix(),path_or_fileobj=str(p)) for p in changes])
infos={x.path:x for x in api.get_paths_info(REPO,[p.relative_to(S).as_posix() for p in changes],revision=result.oid,repo_type='dataset')}
for p in changes:
    info=infos[p.relative_to(S).as_posix()];raw=p.read_bytes();assert info.size==len(raw)
    if info.lfs:assert info.lfs.sha256==hashlib.sha256(raw).hexdigest()
    else:assert info.blob_id==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
receipt['data_binding_revision']=base;receipt['revision']=result.oid;receipt['remaining_reason_counts']=dict(collections.Counter(x['reason'] for x in missing));dump(O/'PUBLISHED.json',receipt)
print(json.dumps({'revision':result.oid,'remaining_reason_counts':receipt['remaining_reason_counts']}),flush=True)
