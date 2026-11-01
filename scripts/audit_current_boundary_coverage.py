"""Audit numerical-reference coverage against the pinned 72,000-video release.

No solver calls, quality gates, new event thresholds, or formal-score promotion.
Name matches are candidates only. All counts have a fixed current-media denominator.
"""
import collections,datetime,gzip,hashlib,io,json
from pathlib import Path

ROOT=Path('review/scene_family_completion_20261018')
LABELS={
 'distance_linked':'已有数值参考且媒体/输入对应',
 'numeric_identity_pending':'已有数值记录，身份关联待完成',
 'search_complete_no_flip':'原范围搜索完成，未观察到翻转',
 'necessary_search_pending':'新目标事件补算尚未完成',
 'render_center_only':'仅找到渲染中心，来源待追溯',
 'source_lookup_pending':'尚无对应数值来源，需继续查找',
}

def config_hashes(row):
    values={row.get(k) for k in ['source_config_sha256','reference_config_sha256','config_sha256','prompt_source_config_sha256']}
    ev=row.get('prompt_binding_evidence') or {};ce=ev.get('config_evidence') or {}
    if ce.get('verified'):values.add(ce.get('expected_sha256'))
    return {v for v in values if isinstance(v,str) and len(v)==64}

def identity(video,record,inventory):
    """A matching name alone never certifies physical/source identity."""
    camera=video['camera'];sha=video['sha256']
    recorded_videos=record.get('videos') or {}
    direct=recorded_videos.get(camera,{}) if isinstance(recorded_videos,dict) else {}
    if direct.get('sha256')==sha:return 'direct_record_video_sha256'
    for v in record.get('current_release_videos',[]):
        if v['video_id']==video['video_id'] and v['video_sha256']==sha:return 'published_current_media_binding'
    update=video.get('media_version_update') or {}
    if (direct.get('sha256') and update.get('previous_sha256')==direct['sha256'] and update.get('current_sha256')==sha and update.get('input_config_bytes_identical') is True and update.get('new_media_hf_sha_verified') is True):
        return 'reviewed_input_identical_media_replacement'
    if config_hashes(video)&config_hashes(record):return 'exact_source_config_sha256'
    for ref in inventory:
        same_revision=bool(record.get('revision')) and ref.get('revision')==record['revision']
        same_config=bool(config_hashes(ref)&config_hashes(record))
        if (same_revision or same_config) and (ref.get('videos') or {}).get(camera,{}).get('sha256')==sha:
            return 'same_source_revision_and_inventory_video_sha256' if same_revision else 'same_source_config_and_inventory_video_sha256'
    return None

def classify(evidence):
    for key in ['distance_linked','search_complete_no_flip','numeric_identity_pending','necessary_search_pending','render_center_only']:
        if evidence.get(key):return key
    return 'source_lookup_pending'

