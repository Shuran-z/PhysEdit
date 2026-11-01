"""Admit a reviewed updated triplet and separate release availability from QA coverage."""
import collections
import copy
import fcntl
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil

logging.disable(logging.CRITICAL);os.environ['NO_PROXY']='.amazonaws.com';os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import HfApi,CommitOperationCopy,get_token

ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029');OUT=ROOT/'updated_admission'
BASE=ROOT/'isaac_admission/metadata';PREFIX='releases/72000_release_candidate_20261029'
EXPECTED='16cfc2b67fdfe1de274b088d830a06a3095d23fb';REPO='phy2/phydataset'


def load(p):return json.loads(p.read_text())
def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=True))
def read(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
def write(p,rs):
    p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,'wt') as f:
        for r in rs:f.write(json.dumps(r,ensure_ascii=True)+'\n')


def main():
    raise RuntimeError('Superseded by publish_t19_standard_update_remote.py; dated release layout must not be recreated.')
    OUT.mkdir(exist_ok=True);lock=open(OUT/'publish.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    api=HfApi(token=get_token());rows=read(BASE/PREFIX/'videos.jsonl.gz')
    selected=load(ROOT/'updated_selected/records.json');assert len(selected)==3
    checks={r['video_id']:r for r in load(ROOT/'updated_media_review/input_checks.json')}
    byid={r['video_id']:r for r in rows};progress=OUT/'progress.json'
    if progress.exists():state=load(progress)
    else:
        head=api.repo_info(REPO,repo_type='dataset',expand=['sha']).sha;assert head==EXPECTED
        branch='snapshot-before-updated-t19-triplet-20261030';api.create_branch(REPO,repo_type='dataset',branch=branch,revision=head,exist_ok=True)
        for x in selected:
            assert x['decoded_frames_old_new']==[210,210] and x['fps_old_new']==[30.,30.]
            assert checks[x['video_id']]['same_config_bytes']
            assert hashlib.sha256(Path(x['new_cached_path']).read_bytes()).hexdigest()==x['current_sha256']
            assert x['inventory_sha256']==byid[x['video_id']]['sha256']
        commit=api.create_commit(REPO,repo_type='dataset',parent_commit=head,
            operations=[CommitOperationCopy(src_path_in_repo=x['path'],src_revision=EXPECTED,path_in_repo=byid[x['video_id']]['canonical_path']) for x in selected],
            commit_message='Bind reviewed updated Isaac T19 triplet; preserve original media provenance')
        state={'media_revision':commit.oid,'backup_branch':branch};dump(progress,state)
    info={x.path:x for x in api.get_paths_info(REPO,[byid[x['video_id']]['canonical_path'] for x in selected],repo_type='dataset',revision=state['media_revision'])}
    meta=OUT/'metadata';evidence=meta/PREFIX/'t19_updated_review_20261030';evidence.mkdir(parents=True,exist_ok=True)
    for name in ['input_checks.json','input_summary.json','fetch_errors.json']:
        shutil.copy2(ROOT/'updated_media_review'/name,evidence/name)
    write(evidence/'pixel_comparisons.jsonl.gz',load(ROOT/'updated_media_review/results.json'))
    write(evidence/'all960_source_comparison.jsonl.gz',load(ROOT/'current960_media_comparison.json')['checks'])
    decisions=[]
    for x in selected:
        row=byid[x['video_id']];old=copy.deepcopy(row);assert row['quality_admission_status']=='UNUSABLE_RETIRED'
        assert info[row['canonical_path']].lfs.sha256==x['current_sha256']
        config=checks[x['video_id']];src=Path(config['local_original_config']);qa=src.parent/'metadata/qa.json'
        assert load(qa)['status']=='PASS'
        for source,name in [(src,'config.json'),(qa,'source_qa.json'),(Path(x['dense_evidence']),row['camera']+'_dense.jpg')]:shutil.copy2(source,evidence/name)
        proof={'video_id':row['video_id'],'video_sha256':x['current_sha256'],'decision':'accept','reviewer':'assistant_dense_updated_rgb_review_20261030',
            'evidence':[{'path':'t19_updated_review_20261030/'+row['camera']+'_dense.jpg','sha256':x['dense_evidence_sha256']},
                        {'path':'t19_updated_review_20261030/config.json','sha256':config['config_sha256']}],
            'checks':dict.fromkeys(['identity_geometry','contact_physics','declared_controls','event_visibility','temporal_coverage'],True),
            'rgb_frame_indices':x['rgb_frame_indices'],
            'method':'Dense updated RGB motion sequence, synchronized views, exact original input identity, source physics QA; full video decode',
            'reason':'Single identifiable can passes the tissue box and settles; no persistent duplicated can bodies or visible lasting intersection in reviewed sequence. Table support and both identities remain interpretable.',
            'limits':'Visual inspection uses dense motion frames and temporal samples. Original numerical QA is carried over; no new state recovery or exact boundary truth claimed. Updated bytes show photometric changes; a new simulation/render is not established.'}
        row.setdefault('previous_video_versions',[]).append({'video_sha256':old['sha256'],'download':old['download'],'source_download':old.get('source_download'),'prompt_binding_evidence':old.get('prompt_binding_evidence'),'quality_admission_status':old['quality_admission_status']})
        row.update(sha256=x['current_sha256'],local_source=x['new_cached_path'],storage_host='p25',verified_hash=True,
            source_repo=REPO,source_revision=EXPECTED,source_path=x['path'],archive_member='',
            source_download={'repo_id':REPO,'revision':EXPECTED,'path':x['path'],'member':''},
            download={'repo_id':REPO,'revision':state['media_revision'],'path':row['canonical_path'],'member':''},
            media_in_current_scene_directory=True,quality_admission_status='USABLE_VERIFIED_VISUAL_PHYSICS',visual_physics_adjudication=proof,
            quality_reactivation={'authorization':'author_20261029_use_qualified_isaac_t19','video_sha256':x['current_sha256'],'decision':'accept','reviewer':proof['reviewer'],'evidence':proof['evidence'],'original_admission':'UNUSABLE_RETIRED','mode':'reviewed_updated_video_with_identical_declared_inputs'},
            prompt_binding_method='unchanged_text_rebound_to_reviewed_updated_video_with_identical_source_config',
            state_availability_note='Original state not recovered; do not infer state-dependent evaluation eligibility from video admission.')
        row['prompt_binding_evidence']={'video_sha256':x['current_sha256'],'derived_from_video_sha256':old['sha256'],'source_config_sha256':config['config_sha256'],'source_config_bytes_identical':True,'reviewed_new_version':True,'prior_binding_preserved_in':'previous_video_versions'}
        row['media_version_update']={'previous_sha256':old['sha256'],'current_sha256':x['current_sha256'],
            'input_config_bytes_identical':True,'new_media_hf_sha_verified':True,'source_revision':EXPECTED,
            'source_path':x['path'],'scope':'same declared input, individually reviewed updated video; no new critical truth claimed'}
        assert all(row[k]==old[k] for k in ['prompt_variants_en','prompt_variant_sha256','parameter_facts','native_sample_id','camera','canonical_path'])
        decisions.append(proof)
    quality=dict(collections.Counter(r['quality_admission_status'] for r in rows));usable=[r for r in rows if r['quality_admission_status'].startswith('USABLE_')];available=[r for r in rows if not r['quality_admission_status'].startswith('UNUSABLE_')]
    assert len(rows)==72000 and len(usable)==32883 and len(available)==71046 and quality['UNUSABLE_RETIRED']==954 and quality['PENDING_REVIEW']==38163
    dest=meta/PREFIX;write(dest/'videos.jsonl.gz',rows);write(dest/'usable_videos.jsonl.gz',usable);write(dest/'nonretired_videos.jsonl.gz',available);write(evidence/'decisions.jsonl.gz',decisions)
    summary={'total':72000,'available_nonretired':71046,'accepted_evidence':32883,'visual_review_pending':38163,'retired':954,'newly_accepted_updated_videos':3,'isaac_t19_accepted_total':6,'updated_files_identified':246,'unchanged_files':714,'updated_input_configurations':86,'new_simulation_or_render_confirmed':False,'full_visual_review_complete':False,'availability_is_not_quality_certification':True};dump(evidence/'status.json',summary);dump(OUT/'summary.json',summary)
    prior=load(BASE/PREFIX/'validation.json');oldunique=prior['unique_video_hashes'];newunique=len({r['sha256'] for r in rows})
    for relative in ['README.md',PREFIX+'/README.md',PREFIX+'/PUBLICATION_CHECK.md']:
        text=(BASE/relative).read_text().replace('32,880','32,883').replace('| 停用 | 957 |','| 停用 | 954 |').replace('957条只保留固定来源绑定','954条只保留固定来源绑定').replace('71,043','71,046').replace('56,187','56,190')
        text=text.replace(f'{oldunique:,}',f'{newunique:,}').replace(f"{prior['usable_unique_video_hashes']:,}",f"{len({r['sha256'] for r in usable}):,}")
        text=text.replace('其余957条','其余954条').replace('Isaac T19已有3条','Isaac T19已有6条').replace('启用3条，其余954条','启用6条，其余954条')
        p=meta/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    card=meta/'README.md';text=card.read_text().replace('| 可用 | 32,883 |','| 已有验收依据 | 32,883 |').replace('| 待复核 | 38,163 |','| 待完成逐条复核 | 38,163 |').replace('| 停用 | 954 |','| 暂停准入 | 954 |')
    # Replace the short earlier triplet note with the current complete scope.
    text=text.split('\nIsaac T19：当前启用3条同一轨迹')[0]
    text+='\n## 发布范围与复核覆盖\n\n当前非停用发布范围为71,046条，其中32,883条已有验收依据，38,163条尚未完成逐条复核。待复核不表示已确认存在质量缺陷；已知或按来源政策暂停准入的954条另列。下载全部非停用记录可使用`nonretired_videos.jsonl.gz`与下载工具的`--admission nonretired`。该范围不能表述为全部通过画面或物理质量认证。\n\nIsaac T19已逐条启用6条、来自两组三机位轨迹，其中3条采用本轮核查的更新画面。更新文件不自动提供新的临界真值或状态测量资格。\n'
    card.write_text(text)
    release=meta/PREFIX/'README.md';release.write_text(release.read_text()+'\n`nonretired_videos.jsonl.gz`包含71,046条非停用发布记录，包括38,163条待完成逐条复核的记录；`usable_videos.jsonl.gz`包含32,883条已有验收依据的记录。两者不是相互独立的数据集。\n')
    selected_rows=[r for r in rows if r['quota_scene']=='T19'];scene=meta/'data/T19';write(scene/'videos.jsonl.gz',selected_rows)
    for engine in ['genesis','isaac']:write(scene/f'videos_{engine}.jsonl.gz',[r for r in selected_rows if r['engine']==engine])
    index=load(BASE/'data/T19/INDEX.json');index.update(quality_states=dict(collections.Counter(r['quality_admission_status'] for r in selected_rows)),current_scene_media_records=2646,media_revision=state['media_revision']);dump(scene/'INDEX.json',index)
    text=(BASE/'data/T19/README.md').read_text().replace('| Registered usable | 822 |','| Registered usable | 825 |').replace('| Excluded | 957 |','| Excluded | 954 |').replace('| Media in current scene directories | 2,643 |','| Media in current scene directories | 2,646 |').replace('Three individually reviewed Isaac videos are enabled; 957 retired Isaac records remain excluded.','Six individually reviewed Isaac videos are enabled; 954 retired Isaac records remain excluded.')
    (scene/'README.md').write_text(text+'\n[Updated T19 media investigation](../../'+PREFIX+'/t19_updated_review_20261030/status.json). 246 files differ from the old inventory; this is not proof that all were resimulated or that all ghosting was repaired.\n')
    p=scene/'isaac/README.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# T19 / Isaac\n\n6 videos from two individually reviewed triplets are usable; 954 remain excluded. One triplet uses updated media with identical declared inputs. Use the parent videos_isaac.jsonl.gz for exact versions, hashes and admission states.\n')
    indices=load(BASE/PREFIX/'scene_index.json');dump(dest/'scene_index.json',[index if x['quota_scene_id']=='T19' else x for x in indices])
    pointer=load(BASE/'catalog/active_72000.json');pointer.update(usable_records=32883,nonretired_records=71046,nonretired_manifest_path=PREFIX+'/nonretired_videos.jsonl.gz',media_revision=state['media_revision']);dump(meta/'catalog/active_72000.json',pointer)
    prior.update(quality_states=quality,usable_entries=32883,unique_video_hashes=newunique,usable_unique_video_hashes=len({r['sha256'] for r in usable}),nonretired_entries_in_current_repository=71046,excluded_records_kept_as_provenance=954,current_media_files=56190,media_revision=state['media_revision'],manifest_sha256=hashlib.sha256((dest/'videos.jsonl.gz').read_bytes()).hexdigest(),isaac_t19_reviewed_acceptances=6,release_availability_count=71046,availability_is_not_full_quality_certification=True);dump(dest/'validation.json',prior)
    for oldpath in ['t19_review/status.json','isaac_admission_20261029/status.json']:
        oldstatus=load(BASE/PREFIX/oldpath)
        if 'quality_states' in oldstatus:oldstatus['quality_states']=quality
        oldstatus.update(current_total_usable=32883,current_pending=38163,current_retired=954,superseded_totals_note='See catalog/active_72000.json and current validation.json for current totals; original per-round decisions retained.')
        dump(dest/oldpath,oldstatus)
    head=api.repo_info(REPO,repo_type='dataset',expand=['sha']).sha;assert head==state['media_revision']
    commit=api.upload_folder(repo_id=REPO,repo_type='dataset',folder_path=str(meta),parent_commit=head,commit_message='Use reviewed updated T19 triplet and separate nonretired availability from quality review coverage')
    files=[p for p in meta.rglob('*') if p.is_file()];infos={x.path:x for x in api.get_paths_info(REPO,[p.relative_to(meta).as_posix() for p in files],repo_type='dataset',revision=commit.oid)}
    for p in files:
        b=p.read_bytes();item=infos[p.relative_to(meta).as_posix()];assert item.size==len(b)
        if item.lfs:assert item.lfs.sha256==hashlib.sha256(b).hexdigest()
        else:assert item.blob_id==hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    assert api.repo_info(REPO,repo_type='dataset',revision=commit.oid,expand=['private']).private is True
    result={'repo':REPO,'revision':commit.oid,'media_revision':state['media_revision'],'counts':summary,'video_and_metadata_hashes_verified':True,'core100_changed':False,'license_changed':False,'visibility_changed':False};dump(OUT/'PUBLISHED.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
