"""Build the active media inventory from immutable baseline and completed receipts.

Does not grant physical acceptance, change Core100, or rename T14S into T14.
"""
import collections
import copy
import base64
import csv
import datetime
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

from boundary_ssh import remote_text

REPO = Path(__file__).resolve().parents[1]
BASE = REPO.parent / 'release_standardization_20261028_880_audit'
OUT = REPO.parent / 'release_72000_active'
ROOTS = {
    'p25': ['/data_cached/wangzijun_p25/t18_t19_resume_current880_20261028',
            '/data_cached/wangzijun_p25/t18_t19_parallel_return_20261028',
            '/data_cached/wangzijun_p25/t18_t19_oom_retry_20261028',
            '/data_cached/wangzijun_p25/t19_stall_recovery_20261029',
            '/data_cached/wangzijun_p25/t19_scaleout_20261029',
            '/data_cached/wangzijun_p25/t19_p26_recovery_20261029'],
    'sg88': ['/data/yangkaiyuan/t18_t19_resume_20261028'],
}

# Conservative source-evidence tiers. These are not a new physical acceptance test.
SOURCE_ACCEPTED = {'published_acceptance_record', 'published_canonical_qa_pass',
                   'SOURCE_QA_PASS', 'SOURCE_DELIVERY_ACCEPTED'}

def admission(row):
    quality = row['source_quality']
    if quality == 'REVIEW_ONLY_RETIRED_REFERENCE_NOT_REACTIVATED':
        reactivation = row.get('quality_reactivation')
        if not reactivation:
            return 'UNUSABLE_RETIRED'
        # Authorizations are separate: Genesis re-review and the later request
        # to use individually qualified Isaac T19. Neither is batch approval.
        assert row['scene']=='T19'
        authorized={'genesis':'author_20261029_review_genesis1830_keep_qualified',
                    'isaac':'author_20261029_use_qualified_isaac_t19'}
        assert reactivation['authorization']==authorized[row['engine']]
        assert reactivation['video_sha256']==row['sha256']
        assert reactivation.get('evidence') and reactivation.get('reviewer')
        assert reactivation['decision'] in {'accept','reject','review'}
        reviewed=row.get('visual_physics_adjudication')
        assert reviewed and reviewed['video_sha256']==row['sha256']
        assert reviewed['decision']==reactivation['decision']
        if reactivation['decision']=='review' and (row.get('post_render_audit') or {}).get('media_and_state_integrity')!='FAIL':
            return 'PENDING_REVIEW'
    audit = row.get('post_render_audit') or {}
    if audit.get('media_and_state_integrity') == 'FAIL':
        return 'UNUSABLE_INTEGRITY_FAILURE'
    author = row.get('author_acceptance')
    if author:
        assert author['video_sha256'] == row['sha256']
        assert author['decision'] == 'author_accept' and author.get('evidence')
        return 'USABLE_AUTHOR_ACCEPTED'
    reviewed=row.get('visual_physics_adjudication')
    if reviewed:
        assert reviewed['video_sha256']==row['sha256'], 'Review applies to different video bytes'
        assert reviewed.get('reviewer') and reviewed.get('evidence')
        if reviewed['decision']=='reject':
            assert reviewed.get('reason')
            return 'UNUSABLE_VISUAL_PHYSICS_FAILURE'
        if reviewed['decision']=='accept':
            required=['identity_geometry','contact_physics','declared_controls','event_visibility','temporal_coverage']
            assert all(reviewed.get('checks',{}).get(k) is True for k in required), 'Incomplete physical/visual acceptance'
            return 'USABLE_VERIFIED_VISUAL_PHYSICS'
    if quality in SOURCE_ACCEPTED:
        return 'USABLE_PER_EXISTING_SOURCE_ACCEPTANCE'
    return 'PENDING_REVIEW'

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=True, indent=2), encoding='utf8')
    tmp.replace(path)


def choose_completed_receipt(a, b, published_hashes):
    """Resolve retries by immutable published bytes, never by receipt order/date."""
    first={v['camera']:v['sha256'] for v in a['results']}
    second={v['camera']:v['sha256'] for v in b['results']}
    if first==second:return 1
    if published_hashes and first==published_hashes:return 0
    if published_hashes and second==published_hashes:return 1
    raise ValueError('Conflicting completed receipts do not match the current published triplet')


