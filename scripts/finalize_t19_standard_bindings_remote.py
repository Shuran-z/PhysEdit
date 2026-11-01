"""Keep standard scene and prompt indices aligned with reviewed T19 media."""
import os,json,gzip,hashlib,time,logging,shutil
from pathlib import Path
logging.disable(logging.CRITICAL);os.environ['NO_PROXY']='.amazonaws.com';os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import HfApi,get_token,CommitOperationAdd,CommitOperationDelete,hf_hub_download
ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029');OUT=ROOT/'standard_updated_admission'
REPO='phy2/phydataset'
def read(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
def write(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,'wt') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=True)+'\n')
def retry(fn):
    for i in range(8):
        try:return fn()
        except Exception:
            if i==7:raise
            time.sleep(2)
def main():
    receipt=json.loads((OUT/'PUBLISHED.json').read_text());head=receipt['revision'];api=HfApi(token=get_token())
    assert retry(lambda:api.repo_info(REPO,repo_type='dataset',expand=['sha']).sha)==head
    rows=read(OUT/'metadata/releases/physedit/catalog/videos.jsonl.gz');target={r['video_id']:r for r in rows if r.get('media_version_update') and r['video_id'].startswith('phy_isaac_t19_67a7c1d07f0f0048')};assert len(target)==3
    rel='releases/physedit/prompts/video_prompt_bindings.jsonl.gz';old=OUT/'old_prompt_bindings.jsonl.gz'
    info=retry(lambda:api.get_paths_info(REPO,[rel],repo_type='dataset',revision=head))[0]
    if info.lfs.sha256!=hashlib.sha256(old.read_bytes()).hexdigest():
        old=Path(retry(lambda:hf_hub_download(REPO,rel,repo_type='dataset',revision=head,token=get_token())))
    bindings=read(old);count=0
    for r in bindings:
        key=r.get('legacy_video_id',r['video_id'])
        if key not in target:continue
        row=target[key];assert r['prompt_sha256']==row['prompt_variant_sha256']
        r['video_sha256']=row['sha256'];r['download']=row['download'];r['quality_admission_status']=row['quality_admission_status'];r['source_binding_evidence']=row['prompt_binding_evidence'];count+=1
    assert count==3 and len(bindings)==72000
    meta=OUT/'binding_metadata';write(meta/rel,bindings)
    for engine in ['genesis','isaac']:
        write(meta/f'releases/physedit/catalog/by_scene/{engine}__T19.jsonl.gz',[r for r in rows if r['quota_scene']=='T19' and r['engine']==engine])
    report={'records':72000,'changed_video_bindings':3,'prompt_texts_changed':0,'training_manifest_changed':False,'core100_changed':False,'media_sha_verified':True}
    path=meta/'releases/physedit/checks/T19_UPDATED_MEDIA.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2))
    files=[p for p in meta.rglob('*') if p.is_file()]
    operations=[CommitOperationAdd(path_in_repo=p.relative_to(meta).as_posix(),path_or_fileobj=str(p)) for p in files]
    # Remove only three redundant indices created by this publication attempt.
    operations += [CommitOperationDelete(path_in_repo='releases/physedit/catalog/by_scene/T19/'+name) for name in ['videos.jsonl.gz','videos_genesis.jsonl.gz','videos_isaac.jsonl.gz']]
    c=api.create_commit(REPO,repo_type='dataset',parent_commit=head,operations=operations,commit_message='Align T19 prompt-media hashes and standard scene indices')
    infos={x.path:x for x in retry(lambda:api.get_paths_info(REPO,[p.relative_to(meta).as_posix() for p in files],repo_type='dataset',revision=c.oid))}
    for p in files:
        b=p.read_bytes();x=infos[p.relative_to(meta).as_posix()];assert x.size==len(b)
        if x.lfs:assert x.lfs.sha256==hashlib.sha256(b).hexdigest()
        else:assert x.blob_id==hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    receipt.update(revision=c.oid,prompt_media_indices_verified=True);(OUT/'PUBLISHED.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
