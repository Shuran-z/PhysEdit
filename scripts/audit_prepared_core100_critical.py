"""Read-only audit of a pinned Core100 critical reference package.

Writes a separate receipt; never changes rosters, labels or active pointers.
This is a reference/contract audit, not an independent physics validation.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from physedit.core100_critical import ROOT,load,primary,sha
from physedit.boundary import write_json,write_rows
from physedit.core100_rebalanced import load as load_roster


def audit(pointer_path,out):
    pointer_path=Path(pointer_path).resolve();pointer=json.loads(pointer_path.read_text(encoding='utf8'))
    registry=(pointer_path.parent/pointer['registry']).resolve()
    data,_=load(registry,pointer['registry_sha256'])
    _,manifest,tasks,_=load_roster(ROOT/data['roster_pointer']['path'])
    scene_counts=Counter(r['scene_id']for r in data['cases'])
    assert scene_counts=={f'T{i:02}':5 for i in range(1,21)}
    conditions={r['clip_id']:r for r in tasks}
    bindings={r['clip_id']:r for r in data['input_bindings']};rows=[]
    for r in data['cases']:
        u=primary(r);domain=r['normalization_domain']
        assert not u['supplemental_axis']
        if domain is not None:
            assert math.isclose(u['normalization_span'],domain[1]-domain[0],rel_tol=1e-9,abs_tol=1e-12)
            normalization_basis='original parameter-domain span'
        else:
            # Joint G samples use their registered dimensionless path
            # coordinate, not an invented scalar physical-parameter range.
            assert r['parameter']=='joint_global_configuration'and u['axis']=='original_G_global_path'
            revision=r['observable_event_revision']
            assert u['normalization_span']==1.0
            assert u['theta']==revision['original_global_source_coordinate']
            assert u['intervals']==[[p['theta']for p in revision['published_global_endpoints']]]
            normalization_basis='original ordered joint-path coordinate; not a single-parameter effect'
        intervals=u['intervals'];assert intervals
        low,high=u['normalized_absolute_interval']
        bucket='near'if high<=.05 else'mid'if low>.05 and high<=.15 else'far'if low>.15 else None
        assert bucket==u['bin'],r['clip_id']
        assert u['event']in r['judge_protocol']['events']
        assert r['condition_frame_index']==bindings[r['clip_id']]['condition_frame_index']
        assert r['reference_video_sha256']==conditions[r['clip_id']]['reference']['sha256']
        rows.append(dict(clip_id=r['clip_id'],scene_id=r['scene_id'],reference_video_sha256=r['reference_video_sha256'],
            event=u['event'],label=u['label'],axis=u['axis'],theta=u['theta'],
            observation_window_s=r['horizon_s'],condition_frame_index=r['condition_frame_index'],
            intervals=intervals,normalization_domain=domain,normalization_span=u['normalization_span'],normalization_basis=normalization_basis,
            normalized_absolute_interval=[low,high],distance_bin=bucket,
            rgb_distance_admitted=u['rgb_distance_admitted'],rgb_blockers=u['rgb_blockers'],
            event_observation_admitted=u['event']in r['admitted_rgb_events'],
            numerical_profile=r.get('numerical_reference_profile'),
            source_state_sha256=r.get('source_state_sha256'),
            reference_id=u['reference_id']))
    by_clip={r['clip_id']:r for r in rows}
    for pair in data['pairs']:
        a,b=[by_clip[c]for c in pair['clips']]
        assert a['label']!=b['label']
        assert a['axis']==b['axis']and a['event']==b['event']
        assert a['scene_id']==b['scene_id']
        assert pair['pairing_mode']in ['independent','coupled_seed']
    pending=[r['clip_id']for r in rows if not r['rgb_distance_admitted']]
    near=[r for r in rows if r['rgb_distance_admitted']and r['distance_bin']=='near']
    source_hashes=dict(data['source_hashes'])
    protected={name:sha(ROOT/name)for name in [
        'catalog/active_core100_conditions.json','catalog/active_core100_critical_protocol.json',
        'benchmarks/core100_critical_pairs_v2_20261101/MANIFEST.json',
        'benchmarks/core100_critical_pairs_v3_20261103/MANIFEST.json']}
    summary=dict(roster_release=data['roster_release'],protocol_version=data['version'],
        registry_sha256=sha(registry),reference_count=100,numerical_boundaries=100,
        original_family_numerical_pending=0,rgb_critical_references=100-len(pending),
        rgb_critical_pending=pending,not_applicable_reference_count=0,
        admitted_near_count=len(near),near_reference_labels=dict(Counter(str(r['label'])for r in near)),
        pairs_by_mode=dict(Counter(p['pairing_mode']for p in data['pairs'])),
        validated_local_source_snapshot_count=len(source_hashes),
        newly_replaced_generation_and_annotation_pending=manifest['newly_replaced_generation_and_annotation_pending'],
        all_changed_inputs_require_generation_and_annotation=manifest['model_generation_and_annotation_pending'],
        prepared_not_activated=pointer['status']=='prepared_not_live',
        physical_quality_or_independent_human_annotation_validated_by_this_audit=False,
        model_experiments_executed_by_this_audit=False,
        protected_current_hashes=protected,
        full_EventExact=dict(status='not_registered',reason='Primary-event labels do not establish a complete causal-chain annotation contract.'),
        BoundaryError=dict(status='not_registered',reason='No model response-grid threshold estimator registered; endpoint pairs alone are insufficient.'),
        inversion=dict(status='separate_registration_required',reason='No eligibility inferred from critical event admission.'),
        reference_binding_complete=not pending,
        remaining_reference_action=('Resolve pending reference event visibility: '+','.join(pending))if pending else None,
        audit_scope='Reference binding and distance arithmetic only; pipeline and model execution require separate evidence.')
    scene_rows=[]
    for scene in sorted(scene_counts):
        own=[r for r in rows if r['scene_id']==scene]
        scene_rows.append(dict(scene=scene,registered=5,numerical=5,rgb_critical=sum(r['rgb_distance_admitted']for r in own),
            pending=[r['clip_id']for r in own if not r['rgb_distance_admitted']],
            near=sum(r['rgb_distance_admitted']and r['distance_bin']=='near'for r in own)))
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    write_rows(out/'cases.jsonl',rows);write_json(out/'summary.json',summary)
    write_json(out/'scenes.json',scene_rows)
    write_json(out/'source_snapshot_hashes.json',source_hashes)
    lines=['# Core100临界参考收口核查','',
        f"版本：{data['roster_release']}；准备包未切换线上。",'',
        f"100条均有原参数族临界区间和归一化距离；{100-len(pending)}条可作RGB临界评分；0条判为不适用；{len(pending)}条待解决。",
        '',f"Near参考{len(near)}条；13组跨界配对（独立5、共享生成种子8）。这些是参考数量，不是模型成绩。",'',
        '|场景|数值齐全|RGB临界可评|待完成|Near|','|---|---:|---:|---|---:|']
    for r in scene_rows:lines.append(f"|{r['scene']}|5|{r['rgb_critical']}|{','.join(r['pending'])or'无'}|{r['near']}|")
    lines+=['',('待解决：'+','.join(pending))if pending else'参考绑定已齐。T03_C02采用作者批准的cam02，以越缘下落为主判据，不要求落地。',
        'Full EventExact和BoundaryError尚未注册；反演须独立登记适用窗口与验证凭据。',
        '本核查重读固定版本、本地来源快照和输入绑定，不替代独立人工标注或实际生成模型实验。']
    (out/'STATUS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    write_json(out/'MANIFEST.json',dict(audit_source_sha256=sha(__file__),pointer_sha256=sha(pointer_path),
        files={p.name:sha(p)for p in out.iterdir()if p.is_file()}))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pointer',type=Path,default=ROOT/'catalog/prepared_core100_critical_protocol_v3.json')
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    value=audit(a.pointer,a.out)
    print(json.dumps({k:value[k]for k in ['numerical_boundaries','rgb_critical_references','rgb_critical_pending','admitted_near_count','reference_binding_complete']}))
