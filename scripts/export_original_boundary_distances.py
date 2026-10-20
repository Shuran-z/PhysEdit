"""Export original critical references and distances, independently of QA gates.

No new solver calls, video judgments, binning or inversion eligibility checks.
An original calibrated centre remains named as such; intervals are never silently
converted to exact thresholds. Missing original values stay missing.
"""
import collections
import csv
import hashlib
import json
import math
import re
from pathlib import Path

ROOT=Path('review/scene_family_completion_20261018')
ORIGINAL=Path('review/original_search_tasks_20261018')


def distances(theta,point=None,bracket=None):
    if not isinstance(theta,(int,float)) or not math.isfinite(theta):raise ValueError('invalid parameter')
    if point is not None:
        if not isinstance(point,(int,float)) or not math.isfinite(point):raise ValueError('invalid original centre')
        return dict(signed_distance=theta-point,absolute_distance=abs(theta-point),distance_lower=None,distance_upper=None)
    if bracket is not None:
        a,b=sorted(bracket)
        if not all(math.isfinite(x) for x in [a,b]):raise ValueError('invalid original bracket')
        return dict(signed_distance=None,absolute_distance=None,distance_lower=max(a-theta,theta-b,0),distance_upper=max(abs(theta-a),abs(theta-b)))
    return dict(signed_distance=None,absolute_distance=None,distance_lower=None,distance_upper=None)


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def declared_star_rows():
    """Recover rendering reference values without upgrading them to solved values."""
    result=[]
    def group_rows(records,source,key,star):
        groups=collections.defaultdict(list)
        for r in records:
            if r.get('family_id') and isinstance(r.get('theta'),(int,float)):groups[key(r)].append(r)
        for context,items in groups.items():
            centres={r['theta'] for r in items if star(r)}
            if len(centres)!=1:continue
            centre=next(iter(centres))
            for r in items:
                result.append(dict(scene_id=r.get('scene_id',r['sample_id'][:3]),engine='genesis',sample_id=r['sample_id'],family_id=r['family_id'],theta=r['theta'],
                    original_rendering_star=centre,reference_kind='recorded_rendering_star_not_automatically_a_solved_boundary',
                    **distances(r['theta'],point=centre),source_file=str(source.resolve()),context=list(context),
                    effective_parameter_value=r.get('effective_parameter_value',r['theta']),repair_record=r.get('repair_record'),
                    parameter_note='theta is the recorded design coordinate; effective parameter is separately retained when a repair changed it'))
    for scene in ['T07','T08']:
        source=ROOT/(scene.lower()+'_measured_published_events.json')
        group_rows(load(source),source,lambda r:(r.get('repo_id'),r.get('revision'),r['background'],r['gravity'],r['family_id'],re.search(r'__rep(\d+)',r['sample_id']).group(1) if '__rep' in r['sample_id'] else None),lambda r:'_theta_star__' in r['sample_id'])
    source=ROOT/'t04_t05_profile_bindings.json'
    group_rows([r for r in load(source) if r.get('design')=='counterfactual_boundary'],source,
        lambda r:(r['source_group_id'],r['family_id']),lambda r:'_star__' in r['sample_id'])
    source=ORIGINAL/'t15_original_family_registry.json'
    for group in load(source)['groups']:
        centres={r['declared_parameter_value'] for r in group['samples'] if r['original_branch']=='theta_star'}
        if len(centres)!=1:continue
        point=next(iter(centres))
        for r in group['samples']:
            result.append(dict(scene_id='T15',engine='genesis',sample_id=r['sample_id'],family_id=group['original_family'],theta=r['declared_parameter_value'],
                original_rendering_star=point,reference_kind='recorded_rendering_star_not_automatically_a_solved_boundary',**distances(r['declared_parameter_value'],point=point),
                source_file=str(source.resolve()),context=[group['version'],group['background_id'],group['gravity_id'],group['original_family']],calibrated_source_id=r.get('calibrated_source_id')))
    return result