def main():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=ROOT/'current_release_coverage'/stamp;out.mkdir(parents=True)
    inputs={}
    def read_bytes(path):
        raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();inputs[str(path.resolve())]=digest
        if path.is_relative_to(ROOT) and path.name!='combined_distance_inputs.jsonl':
            frozen=out/'frozen_inputs'/(digest+'.gz');frozen.parent.mkdir(exist_ok=True)
            if not frozen.exists():frozen.write_bytes(gzip.compress(raw,compresslevel=3,mtime=0))
        return raw
    def read(path):return json.loads(read_bytes(path))
    active=read(Path('../release_72000_active/ACTIVE_CATALOG.json'))
    live=read(ROOT/'live_catalog_identity_20261030.json')
    payload=read_bytes(Path(active['manifest']))
    assert hashlib.sha256(payload).hexdigest()==active['manifest_sha256']==live['manifest_sha256']
    current=list(map(json.loads,gzip.decompress(payload).decode('utf8').splitlines()))
    assert len(current)==72000 and len({r['video_id'] for r in current})==72000
    trajectories=collections.defaultdict(list)
    for v in current:trajectories[(v['engine'],v['native_sample_id'])].append(v)
    assert len(trajectories)==24000 and all(len(vs)==3 for vs in trajectories.values())
    inventory=collections.defaultdict(list)
    for line in io.StringIO(read_bytes(Path('../dataset_splits_v2/all_selected_trajectories.jsonl')).decode('utf8')):
        r=json.loads(line);inventory[(r['engine'],r['sample_id'])].append(r)
    ledger=read_bytes(ROOT/'original_value_distance_ledger/combined_distance_inputs.jsonl')
    (out/'ledger_snapshot.jsonl.gz').write_bytes(gzip.compress(ledger,compresslevel=3,mtime=0))
    numeric=collections.defaultdict(list);numeric_by_config=collections.defaultdict(list);centers=collections.defaultdict(list);unselected=set();legacykeys=set()
    for line in io.StringIO(ledger.decode('utf8')):
        r=json.loads(line);key=(r.get('engine'),r['sample_id'])
        if r['reference_category']=='diagnostic_proxy':continue
        if r['reference_category']=='rendering_star':centers[key].append(r);continue
        if r.get('original_critical_value') is None and not r.get('original_boundary_interval'):continue
        legacykeys.add((r['engine'],r.get('revision'),r['sample_id']))
        for digest in config_hashes(r):numeric_by_config[(r['engine'],r['scene_id'],digest)].append(r)
        if key not in trajectories:unselected.add((r['engine'],r.get('revision'),r['sample_id']));continue
        numeric[key].append(r)
    published_hashes_path=ROOT/'coverage_original_video_hashes_20261030.json'
    if published_hashes_path.exists():
        proofs=read(published_hashes_path)
        by_source={(r['revision'],r['path']):r for r in proofs['records'] if r.get('sha256')}
        for records in numeric.values():
            for r in records:
                if not isinstance(r.get('videos'),list):
                    config_path=r.get('published_config_path','')
                    prefix=config_path.split('/configs/')[0] if '/configs/' in config_path else None
                    if not prefix:continue
                    paths=[path for rev,path in by_source if rev==r.get('revision') and path.startswith(prefix+'/videos/'+r['sample_id']+'__cam')]
                else:paths=r['videos']
                matched={}
                for path in paths:
                    proof=by_source.get((r['revision'],path))
                    if proof:
                        for cam in ['cam01','cam02','cam03']:
                            if '__'+cam in path:matched[cam]={'sha256':proof['sha256']}
                if matched:r['videos']=matched
    noflip=collections.defaultdict(list);required=collections.defaultdict(list)
    path=ROOT/'t18_event_reference_candidates_20261020.jsonl'
    for line in io.StringIO(read_bytes(path).decode('utf8')):
        r=json.loads(line);key=(r['engine'],r['sample_id'])
        if r.get('boundary_status')=='no_observed_flip_on_original_grid':noflip[key].append(r)
        elif r.get('search_status')!='conditional_event_search_completed':required[key].append(r)
    answers=read(ROOT/'t07_B_E4_reference_answers_20261022.json')
    byanswer={r['sample_id']:r for r in answers}
    t07=read(ROOT/'t07_B_full_grid_summary_20261027.json')
    for result in t07['results']:
        r=byanswer.get(result['sample_id'])
        if r is None:continue
        if result['status']=='conditional_grid_completed' and not result.get('intervals'):noflip[('genesis',r['sample_id'])].append(r)
        elif result['status']=='failed':required[('genesis',r['sample_id'])].append(r)
    for r in read(ROOT/'t14_all_context_reference_candidates_20261020.json'):
        if 'boundary_intervals' in r and not r['boundary_intervals']:noflip[(r['engine'],r['sample_id'])].append(r)
    # Frozen plans classify required new-event searches; unfinished optional scans
    # never make an otherwise linked original value "missing".
    counts=collections.Counter();scene_counts=collections.defaultdict(collections.Counter)
    traj_counts=collections.Counter();links=[];evidence_modes=collections.Counter();normalizable=set();original=set();supplemental=set();no_flip_candidates=0
    all_rows=[]
    for key,videos in trajectories.items():
        statuses=[]
        for video in videos:
            statuses_evidence={};bound=[];pending=[]
            candidates={r['distance_record_id']:r for r in numeric.get(key,[])}
            for digest in config_hashes(video):
                for r in numeric_by_config.get((video['engine'],video['quota_scene'],digest),[]):candidates[r['distance_record_id']]=r
            for r in candidates.values():
                mode=identity(video,r,inventory.get(key,[]))
                if mode:
                    bound.append((r,mode));evidence_modes[mode]+=1
                else:pending.append(r)
            if bound:statuses_evidence['distance_linked']=True
            if pending:statuses_evidence['numeric_identity_pending']=True
            complete_no_flip=[r for r in noflip.get(key,[]) if identity(video,r,inventory.get(key,[]))]
            needed=[r for r in required.get(key,[]) if identity(video,r,inventory.get(key,[]))]
            if complete_no_flip:statuses_evidence['search_complete_no_flip']=True
            if needed:statuses_evidence['necessary_search_pending']=True
            if centers.get(key):statuses_evidence['render_center_only']=True
            status=classify(statuses_evidence);statuses.append(status);counts[status]+=1
            scene_counts[video['quota_scene']][status]+=1
            missing_reason=''
            if status=='numeric_identity_pending':missing_reason='same native source name has numerical records; video/config identity not yet proven'
            elif status=='render_center_only':missing_reason='recorded theta_star alone does not certify a solved event boundary'
            elif status=='source_lookup_pending':missing_reason='no usable match in audited sources; not evidence that no original search exists'
            record={'video_id':video['video_id'],'scene':video['quota_scene'],'native_scene':video['native_scene_id'],'engine':video['engine'],'native_sample_id':key[1],'camera':video['camera'],'video_sha256':video['sha256'],'category':status,'numeric_records':len(candidates),'linked_numeric_records':len(bound),'independent_required_target_pending':bool(needed),'unresolved_reason':missing_reason,'formal_NearAcc_granted':False}
            all_rows.append(record)
            if status=='numeric_identity_pending':
                record['identity_evidence']=[dict(ledger_record_id=r['distance_record_id'],source_revision=r.get('revision'),source_camera_sha256=(r.get('videos') or {}).get(video['camera'],{}).get('sha256') if isinstance(r.get('videos'),dict) else None,source_config_sha256=sorted(config_hashes(r)),current_config_sha256=sorted(config_hashes(video))) for r in pending]
            for r,mode in bound:
                original.add(video['video_id']) if r['reference_category']=='recovered_original' else supplemental.add(video['video_id'])
                normalized=isinstance(r.get('normalization_span'),(int,float)) and r['normalization_span']>0
                normalized=normalized or isinstance(r.get('normalized_distance_upper'),(int,float))
                if normalized:normalizable.add(video['video_id'])
                links.append(dict(video_id=video['video_id'],video_sha256=video['sha256'],engine=video['engine'],scene=video['quota_scene'],sample_id=key[1],source_sample_id=r['sample_id'],camera=video['camera'],ledger_record_id=r.get('distance_record_id'),reference_category=r['reference_category'],family_id=r.get('family_id'),parameter_name=r.get('parameter_name'),parameter_unit=r.get('parameter_unit'),target_event=r.get('target_event'),theta=r['theta'],original_critical_value=r.get('original_critical_value'),original_boundary_interval=r.get('original_boundary_interval'),absolute_distance=r.get('absolute_distance'),distance_lower=r.get('distance_lower'),distance_upper=r.get('distance_upper'),normalization_span=r.get('normalization_span'),distance_bin=r.get('distance_bin'),normalized_distance_lower=r.get('normalized_distance_lower'),normalized_distance_upper=r.get('normalized_distance_upper'),match_method=mode,source_ledger=r.get('ledger_source'),formal_NearAcc_granted=False))
        if all(s=='distance_linked' for s in statuses):traj_counts['all_three_views_distance_linked']+=1
        if 'distance_linked' in statuses:traj_counts['at_least_one_view_distance_linked']+=1
        traj_counts['total']+=1
    def write(name,rows):
        with gzip.open(out/name,'wt',encoding='utf8') as f:
            for row in rows:f.write(json.dumps(row,ensure_ascii=True)+'\n')
    write('video_coverage.jsonl.gz',all_rows);write('current_release_distance_links.jsonl.gz',links)
    summary={'created_utc':stamp,'publication_revision':live['revision'],'manifest_sha256':active['manifest_sha256'],'videos':len(current),'trajectories':len(trajectories),'categories':{k:counts[k] for k in LABELS},'distance_linkage_coverage_percent':100*counts['distance_linked']/len(current),'trajectory_coverage':dict(traj_counts),'linked_with_original_records':len(original),'linked_with_supplemental_records':len(supplemental),'linked_with_normalization_record':len(normalizable),'legacy_versioned_numerical_trajectories':len(legacykeys),'legacy_numerical_trajectories_not_named_in_current_release':len(unselected),'match_record_counts':dict(evidence_modes),'by_scene':[dict(scene=f'T{i:02}',total=3600,**{k:scene_counts[f'T{i:02}'][k] for k in LABELS}) for i in range(1,21)],'inputs_sha256':inputs,'interpretation':'Coverage means at least one numerical event/parameter reference associated with current media. It is not complete coverage of all event families, observed outcomes, or formal NearAcc. Unmatched is lookup work, not a confirmed simulation requirement.'}
    summary['linked_normalization_pending']=counts['distance_linked']-len(normalizable)
    summary['whole_protocol_completion_percent']=None
    assert sum(summary['categories'].values())==72000
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    lines=['# 当前发布清单的临界数值参考覆盖核查','',f"固定发布：`phy2/phydataset@{live['revision']}`；72,000视频、24,000轨迹。",'',
           '**这里计算的是当前视频至少一个参数/事件的数值参考关联覆盖率，不是所有临界族完成率或NearAcc评分完成率。**','',
           '|类别|视频数|占72,000比例|','|---|---:|---:|']
    for k,label in LABELS.items():lines.append(f'|{label}|{counts[k]}|{100*counts[k]/72000:.2f}%|')
    lines+=['','|场景|已对应数值|数值待身份关联|搜索无翻转|必要补算未结束|仅渲染中心|来源待查|','|---|---:|---:|---:|---:|---:|---:|']
    for r in summary['by_scene']:lines.append('|'+r['scene']+'|'+'|'.join(str(r[k]) for k in LABELS)+'|')
    lines+=['','## 口径与下一步','',
            f"- 已对应视频中{len(normalizable):,}条另有归一化记录，{summary['linked_normalization_pending']:,}条仍需补归一化来源；这属于记录接入，不能直接变成补算任务。",
            '- 三机位按发布清单分别核对，不把三机位当作三个独立物理实验；另报24,000轨迹的覆盖。',
            '- 只有视频SHA、源配置SHA或同来源版本的库存视频SHA对应才计入“已对应”；同名不算完成。',
            '- 原值与补算分别保留；源区间存在时不因额外复现失败删除。',
            '- 仅渲染中心需先找生成脚本或搜索来源；来源待查不直接改成必须补算。',
            '- “搜索无翻转”只说明原网格未观察到该事件边界，不虚构距离；一个视频仍可能有其他未完成的事件目标。',
            '- 所有数据保留。没有套用物理反演准入、画面审核或near分桶门槛来删掉样本。',
            '- 导出的current_release_distance_links.jsonl.gz是数值关联表，未改变正式评测答案或授予NearAcc资格。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    pointer={'snapshot':str(out.resolve()),'summary':str((out/'SUMMARY.json').resolve()),'report':str((out/'REPORT.md').resolve()),'publication_revision':live['revision'],'distance_links':str((out/'current_release_distance_links.jsonl.gz').resolve()),'video_coverage':str((out/'video_coverage.jsonl.gz').resolve()),'numerical_bindings_only':True}
    (ROOT/'CURRENT_RELEASE_COVERAGE.json').write_text(json.dumps(pointer,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['inputs_sha256','by_scene','match_record_counts']},ensure_ascii=True))
    print(str((out/'REPORT.md').resolve()))

if __name__=='__main__':main()
