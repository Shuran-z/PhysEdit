"""Publish exactly the reviewed Isaac triplet, preserving inputs and original media."""
import collections
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path

logging.disable(logging.CRITICAL)
os.environ['HF_HUB_DISABLE_XET']='1';os.environ['NO_PROXY']='.amazonaws.com'
from huggingface_hub import HfApi,CommitOperationAdd,get_token

ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029/isaac_admission')
PREFIX='releases/72000_release_candidate_20261029';REPO='phy2/phydataset'


def load(p):return json.loads(p.read_text())
def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=True))
def read(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
def write(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,'wt') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=True)+'\n')


def main():
    import fcntl
    lock=open(ROOT/'publish.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    api=HfApi(token=get_token());base=load(ROOT/'base_catalog.json');plan=load(ROOT/'media_plan.json');assert len(plan)==3
    progress=ROOT/'progress.json'
    if progress.exists():state=load(progress)
    else:
        head=api.repo_info(REPO,repo_type='dataset',expand=['sha']).sha
        assert head==base['revision'],'Upstream changed; merge before publishing'
        branch='snapshot-before-qualified-isaac-t19-20261029';api.create_branch(REPO,repo_type='dataset',branch=branch,revision=head,exist_ok=True)
        for r in plan:assert hashlib.sha256(Path(r['source']).read_bytes()).hexdigest()==r['sha256']
        commit=api.create_commit(REPO,repo_type='dataset',parent_commit=head,
            operations=[CommitOperationAdd(path_in_repo=r['destination'],path_or_fileobj=r['source']) for r in plan],
            commit_message='Place individually reviewed Isaac T19 triplet in canonical scene directory')
        state={'media_revision':commit.oid,'initial_revision':head,'backup_branch':branch};dump(progress,state)
    infos={x.path:x for x in api.get_paths_info(REPO,[r['destination'] for r in plan],repo_type='dataset',revision=state['media_revision'])}
    assert all(infos[r['destination']].lfs.sha256==r['sha256'] for r in plan)
    meta=ROOT/'metadata';dest=meta/PREFIX;rows=read(dest/'videos.jsonl.gz');byid={r['video_id']:r for r in rows}
    for p in plan:
        r=byid[p['video_id']];r['source_download']=r.get('source_download') or r['download']
        r['download']={'repo_id':REPO,'revision':state['media_revision'],'path':p['destination'],'member':''};r['media_in_current_scene_directory']=True
    usable=[r for r in rows if r['quality_admission_status'].startswith('USABLE_')];assert len(usable)==32880
    write(dest/'videos.jsonl.gz',rows);write(dest/'usable_videos.jsonl.gz',usable)
    current=Path('/data_cached/wangzijun_p25/t19_review_20261029/metadata')
    prior_unique=load(current/PREFIX/'validation.json')['usable_unique_video_hashes']
    # Read source metadata from the previous exact published version.
    for relative in ['README.md',PREFIX+'/README.md',PREFIX+'/PUBLICATION_CHECK.md']:
        text=(current/relative).read_text().replace('32,877','32,880').replace('| 停用 | 960 |','| 停用 | 957 |').replace('960条只保留固定来源绑定','957条只保留固定来源绑定').replace('71,040','71,043').replace('56,184','56,187')
        text=text.replace(f'{prior_unique:,}',f"{len({r['sha256'] for r in usable}):,}")
        text=text.replace('960条Isaac T19按明确来源限制恢复停用','Isaac T19逐条复核后启用3条，其余957条保留停用')
        text=text.replace('960条Isaac旧版继续停用，修复候选尚未正式替换','Isaac T19已有3条经逐条复核重新启用，其余957条仍停用')
        p=meta/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    (meta/'README.md').write_text((meta/'README.md').read_text()+'\nIsaac T19：当前启用3条同一轨迹的三机位视频，为绕过目标的未命中案例。启用基于逐条画面复核、原物理QA和输入核对，不代表已覆盖T19完整事件分支或完成状态文件恢复。\n')
    selected=[r for r in rows if r['quota_scene']=='T19'];scene=meta/'data/T19'
    write(scene/'videos.jsonl.gz',selected)
    for engine in ['genesis','isaac']:write(scene/f'videos_{engine}.jsonl.gz',[r for r in selected if r['engine']==engine])
    index=load(current/'data/T19/INDEX.json');index.update(quality_states=dict(collections.Counter(r['quality_admission_status'] for r in selected)),current_scene_media_records=2643,media_revision=state['media_revision']);dump(scene/'INDEX.json',index)
    text=(current/'data/T19/README.md').read_text().replace('| Registered usable | 819 |','| Registered usable | 822 |').replace('| Excluded | 960 |','| Excluded | 957 |').replace('| Media in current scene directories | 2,640 |','| Media in current scene directories | 2,643 |').replace('The 960 retired Isaac records remain excluded.','Three individually reviewed Isaac videos are enabled; 957 retired Isaac records remain excluded.')
    (scene/'README.md').write_text(text+'\n[Isaac triplet review and exact evidence](../../'+PREFIX+'/isaac_admission_20261029/status.json). This reactivates existing video bytes, not a new render or critical-boundary certification.\n')
    p=scene/'isaac/README.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# T19 / Isaac\n\n3 videos from one reviewed triplet are currently usable. 957 records remain retired. Use the parent videos_isaac.jsonl.gz index for admission and exact download hashes. Prompts and physical inputs are unchanged.\n')
    indices=load(current/PREFIX/'scene_index.json');dump(dest/'scene_index.json',[index if x['quota_scene_id']=='T19' else x for x in indices])
    pointer=load(current/'catalog/active_72000.json');pointer.update(usable_records=32880,media_revision=state['media_revision']);dump(meta/'catalog/active_72000.json',pointer)
    quality=dict(collections.Counter(r['quality_admission_status'] for r in rows));validation=load(current/PREFIX/'validation.json')
    validation.update(quality_states=quality,usable_entries=32880,usable_unique_video_hashes=len({r['sha256'] for r in usable}),nonretired_entries_in_current_repository=71043,excluded_records_kept_as_provenance=957,current_media_files=56187,media_revision=state['media_revision'],manifest_sha256=hashlib.sha256((dest/'videos.jsonl.gz').read_bytes()).hexdigest(),isaac_t19_reviewed_acceptances=3)
    dump(dest/'validation.json',validation)
    oldstatus=load(current/PREFIX/'t19_review/status.json');oldstatus.update(usable=32880,pending=38163,retired=957,quality_states=quality);oldstatus['isaac_t19']={'retired':957,'reviewed_accepted':3,'replacement_performed':False,'reactivation_of_exact_existing_videos':True};dump(dest/'t19_review/status.json',oldstatus)
    head=api.repo_info(REPO,repo_type='dataset',expand=['sha']).sha;assert head==state['media_revision']
    commit=api.upload_folder(repo_id=REPO,repo_type='dataset',folder_path=str(meta),parent_commit=head,
        commit_message='Enable 3 individually reviewed Isaac T19 videos; retain 957 retired, preserve all prompts and physical parameters')
    files=[p for p in meta.rglob('*') if p.is_file()];infos={x.path:x for x in api.get_paths_info(REPO,[p.relative_to(meta).as_posix() for p in files],repo_type='dataset',revision=commit.oid)}
    for p in files:
        b=p.read_bytes();item=infos[p.relative_to(meta).as_posix()];assert item.size==len(b)
        if item.lfs:assert item.lfs.sha256==hashlib.sha256(b).hexdigest()
        else:assert item.blob_id==hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    assert api.repo_info(REPO,repo_type='dataset',revision=commit.oid,expand=['private']).private is True
    result={'repo':REPO,'revision':commit.oid,'media_revision':state['media_revision'],'counts':load(ROOT/'summary.json'),'metadata_hashes_verified':True,'video_hashes_verified':True,'core100_changed':False,'license_changed':False,'visibility_changed':False};dump(ROOT/'PUBLISHED.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