def main():
    inventory=[json.loads(line) for line in Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()]
    published={(r['engine'],r['sample_id']):r for r in inventory}
    rows=[]
    def add(record,path,kind,point=None,bracket=None,version_note=None):
        sid=record['sample_id'];engine=record.get('engine','genesis');ref=published.get((engine,sid))
        theta=record.get('theta');scene=record.get('scene_id',sid[:3])
        if ref is None or theta is None:return
        rows.append(dict(scene_id=scene,engine=engine,sample_id=sid,repo_id=ref.get('repo_id'),revision=ref.get('revision'),release=ref.get('release'),
            videos=ref.get('videos',{}),family_id=record.get('family_id',record.get('family')),parameter_name=record.get('parameter_name',record.get('changed_variable')),
            parameter_unit=record.get('parameter_unit',record.get('unit')),theta=theta,original_reference_kind=kind,original_critical_value=point,original_boundary_interval=bracket,
            **distances(theta,point,bracket),source_file=str(path.resolve()),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            original_source_path=record.get('contract_path',record.get('boundary',{}).get('source')),version_note=version_note,
            publication_status='retired_T19_render' if scene=='T19' else 'historical_frozen_release' if scene in ['T03','T11','T12','T13'] else 'published_reference',
            extra_validation_separate=True))
    for scene in ['T01','T02']:
        path=ORIGINAL/(scene.lower()+'_original_family_bindings.json')
        for r in load(path):
            if r.get('original_calibrated_star') is not None:
                add(r,path,'original_calibrated_centre',point=r['original_calibrated_star'],version_note='Original recorded calibrated value; not a new claim of analytic exactness.')
    path=ORIGINAL/'t14_original_family_bindings.json'
    source=next(r for r in load(ORIGINAL/'p26_records.json') if r['path'].endswith('manifests/t14_independent_event_contract_v2.json'))
    calibration=json.loads(source['text'])['calibration_results_r006']
    for r in load(path):
        if r.get('original_search_interval') is None:continue
        if r['family']=='B':
            add(r,path,'original_calibrated_centre',point=calibration['B_yaw_boundaries'][r['gravity_id']]['theta_star_deg'],version_note='Selected old T14; original calibration solver .005, released solver .001. Original value retained; supplemental solver result separate.')
        else:add(r,path,'original_search_interval',bracket=r['original_search_interval'],version_note='Selected old T14; original calibration profile and released solver differ. Do not overwrite original record with supplemental results.')
    for filename in ['isaac_original_distance_registry.json','isaac_repair_distance_registry.json']:
        path=ROOT/filename
        for r in load(path):
            intervals=r.get('boundary',{}).get('intervals',[])
            for interval in intervals:
                add(r,path,'original_search_interval',bracket=interval['bracket'],version_note='Original-source linkage retained; repair/version review is a separate column, not a distance gate.')
    # T20 search-source inputs are intentionally not promoted to published IDs.
    out=ROOT/'original_value_distance_ledger';out.mkdir(exist_ok=True)
    (out/'sample_distances.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    stars=declared_star_rows()
    for r in stars:
        ref=published.get((r['engine'],r['sample_id']))
        if ref:r.update(repo_id=ref.get('repo_id'),revision=ref.get('revision'),release=ref.get('release'),videos=ref['videos'])
    (out/'recorded_rendering_star_distances.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in stars),encoding='utf-8')
    star_fields=['scene_id','sample_id','repo_id','revision','release','family_id','theta','effective_parameter_value','original_rendering_star','signed_distance','absolute_distance','reference_kind','source_file']
    with (out/'recorded_rendering_star_distances.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=star_fields,extrasaction='ignore');writer.writeheader();writer.writerows(stars)
    fields=['scene_id','engine','sample_id','repo_id','revision','release','family_id','parameter_name','parameter_unit','theta','original_reference_kind','original_critical_value','original_boundary_interval','signed_distance','absolute_distance','distance_lower','distance_upper','publication_status','source_file','version_note']
    with (out/'sample_distances.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    summary=[]
    for scene in [f'T{i:02}' for i in range(1,21)]:
        rr=[r for r in rows if r['scene_id']==scene]
        summary.append(dict(scene_id=scene,published_samples_with_original_reference=len({(r['engine'],r['sample_id']) for r in rr}),
            original_point_records=sum(r['original_critical_value'] is not None for r in rr),original_interval_records=sum(r['original_boundary_interval'] is not None for r in rr),
            reference_kinds=dict(collections.Counter(r['original_reference_kind'] for r in rr)),
            separate_recorded_rendering_star_samples=sum(r['scene_id']==scene for r in stars),
            recovery_status='partial_original_values_exported' if rr else 'original_value_not_yet_exported',
            action='continue original metadata/log lookup; recompute only genuinely missing references',
            extra_validation_blocks_distance=False))
    (out/'all20_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 原临界参考与视频参数距离','', '本表只记录原值恢复和距离计算，不含画面审核、反演适用性、重复验证和NearAcc准入。原值为区间时报告距离上下界；不自行取中点当精确临界点。','', '|场景|已对应样本|原中心值记录|原区间记录|另存渲染star样本|状态|','|---|---:|---:|---:|---:|---|']
    for r in summary:lines.append(f"|{r['scene_id']}|{r['published_samples_with_original_reference']}|{r['original_point_records']}|{r['original_interval_records']}|{r['separate_recorded_rendering_star_samples']}|{'部分原值已导出' if r['published_samples_with_original_reference'] else '原值尚未导出，继续查找'}|")
    lines+=['','T19旧渲染距离仅作历史来源保留，当前仍停用。新T11/T12/T13和当前T03不能被历史库存身份覆盖。T14采用用户指定的旧笔穿通道版。','', '未导出不表示从未计算；不据此直接启动补算。']
    (out/'ALL20_ORIGINAL_VALUES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(records=len(rows),unique_samples=len({(r['engine'],r['sample_id']) for r in rows}),separate_rendering_star_records=len(stars),rendering_star_scenes=dict(collections.Counter(r['scene_id'] for r in stars)),scenes_with_original_values=[r['scene_id'] for r in summary if r['published_samples_with_original_reference']],output=str(out.resolve())),ensure_ascii=False))


if __name__=='__main__':main()
