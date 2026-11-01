"""Publish an incremental, explicitly incomplete T19 review and verified media links."""
import collections
import concurrent.futures
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import time

os.environ['HF_HUB_DISABLE_XET']='1'
os.environ['NO_PROXY']='.amazonaws.com'
logging.disable(logging.CRITICAL)
from huggingface_hub import HfApi, CommitOperationCopy, get_token
import huggingface_hub.hf_api as hub_api
from huggingface_hub._commit_api import _CopySource

ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029')
PREFIX='releases/72000_release_candidate_20261029'
repo='phy2/phydataset';api=HfApi(token=get_token())


def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=True))


def read(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))


def write(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,'wt') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=True)+'\n')


def info(repo_id,paths,revision):
    parts=[paths[i:i+400] for i in range(0,len(paths),400)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        return {r.path:r for part in pool.map(lambda p:api.get_paths_info(repo_id,p,repo_type='dataset',revision=revision),parts) for r in part}


def main():
    import fcntl
    lock=open(ROOT/'publish.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    plan=json.loads((ROOT/'copy_plan.json').read_text());assert len(plan)==1830
    base=json.loads((ROOT/'base_catalog.json').read_text())
    state_path=ROOT/'publish_progress.json'
    if state_path.exists():state=json.loads(state_path.read_text())
    else:
        head=api.repo_info(repo,repo_type='dataset',expand=['sha']).sha
        assert head==base['revision'],'Upstream changed; merge the current manifest before publishing'
        branch='snapshot-before-t19-hash-bound-review-20261029'
        api.create_branch(repo,repo_type='dataset',branch=branch,revision=head,exist_ok=True)
        state={'initial_revision':head,'backup_branch':branch,'completed_media':0,'pid':os.getpid()};dump(state_path,state)
    cache={}
    grouped=collections.defaultdict(list)
    for r in plan:
        s=r['source_download'];grouped[s['repo_id'],s['revision']].append(s['path'])
    for (source,rev),paths in grouped.items():
        for path,item in info(source,paths,rev).items():cache[source,rev,path]=item
    for r in plan:
        s=r['source_download'];item=cache[s['repo_id'],s['revision'],s['path']]
        assert item.lfs and item.lfs.sha256==r['sha256'] and not s.get('member')
    def sources(copies,repo_type,repo_id,headers,revision,endpoint=None):
        return {_CopySource(o.src_repo_id,o.src_repo_type,o.src_path_in_repo,o.src_revision):cache[o.src_repo_id,o.src_revision,o.src_path_in_repo] for o in copies}
    hub_api._fetch_files_to_copy=sources
    for start in range(state['completed_media'],len(plan),400):
        batch=plan[start:start+400];head=api.repo_info(repo,repo_type='dataset',expand=['sha']).sha
        found=info(repo,[r['destination'] for r in batch],head)
        for r in batch:
            if r['destination'] in found:assert found[r['destination']].lfs.sha256==r['sha256']
        missing=[r for r in batch if r['destination'] not in found]
        if missing:
            ops=[CommitOperationCopy(src_repo_id=r['source_download']['repo_id'],src_repo_type='dataset',
                src_revision=r['source_download']['revision'],src_path_in_repo=r['source_download']['path'],path_in_repo=r['destination']) for r in missing]
            head=api.create_commit(repo,repo_type='dataset',operations=ops,parent_commit=head,
                commit_message=f'Bind recovered Genesis T19 media {start+1}-{start+len(batch)}; quality decisions remain per-video').oid
        checked=info(repo,[r['destination'] for r in batch],head)
        assert all(checked[r['destination']].lfs.sha256==r['sha256'] for r in batch)
        state.update(completed_media=start+len(batch),media_revision=head);dump(state_path,state)
        print(json.dumps({'verified_media':state['completed_media']}),flush=True)
    meta=ROOT/'metadata';dest=meta/PREFIX;rows=read(dest/'videos.jsonl.gz');by_id={r['video_id']:r for r in rows}
    for p in plan:
        r=by_id[p['video_id']];r['source_download']=p['source_download']
        r['download']={'repo_id':repo,'revision':state['media_revision'],'path':p['destination'],'member':''}
        r['media_in_current_scene_directory']=True
    write(dest/'videos.jsonl.gz',rows);usable=[r for r in rows if r['quality_admission_status'].startswith('USABLE_')];write(dest/'usable_videos.jsonl.gz',usable)
    selected=[r for r in rows if r['quota_scene']=='T19'];scene=meta/'data/T19'
    write(scene/'videos.jsonl.gz',selected)
    for engine in ['genesis','isaac']:write(scene/f'videos_{engine}.jsonl.gz',[r for r in selected if r['engine']==engine])
    quality=dict(collections.Counter(r['quality_admission_status'] for r in rows));summary=json.loads((ROOT/'summary.json').read_text())
    old_media=Path('/data_cached/wangzijun_p25/publication_audit_20261029/metadata')
    # Start from the exact base metadata, changing only affected summary fields.
    for relative in ['README.md','data/README.md',PREFIX+'/README.md',PREFIX+'/PUBLICATION_CHECK.md']:
        text=(old_media/relative).read_text()
        for a,b in [('32,868','32,877'),('36,342','38,163'),('2,790','960'),('69,210','71,040')]:text=text.replace(a,b)
        p=meta/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    check=meta/PREFIX/'PUBLICATION_CHECK.md'
    text=check.read_text().replace('54,354','56,184').replace('31,399',f"{len({r['sha256'] for r in usable}):,}")
    text+='\nT19复核：1,830条Genesis已逐条完成解码、哈希和原始状态检查；9条通过密集事件帧与状态结合复核，1,821条画面复核尚未完成。Isaac的369条修复候选中138条与停用库存同哈希，231条为不同内容；未作为正式替换。\n'
    check.write_text(text)
    root_card=meta/'README.md';root_card.write_text(root_card.read_text()+'\nT19：1,830条Genesis视频已完成解码、哈希与状态检查，其中9条通过画面与状态结合复核，1,821条仍待画面复核。960条Isaac旧版继续停用，修复候选尚未正式替换。\n')
    index=json.loads((old_media/'data/T19/INDEX.json').read_text());index.update(quality_states=dict(collections.Counter(r['quality_admission_status'] for r in selected)),current_scene_media_records=2640,media_revision=state['media_revision']);dump(scene/'INDEX.json',index)
    for engine,n in [('genesis',2640),('isaac',0)]:
        p=scene/engine/'README.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(f'# T19 / {engine}\n\nThis directory has {n} current media records. Use videos_{engine}.jsonl.gz in the parent directory for exact hashes, prompts and per-video admission. Presence does not imply quality acceptance.\n')
    (scene/'README.md').write_text('''# T19 — Object impact arrangements

Version-specific object composition, initial motion, impact geometry, mass and restitution.

| Field | Records |
|---|---:|
| Genesis | 2,640 |
| Isaac | 960 |
| Total | 3,600 |
| Media in current scene directories | 2,640 |
| Registered usable | 819 |
| Pending review | 1,821 |
| Excluded | 960 |

[Complete index](videos.jsonl.gz) · [Genesis index](videos_genesis.jsonl.gz) · [Isaac index](videos_isaac.jsonl.gz)

The 810 author-accepted Genesis videos retain their acceptance. Of the 1,830
recovered Genesis videos, 9 have passed dense event-frame and original-state
review; 1,821 await visual/physical adjudication. All 1,830 completed full decode,
hash and finite position/velocity checks. These technical checks are not visual
acceptance. The 960 retired Isaac records remain excluded. Repair candidates
have not replaced those records. Select members by quality_admission_status.
''')
    indices=json.loads((old_media/PREFIX/'scene_index.json').read_text())
    assert isinstance(indices,list)
    indices=[index if x['quota_scene_id']=='T19' else x for x in indices];dump(dest/'scene_index.json',indices)
    active=json.loads((old_media/'catalog/active_72000.json').read_text());active['usable_records']=len(usable);active['media_revision']=state['media_revision'];dump(meta/'catalog/active_72000.json',active)
    validation=json.loads((old_media/PREFIX/'validation.json').read_text());validation.update(quality_states=quality,usable_entries=len(usable),usable_unique_video_hashes=len({r['sha256'] for r in usable}),nonretired_entries_in_current_repository=71040,excluded_records_kept_as_provenance=960,current_media_files=54354+1830,media_revision=state['media_revision'],manifest_sha256=hashlib.sha256((dest/'videos.jsonl.gz').read_bytes()).hexdigest(),t19_review=summary['genesis_t19']);dump(dest/'validation.json',validation)
    assert len(rows)==72000 and len(usable)==32877 and quality['PENDING_REVIEW']==38163 and quality['UNUSABLE_RETIRED']==960
    head=api.repo_info(repo,repo_type='dataset',expand=['sha']).sha
    commit=api.upload_folder(repo_id=repo,repo_type='dataset',folder_path=str(meta),parent_commit=head,
        commit_message='Record hash-bound T19 review: 9 visually accepted, 1821 awaiting visual review; Isaac retired batch unchanged')
    files=sorted(p for p in meta.rglob('*') if p.is_file());checked=info(repo,[p.relative_to(meta).as_posix() for p in files],commit.oid)
    for p in files:
        b=p.read_bytes();item=checked[p.relative_to(meta).as_posix()];assert item.size==len(b)
        if item.lfs:assert item.lfs.sha256==hashlib.sha256(b).hexdigest()
        else:assert item.blob_id==hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    assert api.repo_info(repo,repo_type='dataset',revision=commit.oid,expand=['private']).private is True
    dump(ROOT/'PUBLISHED.json',{'repo':repo,'revision':commit.oid,'media_revision':state['media_revision'],'all_1830_media_hashes_verified':True,'all_metadata_hashes_verified':True,'counts':summary,'full_visual_review_complete':False,'license_changed':False,'visibility_changed':False})
    print(json.dumps({'published':commit.oid,'counts':summary}),flush=True)


if __name__=='__main__':main()
