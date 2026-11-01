"""Merge three reviewed updated videos into the current standard release.

Preserves the author's full release acceptance, training split, and prompt text.
"""
import os, json, gzip, hashlib, copy, collections, time, shutil, logging, fcntl
from pathlib import Path
logging.disable(logging.CRITICAL)
os.environ['NO_PROXY']='.amazonaws.com';os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import HfApi, CommitOperationCopy, get_token
ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029')
BASE=ROOT/'current_standard_base';OUT=ROOT/'standard_updated_admission'
REPO='phy2/phydataset';SOURCE_REV='16cfc2b67fdfe1de274b088d830a06a3095d23fb'
def load(p):return json.loads(p.read_text())
def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=True,indent=2))
def read(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
def write(p,rs):
    p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,'wt') as f:
        for r in rs:f.write(json.dumps(r,ensure_ascii=True)+'\n')
def retry(fn):
    for i in range(8):
        try:return fn()
        except Exception:
            if i==7:raise
            time.sleep(2)
def main():
    OUT.mkdir(exist_ok=True);lock=open(OUT/'publish.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    api=HfApi(token=get_token());base=load(BASE/'BASE.json');head=base['head'];pointer=base['pointer']
    path=pointer['manifest_path'];rows=read(BASE/path);byid={r['video_id']:r for r in rows}
    selected=load(ROOT/'updated_selected/records.json');checks={r['video_id']:r for r in load(ROOT/'updated_media_review/input_checks.json')}
    assert len(selected)==3 and len(rows)==72000
    assert all(r['author_accepted'] for r in rows)
    progress=OUT/'progress.json'
    if progress.exists():state=load(progress)
    else:
        assert retry(lambda:api.repo_info(REPO,repo_type='dataset',expand=['sha']).sha)==head,'Publication changed; fetch current base before merging'
        retry(lambda:api.create_branch(REPO,repo_type='dataset',branch='snapshot-before-t19-standard-update-20261030',revision=head,exist_ok=True))
        for x in selected:
            assert x['decoded_frames_old_new']==[210,210] and checks[x['video_id']]['same_config_bytes']
            assert byid[x['video_id']]['sha256']==x['inventory_sha256']
            assert hashlib.sha256(Path(x['new_cached_path']).read_bytes()).hexdigest()==x['current_sha256']
        c=api.create_commit(REPO,repo_type='dataset',parent_commit=head,operations=[CommitOperationCopy(src_path_in_repo=x['path'],src_revision=SOURCE_REV,path_in_repo=byid[x['video_id']]['canonical_path']) for x in selected],commit_message='Bind reviewed updated T19 media with exact original inputs')
        state={'media_revision':c.oid,'base_revision':head};dump(progress,state)
    info={x.path:x for x in retry(lambda:api.get_paths_info(REPO,[byid[x['video_id']]['canonical_path'] for x in selected],repo_type='dataset',revision=state['media_revision']))}
    meta=OUT/'metadata';prefix='releases/physedit/provenance/quality_review/t19_updated_20261030';ev=meta/prefix;ev.mkdir(parents=True,exist_ok=True)
    decisions=[]
    for x in selected:
        r=byid[x['video_id']];old=copy.deepcopy(r);cfg=checks[x['video_id']]
        assert info[r['canonical_path']].lfs.sha256==x['current_sha256']
        src=Path(cfg['local_original_config']);qa=src.parent/'metadata/qa.json';assert load(qa)['status']=='PASS'
        for source,name in [(src,'config.json'),(qa,'source_qa.json'),(Path(x['dense_evidence']),r['camera']+'_dense.jpg')]:shutil.copy2(source,ev/name)
        evidence=[{'path':prefix+'/'+r['camera']+'_dense.jpg','sha256':x['dense_evidence_sha256']},{'path':prefix+'/config.json','sha256':cfg['config_sha256']}]
        proof={'video_sha256':x['current_sha256'],'video_id':r['video_id'],'decision':'accept','reviewer':'assistant_dense_updated_rgb_review_20261030','evidence':evidence,'checks':dict.fromkeys(['identity_geometry','contact_physics','declared_controls','event_visibility','temporal_coverage'],True),'rgb_frame_indices':x['rgb_frame_indices'],'reason':'One coherent can bypasses the tissue box and settles. No persistent duplicate bodies or lasting intersection observed in the reviewed motion sequence.','limits':'Dense sampled RGB and original source QA; no recovered state or new boundary truth. Photometric changes do not establish a new simulation.'}
        r.setdefault('previous_video_versions',[]).append({'video_sha256':old['sha256'],'download':old['download'],'source_download':old.get('source_download'),'prompt_binding_evidence':old.get('prompt_binding_evidence'),'quality_admission_status':old['quality_admission_status']})
        r.update(sha256=x['current_sha256'],local_source=x['new_cached_path'],storage_host='p25',verified_hash=True,source_repo=REPO,source_revision=SOURCE_REV,source_path=x['path'],archive_member='',source_download={'repo_id':REPO,'revision':SOURCE_REV,'path':x['path'],'member':''},download={'repo_id':REPO,'revision':state['media_revision'],'path':r['canonical_path'],'member':''},media_in_current_scene_directory=True,quality_admission_status='USABLE_VERIFIED_VISUAL_PHYSICS',visual_physics_adjudication=proof,quality_reactivation={'authorization':'author_20261029_use_qualified_isaac_t19','video_sha256':x['current_sha256'],'decision':'accept','reviewer':proof['reviewer'],'evidence':evidence,'original_admission':old['quality_admission_status']},state_availability_note='Original state not recovered; video acceptance alone does not grant state-dependent evaluation eligibility.')
        r['prompt_binding_evidence']={'video_sha256':x['current_sha256'],'derived_from_video_sha256':old['sha256'],'source_config_sha256':cfg['config_sha256'],'source_config_bytes_identical':True,'prior_binding_preserved_in':'previous_video_versions'}
        r['media_version_update']={'previous_sha256':old['sha256'],'current_sha256':x['current_sha256'],'input_config_bytes_identical':True,'new_media_hf_sha_verified':True,'source_revision':SOURCE_REV,'source_path':x['path']}
        assert all(r[k]==old[k] for k in ['prompt_variants_en','prompt_variant_sha256','parameter_facts','split','author_accepted','training_ready'])
        decisions.append(proof)
    # Only the three targeted rows change. Training membership and prompts stay frozen.
    original={r['video_id']:r for r in read(BASE/path)};changed={x['video_id'] for x in selected}
    assert all(r==original[r['video_id']] for r in rows if r['video_id'] not in changed)
    assert sum(r['training_ready'] for r in rows)==sum(r['training_ready'] for r in original.values())
    write(meta/path,rows)
    scene=[r for r in rows if r['quota_scene']=='T19']
    for directory in ['data/T19']:
        write(meta/directory/'videos.jsonl.gz',scene)
        for engine in ['genesis','isaac']:write(meta/directory/f'videos_{engine}.jsonl.gz',[r for r in scene if r['engine']==engine])
    for engine in ['genesis','isaac']:
        write(meta/f'releases/physedit/catalog/by_scene/{engine}__T19.jsonl.gz',[r for r in scene if r['engine']==engine])
    index=load(BASE/'data/T19/INDEX.json');index.update(quality_states=dict(collections.Counter(r['quality_admission_status'] for r in scene)),current_scene_media_records=sum(bool(r.get('media_in_current_scene_directory')) for r in scene),media_revision=state['media_revision'],author_accepted_records=3600,quality_states_role='historical evidence coverage, not release admission')
    dump(meta/'data/T19/INDEX.json',index)
    indices=load(BASE/'releases/physedit/catalog/scene_index.json')
    dump(meta/'releases/physedit/catalog/scene_index.json',[index if x['quota_scene_id']=='T19' else x for x in indices])
    pointer.update(media_revision=state['media_revision']);dump(meta/'catalog/active_72000.json',pointer)
    text='# T19 — Object impact arrangements\n\n3,600 author-accepted release records: 2,640 Genesis and 960 Isaac. Full-release acceptance and training/holdout selection follow the standard catalog; older QA labels describe evidence coverage and do not override author acceptance.\n\nSix Isaac videos have individual dense visual-review evidence. Three use updated, brighter files with byte-identical declared input configurations. Across the 960 Isaac source files, 246 differ from the old inventory and 714 are unchanged. Updated bytes alone do not prove that every ghosting problem was fixed.\n\n[Video index](videos.jsonl.gz) · [Updated-video checks and decisions](../../'+prefix+'/status.json). Original versions and per-video hashes remain recorded. No new state-dependent or critical-boundary certification is implied.\n'
    (meta/'data/T19/README.md').write_text(text)
    write(ev/'decisions.jsonl.gz',decisions);write(ev/'pixel_comparisons.jsonl.gz',load(ROOT/'updated_media_review/results.json'))
    write(ev/'all960_source_comparison.jsonl.gz',load(ROOT/'current960_media_comparison.json')['checks'])
    shutil.copy2(ROOT/'updated_media_review/input_checks.json',ev/'input_checks.json')
    summary={'author_accepted_release_records':72000,'training_records':pointer['train_records'],'newly_bound_reviewed_videos':3,'isaac_t19_individually_reviewed':6,'updated_source_files':246,'unchanged_source_files':714,'all_updated_files_full_decoded':True,'all_updated_configs_identical':True,'new_simulation_confirmed':False,'all_T19_ghosting_fixed':False,'historical_quality_states':dict(collections.Counter(r['quality_admission_status'] for r in rows))}
    dump(ev/'status.json',summary)
    assert retry(lambda:api.repo_info(REPO,repo_type='dataset',expand=['sha']).sha)==state['media_revision'],'Concurrent metadata change; merge again'
    commit=api.upload_folder(repo_id=REPO,repo_type='dataset',folder_path=str(meta),parent_commit=state['media_revision'],commit_message='Use reviewed updated T19 triplet; preserve author acceptance, prompts and training split')
    files=[p for p in meta.rglob('*') if p.is_file()];infos={x.path:x for x in retry(lambda:api.get_paths_info(REPO,[p.relative_to(meta).as_posix() for p in files],repo_type='dataset',revision=commit.oid))}
    for p in files:
        b=p.read_bytes();item=infos[p.relative_to(meta).as_posix()];assert item.size==len(b)
        if item.lfs:assert item.lfs.sha256==hashlib.sha256(b).hexdigest()
        else:assert item.blob_id==hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    receipt={'repo':REPO,'revision':commit.oid,'media_revision':state['media_revision'],'counts':summary,'all_uploaded_hashes_verified':True,'prompts_changed':False,'training_membership_changed':False,'core100_changed':False,'base_revision':head}
    dump(OUT/'PUBLISHED.json',receipt);print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