def apply_prompt_completions(rows):
    """Keep published exact-media prompt bindings during later inventory refreshes."""
    pointer=OUT/'ACTIVE_PROMPTS.json'
    if not pointer.exists():return
    active=json.loads(pointer.read_text(encoding='utf8'))
    if 'patch' not in active:
        # Unified prompts are carried by the complete current catalog below.
        assert active.get('manifest') and active.get('manifest_sha256')
        assert active.get('policy')=='core100-aligned-compact-three-prompts'
        assert (OUT/'ACTIVE_CATALOG.json').exists()
        return
    path=Path(active['patch'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==active['patch_sha256']
    with gzip.open(path,'rt',encoding='utf8') as f:
        patches={r['video_id']:r for r in map(json.loads,f)}
    for row in rows:
        patch=patches.get(row['video_id'])
        if not patch:continue
        assert patch['video_sha256']==row['sha256'], 'Prompt patch belongs to different video bytes'
        assert patch['native_sample_id']==row['native_sample_id'] and patch['camera']==row['camera']
        if row.get('prompt_variants_en'):
            assert row['prompt_variants_en']==patch['prompt_variants_en'], 'Existing prompt binding differs'
        row.update(patch)


def apply_current_catalog_metadata(rows):
    """Retain exact-media published names, units, download bindings and explicit source exclusions."""
    pointer=OUT/'ACTIVE_CATALOG.json'
    if not pointer.exists():return
    active=json.loads(pointer.read_text(encoding='utf8'));path=Path(active['manifest'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==active['manifest_sha256']
    wanted={r['video_id']:r for r in rows}
    with gzip.open(path,'rt',encoding='utf8') as f:
        for line in f:
            frozen=json.loads(line);row=wanted.get(frozen['video_id'])
            if row is None:continue
            if row['sha256']!=frozen['sha256']:
                apply_reviewed_media_version(row,frozen)
                continue
            for key,value in frozen.items():
                if key.startswith(('prompt_','canonical_','parameter_unit_')) or key in {
                    'parameter_facts','selected_parameter_keys','external_control_disclosure','external_control_inputs',
                    'download','source_download','media_in_current_scene_directory','native_scene_id',
                    'scene_title_en','scene_description_en','naming_schema','state_availability_note',
                    'author_accepted','training_ready','split','source_group_id','quality_labels_role'}:
                    row[key]=value
            for key in ['quality_reactivation','visual_physics_adjudication']:
                if frozen.get(key):row[key]=frozen[key]
            if frozen.get('quality_source_restriction_evidence'):
                row['source_quality']='REVIEW_ONLY_RETIRED_REFERENCE_NOT_REACTIVATED'
                row['quality_source_restriction_evidence']=frozen['quality_source_restriction_evidence']
                row['source_quality_unchanged']=False


def apply_reviewed_media_version(row, frozen):
    """Carry a published exact-media replacement through later inventory refreshes."""
    update=frozen.get('media_version_update')
    if not update:return False
    assert row['video_id']==frozen['video_id']
    assert row['engine']==frozen['engine']=='isaac' and row['scene']==frozen['scene']=='T19'
    assert update['previous_sha256']==row['sha256'] and update['current_sha256']==frozen['sha256']
    assert any(v['video_sha256']==row['sha256'] for v in frozen.get('previous_video_versions',[]))
    assert update['input_config_bytes_identical'] is True and update['new_media_hf_sha_verified'] is True
    assert frozen['quality_reactivation']['authorization']=='author_20261029_use_qualified_isaac_t19'
    assert admission(frozen)=='USABLE_VERIFIED_VISUAL_PHYSICS'
    row.update(copy.deepcopy(frozen));return True

def collect(host):
    code = '''import pathlib,json,gzip,base64
result={'receipts':[],'statuses':[],'plan':[],'quality':[]}
for root in ROOTS:
 r=pathlib.Path(root)
 for p in (r/'receipts').glob('*.json'):
  x=json.loads(p.read_text(encoding='utf8'));x['receipt_path']=str(p);result['receipts'].append(x)
 for name in ['tuning_status.json','status.json']:
  p=r/name
  if p.exists(): result['statuses'].append(dict(path=str(p),data=json.loads(p.read_text(encoding='utf8'))))
 if (r/'plan.json').exists():result['plan'].extend(json.loads((r/'plan.json').read_text(encoding='utf8')))
q=pathlib.Path(ROOTS[0]).parent/'supplement_quality_20261028'
for p in (q/'results').glob('*.json'):result['quality'].append(json.loads(p.read_text(encoding='utf8')))
print(base64.b64encode(gzip.compress(json.dumps(result).encode(),compresslevel=3)).decode())
'''.replace('ROOTS', repr(ROOTS[host]))
    if host in ('p25', 'p26'):
        data = remote_text(host, code, timeout=60, attempts=2)
    else:
        p = subprocess.run(['ssh', '-i', str(Path.home()/'.ssh/id_ed25519_sg88n5'),
            '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
            'yangkaiyuan@172.25.72.115', 'python3 -'], input=code.encode(),
            capture_output=True, timeout=60, check=True)
        data = p.stdout.decode()
    result = json.loads(gzip.decompress(base64.b64decode(data)))
    save(OUT / ('receipts_' + host + '.json'), result)
    return result

def main():
    OUT.mkdir(exist_ok=True)
    with gzip.open(BASE/'videos_with_three_prompts.jsonl.gz', 'rt', encoding='utf8') as f:
        rows = [json.loads(line) for line in f]
    assert len(rows) == 69087
    for row in rows:
        row.update(storage_host='p25', quota_scene=row['scene'], inventory_origin='baseline')
    replacement = json.loads((BASE/'t14s_authorized_replacement_manifest.json').read_text(encoding='utf8'))
    assert len(replacement['videos']) == 960
    inputs_path=OUT/'t14s_source_inputs.json'
    inputs={r['sample_id']:r for r in json.loads(inputs_path.read_text(encoding='utf8'))} if inputs_path.exists() else {}
    for v in replacement['videos']:
        sid = v['sample_id']; camera = v['camera']
        row = dict(video_id=sid+'__'+camera, native_sample_id=sid, sample_id=sid,
            scene='T14S', quota_scene='T14', engine='isaac', camera=camera,
            background=re.search(r'bg\d+', sid).group(), gravity=re.search(r'__(g\d+)_', sid).group(1),
            local_source=v['path'], storage_host='p25', sha256=v['sha256'], verified_hash=True,
            source_quality='SOURCE_DELIVERY_ACCEPTED' if v['source_accepted'] else 'SOURCE_REVIEW_REQUIRED',
            source_input_evidence=inputs.get(sid),
            prompt_binding_status='PENDING_T14S_SOURCE_BINDING', inventory_origin='authorized_T14S_replacement')
        rows.append(row)
    completed = {}; plans = {}; plans_by_host = {}; failures = {}; quality = {}
    published_triplets={};receipt_conflicts=[]
    catalog_pointer=OUT/'ACTIVE_CATALOG.json'
    if catalog_pointer.exists():
        catalog=json.loads(catalog_pointer.read_text(encoding='utf8'))
        published_manifest=Path(catalog['manifest'])
        assert hashlib.sha256(published_manifest.read_bytes()).hexdigest()==catalog['manifest_sha256']
        with gzip.open(published_manifest,'rt',encoding='utf8') as f:
            for r in map(json.loads,f):
                if r.get('inventory_origin')=='supplement_render':
                    published_triplets.setdefault(r['native_sample_id'],{})[r['camera']]=r['sha256']
    for host in ROOTS:
        result = collect(host)
        quality.update({r['sample']:r for r in result['quality']})
        for plan in result['plan']:
            plans[plan['sample']] = plan
            plans_by_host[(host, plan['sample'])] = plan
        for receipt in result['receipts']:
            sid = receipt['sample']
            if receipt.get('error'): failures[sid] = dict(host=host, error=receipt['error'])
            if receipt.get('media_complete'):
                assert len(receipt['results']) == 3
                assert {v['camera'] for v in receipt['results']} == {'cam01','cam02','cam03'}
                assert all(v['media_pass'] for v in receipt['results'])
                if receipt.get('trajectory'):
                    assert receipt['trajectory']['compression_verified']
                if sid in completed:
                    a={v['camera']:v['sha256'] for v in completed[sid][1]['results']}
                    b={v['camera']:v['sha256'] for v in receipt['results']}
                    if a != b:
                        selected=choose_completed_receipt(completed[sid][1],receipt,published_triplets.get(sid))
                        receipt_conflicts.append(dict(sample=sid,selected=selected,
                            previous_receipt=completed[sid][1]['receipt_path'],candidate_receipt=receipt['receipt_path'],
                            previous_hashes=a,candidate_hashes=b,basis='Exact current published triplet; unselected render not deleted or admitted'))
                        if selected==0:continue
                completed[sid] = (host, receipt)
    save(OUT/'unselected_retry_receipts.json',receipt_conflicts)
    assert len(plans) == 651, len(plans)
    for sid, (host, receipt) in sorted(completed.items()):
        assert sid in plans
        for v in receipt['results']:
            rows.append(dict(video_id=sid+'__'+v['camera'], native_sample_id=sid, sample_id=sid,
                scene=plans[sid]['scene'], quota_scene=plans[sid]['scene'], engine='genesis', camera=v['camera'],
                background=re.search(r'bg\d+',sid).group(), gravity=re.search(r'__(g\d+)_',sid).group(1),
                local_source=v['video'], storage_host=host, sha256=v['sha256'], verified_hash=True,
                source_quality='NEW_RENDER_PHYSICS_VISUAL_REVIEW_REQUIRED',
                media_validation='PASS', receipt_path=receipt['receipt_path'],
                trajectory=receipt.get('trajectory'), inventory_origin='supplement_render',
                post_render_audit=quality.get(sid),
                source_render_configs=plans_by_host[(host, sid)]['configs'],
                prompt_binding_status='PENDING_ORIGINAL_CONFIG_BINDING'))
    apply_prompt_completions(rows)
    apply_current_catalog_metadata(rows)
    decisions_path=OUT/'visual_review'/'adjudications.jsonl'
    decisions={}
    if decisions_path.exists():
        for line in decisions_path.read_text(encoding='utf8').splitlines():
            d=json.loads(line);key=d['video_id']
            assert key not in decisions, 'Duplicate visual adjudication'
            decisions[key]=d
    author_path=OUT/'visual_review'/'author_acceptance_20261029.jsonl'
    author_decisions={d['video_id']:d for d in (map(json.loads,author_path.read_text(encoding='utf8').splitlines()) if author_path.exists() else [])}
    for row in rows:
        if row['video_id'] in decisions:row['visual_physics_adjudication']=decisions[row['video_id']]
        if row['video_id'] in author_decisions:row['author_acceptance']=author_decisions[row['video_id']]
        row['quality_admission_status']=admission(row)
    keys=[(r['engine'],r['native_sample_id'],r['camera']) for r in rows]
    assert len(keys)==len(set(keys)), 'Duplicate source sample-camera'
    counts=collections.Counter((r['engine'],r['quota_scene']) for r in rows)
    cells=collections.Counter((r['engine'],r['quota_scene'],r['background'],r['gravity']) for r in rows)
    for key,n in cells.items(): assert n <= (132 if key[0]=='genesis' else 48), (key,n)
    table=[]
    for scene in ['T%02d'%i for i in range(1,21)]:
        g=counts['genesis',scene]; i=counts['isaac',scene]
        table.append(dict(quota_scene=scene,genesis=g,isaac=i,total=g+i,missing=3600-g-i,
                          isaac_actual_scene='T14S' if scene=='T14' else scene))
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    snapshot=OUT/'snapshots'/stamp; snapshot.mkdir(parents=True,exist_ok=False)
    manifest=snapshot/'videos.jsonl.gz'
    with gzip.open(manifest,'wt',encoding='utf8') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    with (snapshot/'scene_counts.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    pending={sid:dict(scene=p['scene'],failure=failures.get(sid)) for sid,p in plans.items() if sid not in completed}
    save(snapshot/'remaining_render_tasks.json',pending)
    tiers=collections.Counter(r['quality_admission_status'] for r in rows)
    admission_counts=dict(usable_per_existing_source_acceptance=tiers['USABLE_PER_EXISTING_SOURCE_ACCEPTANCE'],
        usable_author_accepted=tiers['USABLE_AUTHOR_ACCEPTED'],
        usable_verified_visual_physics=tiers['USABLE_VERIFIED_VISUAL_PHYSICS'],
        pending_review=tiers['PENDING_REVIEW'],unusable=tiers['UNUSABLE_RETIRED']+tiers['UNUSABLE_INTEGRITY_FAILURE']+tiers['UNUSABLE_VISUAL_PHYSICS_FAILURE'],
        not_rendered=72000-len(rows))
    assert sum(admission_counts.values())==72000
    current_round_counts=dict(
        author_accepted=admission_counts['usable_author_accepted'],
        verified_usable=admission_counts['usable_verified_visual_physics'],
        pending_review=admission_counts['pending_review']+admission_counts['usable_per_existing_source_acceptance'],
        unusable=admission_counts['unusable'],missing=admission_counts['not_rendered'])
    assert sum(current_round_counts.values())==72000
    release_counts=dict(author_accepted=sum(r.get('author_accepted') is True for r in rows),
        missing=72000-len(rows))
    release_counts['without_author_acceptance']=len(rows)-release_counts['author_accepted']
    summary=dict(checked_utc=stamp,target=72000,listed_videos=len(rows),missing_videos=72000-len(rows),
        baseline_videos=69087,t14s_replacement_videos=960,completed_supplement_videos=3*len(completed),
        remaining_supplement_trajectories=len(pending),remaining_failed_trajectories=sum(bool(v['failure']) for v in pending.values()),
        supplementary_integrity_counts=dict(collections.Counter(quality[s]['media_and_state_integrity'] for s in completed if s in quality)),
        supplementary_visual_review_pending=sum(any(r['quality_admission_status']=='PENDING_REVIEW' for r in rows if r.get('sample_id')==sid and r['inventory_origin']=='supplement_render') for sid in completed),
        quality_counts=dict(collections.Counter(r['source_quality'] for r in rows)),
        admission_counts=admission_counts,
        current_round_quality_counts=current_round_counts,
        release_counts=release_counts,
        quality_counts_role='Historical evidence coverage; explicit published author acceptance is reported separately in release_counts.',
        admission_basis='Author acceptance, independent checks and historical source acceptance are recorded separately; not a full-set fresh audit or split admission.',
        unique_content_hashes=len({r['sha256'] for r in rows}),
        bound_prompt_videos=sum(bool(r.get('prompt_variants_en')) for r in rows),
        media_inventory_complete=len(rows)==72000,all_quality_accepted=False,published=False,
        scenes=table,limitations=['Source quality labels retained; media validation is not physical acceptance.',
          'Isaac retired T19 remains excluded; authorized Genesis T19 review is recorded per exact video hash.',
          'T14S occupies the Isaac T14 quota but has a distinct scene identity and boundaries.',
          'New prompt bindings and source-group split exclusions are separate admission requirements.'])
    save(snapshot/'summary.json',summary)
    save(OUT/'ACTIVE.json',dict(snapshot=str(snapshot.resolve()),manifest=str(manifest.resolve()),
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),summary=str((snapshot/'summary.json').resolve())))
    report=['# 72,000条视频发布登记与审核证据','',f'更新时间（UTC）：{stamp}。','',
            '## 当前发布登记','',
            f"作者验收：{release_counts['author_accepted']}条；未登记作者验收：{release_counts['without_author_acceptance']}条；文件缺额：{release_counts['missing']}条。",
            '作者验收与独立审核证据分别记录；下方旧标签不覆盖已发布的作者验收决定。','',
            '## 历史审核证据覆盖','',
            '|状态|数量|','|---|---:|',
            f"|作者确认人工审核通过|{current_round_counts['author_accepted']}|",
            f"|本轮已完成画面与物理复核、确认可用|{current_round_counts['verified_usable']}|",
            f"|待完成本轮复核（包含有历史验收记录者）|{current_round_counts['pending_review']}|",
            f"|旧停用或失败记录（不覆盖作者验收）|{current_round_counts['unusable']}|",
            f"|尚未渲染完成|{current_round_counts['missing']}|",'|合计|72000|','',
            '作者人工验收与自动检查、助手逐项复核分别记录；原诊断证据保留。','',
            '## 历史证据与本轮审核分列','', '|状态|数量|','|---|---:|',
            f"|有明确原验收记录，本轮未全量重审|{admission_counts['usable_per_existing_source_acceptance']}|",
            f"|作者本轮人工验收|{admission_counts['usable_author_accepted']}|",
            f"|通过本轮逐视频画面与物理复核|{admission_counts['usable_verified_visual_physics']}|",
            f"|待复核|{admission_counts['pending_review']}|",
            f"|旧停用或失败记录（不覆盖作者验收）|{admission_counts['unusable']}|",
            f"|尚未渲染完成|{admission_counts['not_rendered']}|",'|合计|72000|','',
            '原验收记录和本轮复核分开统计；完整性PASS、VLM建议和抽帧无明显缺陷均不自动授予物理质量通过。',
            '训练/评测资格按当前发布划分核对；旧质量标签仅保留审核证据覆盖信息。作者发布验收不自动授予缺失状态或临界真值。']
    (OUT/'QUALITY_STATUS.md').write_text('\n'.join(report)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['scenes','quality_counts','limitations']}))

if __name__ == '__main__': main()
