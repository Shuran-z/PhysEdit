"""Reproducible exact-ID audit of fixed100 against current local reference registrations."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

GUIDE={
 'no_exact_id_reference_scoring_registration':'未找到该精确样本ID的评分登记；需绑定原发布版本，不能借用同场景其他样本。',
 'missing_event_specific_boundary':'缺少针对目标事件、固定上下文的边界登记。',
 'missing_normalization':'缺少冻结的参数范围及归一化跨度。',
 'reference_event_and_state_not_admitted':'参考事件、状态及RGB可观察性尚未正式准入。',
 'reference_admission_pending':'参考登记尚未准入，不能直接作为正式答案。',
 'source_version_or_media_binding_unverified':'需核对原发布revision或参考视频SHA256。',
 'reference_state_hash_missing':'缺少绑定到该样本的参考状态SHA256。',
 'reference_target_label_missing':'缺少可用的二分类参考事件标签。',
 'target_event_contract_missing':'缺少明确的目标事件合同。',
 'boundary_not_verified':'只有候选/观察区间，尚未核验为可评分边界。',
 'normalization_missing':'未登记冻结的归一化跨度；候选范围如有则另列。',
 'not_certified_in_near_bin':'未被确定分入Near桶；已确定Far的样本不应补成Near。',
 'reference_rgb_observability_pending':'需审核参考RGB中目标事件是否可观察。',
 'event_definition_and_replay_release_equivalence_pending':'补算事件定义与原发布版等价性尚待核验。',
 'normalization_not_registered':'归一化范围尚未登记。',
 'core_source_revision_not_declared':'固定清单未声明原来源revision，需补来源版本绑定。',
 'no_admitted_opposite_class_in_same_near_family':'同一Near评测族缺少已准入的另一参考类别。',
 'no_frozen_cross_boundary_pair_registration':'尚无冻结的跨界配对ID/配对清单。',
 'fixed_physical_context_and_local_boundary_binding_required':'需证明两端仅改变干预参数，且绑定同一局部边界。',
 'no_verified_opposite_label_peer_in_core100':'固定100条中尚无已核实的同族异标签配对成员。'
}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(repo, core, output):
    repo=Path(repo).resolve();core=Path(core).resolve();output=Path(output);output.mkdir(parents=True,exist_ok=True)
    descriptor=json.loads((repo/'physedit/core100.json').read_text(encoding='utf-8'))
    if sha(core)!=descriptor['files']['core100.jsonl']:raise ValueError('fixed100 manifest SHA256 does not match the frozen descriptor')
    rows=[json.loads(l) for l in core.read_text(encoding='utf-8').splitlines() if l.strip()]
    if len(rows)!=100 or len({r['clip_id'] for r in rows})!=100:raise ValueError('expected 100 unique frozen members')
    source=repo/'review/scene_family_completion_20261018'
    paths=set(source.glob('*registry.json'))|set(source.glob('*reference*answers*.jsonl'))|set(source.glob('*reference*answers*.json'))
    paths.add(source/'five_scene_boundary_candidates_20261020.json')
    # Also inspect existing frozen scorer answer files; their sample namespace often differs.
    paths.update(p for p in (repo/'review').rglob('*answers*.jsonl') if 'scorer_bridge_qa_' not in str(p))
    evidence=collections.defaultdict(list);sources={};parse_errors=[]
    core_ids={r['sample_id'] for r in rows}
    for p in sorted(paths):
        if not p.exists():continue
        rel=p.relative_to(repo).as_posix();sources[rel]=sha(p)
        try:
            records=[json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()] if p.suffix=='.jsonl' else json.loads(p.read_text(encoding='utf-8'))
            if not isinstance(records,list):
                parse_errors.append({'file':rel,'reason':'non-list schema; not silently treated as an empty registry'});continue
            for r in records:
                if not isinstance(r,dict):continue
                sid=r.get('reference_sample_id') or r.get('sample_id')
                if sid in core_ids:evidence[sid].append((rel,r))
                for ep in r.get('endpoints',[]):
                    if not isinstance(ep,dict) or ep.get('sample_id') not in core_ids:continue
                    child={**ep,'family_id':r.get('family_id'),'target_event':r.get('target_event'),
                           'boundary':{'status':'candidate','bracket':r.get('bracket')},
                           'normalization_domain':r.get('normalization_domain'),'candidate_job_id':r.get('job_id'),
                           'fixed_context_sha256':r.get('source_window',{}).get('fixed_context_sha256'),
                           'reference_state_sha256':ep.get('reference_state_sha256',ep.get('state_sha256')),
                           'reference_label':ep.get('reference_label',ep.get('label'))}
                    evidence[ep['sample_id']].append((rel,child))
        except (ValueError,TypeError,KeyError) as exc:parse_errors.append({'file':rel,'reason':str(exc)})
    # Source-state diagnostics are evidence of an event audit, not an admitted scoring registration.
    t15=repo/'review/core100_boundary_pilot_20261021/reference_source_records.json'
    state_diagnostics={}
    if t15.exists():
        sources[t15.relative_to(repo).as_posix()]=sha(t15)
        state_diagnostics={r['clip_id']:{'event_frames':r.get('audit',{}).get('event_frames'),
            'audit_errors':r.get('audit',{}).get('errors'),'source':t15.relative_to(repo).as_posix()} for r in json.loads(t15.read_text(encoding='utf-8'))}
    result=[]
    for r in rows:
        sid=r['sample_id'];matches=evidence.get(sid,[]);summaries=[]
        for path,e in matches:
            target=e.get('target_event');label=e.get('events',{}).get(target,e.get('reference_label'))
            if type(label) is not int or label not in (0,1):label=None
            b=e.get('boundary') or {};d=e.get('distance') or e.get('pipeline_distance') or {}
            try:
                if b.get('status')=='verified':
                    from scorer_runtime.boundary import distance
                    d=distance(e)
            except (ValueError,TypeError,KeyError):d={'status':'invalid','bin':None}
            v=e.get('visual_review') or {}
            version_match=(bool(e.get('revision')) and e.get('revision')==r.get('source_revision')) or bool(v.get('video_sha256') and v['video_sha256']==r.get('sha256'))
            reasons=list(e.get('blocking_reasons') or [])+list((e.get('reference_admission') or {}).get('reasons') or [])
            admitted=(e.get('reference_admission') or {}).get('status')=='admitted'
            checks={'reference_admitted':admitted,'version_or_media_bound':bool(version_match),
                    'reference_state_bound':bool(e.get('reference_state_sha256')),'binary_target_label':label is not None,
                    'target_contract':bool(target),'boundary_verified':b.get('status')=='verified',
                    'normalization_registered':bool(b.get('normalization_span')),'near_bin':d.get('bin')=='near'}
            summaries.append({'registry':path,'registry_sha256':sources[path],'target_event':target,'reference_label':label,
                'family_id':e.get('family_id'),'source_group_id':e.get('source_group_id'),
                'fixed_context_sha256':e.get('fixed_context_sha256'),'theta':e.get('theta'),
                'candidate_job_id':e.get('candidate_job_id'),'candidate_normalization_domain':e.get('normalization_domain'),
                'boundary_status':b.get('status','unavailable'),'boundary':b,'distance':d,'checks':checks,
                'reference_state_sha256':e.get('reference_state_sha256'),'pair_ids':e.get('pair_ids',[]),
                'registered_blockers':sorted(set(reasons))})
        # Highest-quality evidence is selected transparently; contradictory labels/contracts remain blockers.
        summaries.sort(key=lambda x:(sum(x['checks'].values()),x['registry']),reverse=True)
        best=summaries[0] if summaries else None
        blockers=[]
        if not best:blockers+=['no_exact_id_reference_scoring_registration','missing_event_specific_boundary','missing_normalization','reference_event_and_state_not_admitted']
        else:
            blockers+=best['registered_blockers']
            for key,code in [('reference_admitted','reference_admission_pending'),('version_or_media_bound','source_version_or_media_binding_unverified'),
                             ('reference_state_bound','reference_state_hash_missing'),('binary_target_label','reference_target_label_missing'),
                             ('target_contract','target_event_contract_missing'),('boundary_verified','boundary_not_verified'),
                             ('normalization_registered','normalization_missing')]:
                if not best['checks'][key]:blockers.append(code)
            if not best['checks']['near_bin']:blockers.append('not_certified_in_near_bin')
        if not r.get('source_revision'):blockers.append('core_source_revision_not_declared')
        result.append({'clip_id':r['clip_id'],'scene_id':r['event'],'reference_sample_id':sid,
            'source_repo':r.get('source_repo'),'source_revision':r.get('source_revision'),'reference_video_sha256':r.get('sha256'),
            'core_scientific_admission':r.get('scientific_admission'),'evidence_match_count':len(summaries),
            'best_evidence':best,'all_evidence':summaries,'source_state_diagnostic':state_diagnostics.get(r['clip_id']),
            'near_point_eligible':bool(best and all(best['checks'].values()) and not best['registered_blockers']),
            'nearacc_eligible':False,'pairacc_eligible':False,'near_blockers':sorted(set(blockers)),
            'pair_blockers':[],'candidate_peer_ids':[]})
    for row in result:
        b=row['best_evidence'];peers=[];registered=[];near_peers=[]
        if b:
            for other in result:
                e=other['best_evidence']
                if not e or other['clip_id']==row['clip_id']:continue
                same=(b.get('source_group_id') and b.get('family_id') and b['source_group_id']==e.get('source_group_id') and b['family_id']==e.get('family_id') and b['target_event']==e['target_event'])
                same_candidate=bool(b.get('candidate_job_id') and b['candidate_job_id']==e.get('candidate_job_id') and b.get('fixed_context_sha256') and b['fixed_context_sha256']==e.get('fixed_context_sha256') and b['target_event']==e['target_event'])
                same=same or same_candidate
                if same and b['reference_label'] is not None and e['reference_label'] is not None and b['reference_label']!=e['reference_label']:
                    peers.append(other['clip_id'])
                    context_ok=bool(b.get('fixed_context_sha256') and b['fixed_context_sha256']==e.get('fixed_context_sha256'))
                    if context_ok and set(b['pair_ids'])&set(e['pair_ids']) and b['checks']['reference_admitted'] and e['checks']['reference_admitted'] and b['checks']['version_or_media_bound'] and e['checks']['version_or_media_bound']:registered.append(other['clip_id'])
                    if row['near_point_eligible'] and other['near_point_eligible']:near_peers.append(other['clip_id'])
        row['candidate_peer_ids']=peers;row['registered_pair_peer_ids']=registered;row['near_opposite_class_peers']=near_peers
        row['nearacc_eligible']=bool(row['near_point_eligible'] and near_peers)
        if row['near_point_eligible'] and not near_peers:row['near_blockers'].append('no_admitted_opposite_class_in_same_near_family')
        row['pairacc_eligible']=bool(registered)
        if not registered:
            row['pair_blockers']=['no_frozen_cross_boundary_pair_registration','fixed_physical_context_and_local_boundary_binding_required']
            if not peers:row['pair_blockers'].append('no_verified_opposite_label_peer_in_core100')
            if not b or not b['checks']['reference_admitted']:row['pair_blockers'].append('reference_admission_pending')
            if not b or not b['checks']['version_or_media_bound']:row['pair_blockers'].append('source_version_or_media_binding_unverified')
    scenes=[]
    for scene in sorted({r['scene_id'] for r in result}):
        items=[r for r in result if r['scene_id']==scene]
        scenes.append({'scene_id':scene,'total':len(items),'exact_reference_matches':sum(bool(r['best_evidence']) for r in items),
                       'nearacc_eligible':sum(r['nearacc_eligible'] for r in items),'pairacc_eligible':sum(r['pairacc_eligible'] for r in items)})
    report={'schema':'fixed100-metric-readiness-v2','manifest_sha256':sha(core),'manifest_revision':descriptor['revision'],
            'scope':'Exact sample-ID joins to listed local registries and state diagnostics; no fuzzy aliasing, no new physics simulations, no claim that absent registration means absent raw source data.',
            'summary':{'total':100,'exact_reference_matches':sum(bool(r['best_evidence']) for r in result),
                       'near_point_eligible':sum(r['near_point_eligible'] for r in result),'nearacc_eligible':sum(r['nearacc_eligible'] for r in result),
                       'pairacc_eligible':sum(r['pairacc_eligible'] for r in result),'state_diagnostic_matches':sum(bool(r['source_state_diagnostic']) for r in result)},
            'scenes':scenes,'rows':result,'source_hashes':sources,'unparsed_sources':parse_errors,'reason_guide':GUIDE,
            'interpretation':'Readiness of the fixed100 only. Other reference samples can be eligible outside this list. Unresolved references are not generation failures or zero scores.'}
    (output/'core100_readiness.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (output/'core100_readiness.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['clip_id','reference_sample_id','source_revision','matched_registrations','target_event','reference_label','boundary_status','distance_bin','nearacc_eligible','pairacc_eligible','near_blockers','pair_blockers','candidate_peer_ids','registered_pair_peer_ids','candidate_normalization_domain','evidence_files'])
        for r in result:
            b=r['best_evidence'] or {};w.writerow([r['clip_id'],r['reference_sample_id'],r['source_revision'],r['evidence_match_count'],b.get('target_event'),b.get('reference_label'),b.get('boundary_status'),(b.get('distance') or {}).get('bin'),r['nearacc_eligible'],r['pairacc_eligible'],';'.join(r['near_blockers']),';'.join(r['pair_blockers']),';'.join(r['candidate_peer_ids']),';'.join(r['registered_pair_peer_ids']),json.dumps(b.get('candidate_normalization_domain')),';'.join(sorted({e['registry'] for e in r['all_evidence']}))])
    lines=['# 固定100条：NearAcc与PairAcc逐条核查','',f"清单SHA256：`{sha(core)}`。",'',json.dumps(report['summary'],ensure_ascii=False),'',
           '只匹配明确样本ID，记录已核查来源哈希。未找到评分登记不等于原始状态不存在；不以文件名star、同场景或其他版本的边界替代。',
           'PairAcc需要同一固定物理上下文、相同目标事件及局部边界的合法异侧配对，不能用prompt或seed构造。','',
           '## 缺项说明','']+[f'- `{code}`：{text}' for code,text in GUIDE.items()]+['','## 逐条结果','',
           '|样本|匹配登记数|边界状态 / 距离桶|NearAcc|PairAcc|阻塞原因|','|---|---:|---|---|---|---|']
    for r in result:
        b=r['best_evidence'] or {};lines.append('|'+ '|'.join([r['clip_id'],str(r['evidence_match_count']),str(b.get('boundary_status','无登记'))+' / '+str((b.get('distance') or {}).get('bin')),'可用' if r['nearacc_eligible'] else 'N/A','可用' if r['pairacc_eligible'] else 'N/A','; '.join(sorted(set(r['near_blockers']+r['pair_blockers'])))])+'|')
    (output/'CORE100_READINESS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',default='.');p.add_argument('--core',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(audit(a.repo,a.core,a.output)['summary']))
