"""Export the 15 mandatory new-input tasks without importing legacy scores."""
import argparse
import hashlib
import json
from pathlib import Path

from .core100_critical import ROOT,load,primary,sha
from .core100_rebalanced import load as load_roster
from .boundary import write_json,write_rows
from .judge_contract import observation_definitions

POINTER=ROOT/'catalog/prepared_core100_critical_protocol_v4.json'


def export(out,pointer=POINTER):
    pointer=Path(pointer).resolve();p=json.loads(pointer.read_text(encoding='utf8'))
    data,registry=load((pointer.parent/p['registry']).resolve(),p['registry_sha256'])
    root,manifest,tasks,_=load_roster(ROOT/data['roster_pointer']['path'])
    required=manifest['model_generation_and_annotation_pending']
    assert len(required)==15 and len(set(required))==15
    cases={r['clip_id']:r for r in data['cases']};bindings={r['clip_id']:r for r in data['input_bindings']}
    original_eight=json.loads((ROOT/'benchmarks/core100_critical_pairs_v2_20261101/MANIFEST.json').read_text())['model_generation_and_annotation_pending']
    extra_six=json.loads((ROOT/'benchmarks/core100_critical_pairs_v3_20261103/MANIFEST.json').read_text())['newly_replaced_generation_and_annotation_pending']
    generation=[];reviews=[];rows=[]
    for cid in sorted(required):
        c=cases[cid];b=bindings[cid];u=primary(c)
        assert u['rgb_distance_admitted']
        reason='camera_cam03_to_cam02'if cid=='T03_C02'else'eight_reference_replacements'if cid in original_eight else'six_reference_replacements'
        assert cid=='T03_C02'or cid in original_eight or cid in extra_six
        task_id=data['roster_release']+'__'+cid+'__'+c['reference_video_sha256'][:12]
        shared=dict(sample_id=task_id,task_id=task_id,clip_id=cid,roster_release=data['roster_release'],registry_sha256=sha(registry),
            reference_video_sha256=c['reference_video_sha256'],condition_sha256=b['condition_sha256'],
            prompt_variant_sha256=b['prompt_variant_sha256'],observation_window_s=c['horizon_s'])
        generation.append(dict(shared,condition_image=b['condition_image'],prompt_variants_en=b['prompt_variants_en'],
            default_prompt_variant=1,suggested_seeds=[0,1,2],source_width=b['source_width'],source_height=b['source_height'],
            status='generation_required',reuse_legacy_generated_output=False))
        protocol=c['judge_protocol']
        reviews.append(dict(shared,target=protocol['target'],events=observation_definitions(protocol['events']),
            uncertainty_policy=protocol['uncertainty_policy'],status='awaiting_new_generated_video',
            generated_video_sha256=None,reviewer=None,event_labels=None,
            reuse_legacy_annotations_or_scores=False))
        rows.append(dict(shared,reason=reason,target_event=u['event'],
            status='generation_and_annotation_required',legacy_result_policy='retain in original version; never rename or copy to this input'))
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    write_rows(out/'tasks.jsonl',rows);write_rows(out/'generation_tasks.jsonl',generation);write_rows(out/'annotation_tasks.jsonl',reviews)
    text=['# Core100 v4：15条独立重生成、重标注任务','',
        '名单：`'+data['roster_release']+'`。这15条均不得套用旧视频、标签或分数。旧结果保留在原版本。',
        '', '|案例|原因|主事件|状态|','|---|---|---|---|']
    for r in rows:text.append(f"|{r['clip_id']}|{r['reason']}|{r['target_event']}|待新生成及标注|")
    text+=['','每个模型使用同一prompt变体和种子配额。变体1、三个种子时，这15条对应45个生成位置；若三个变体都跑则为135个。',
        '正式Core100评分仍注册全部100条。其余85条仅在视频输入、模型、种子、帧率、观察窗口和prompt完全匹配时才有视频复用的可能；本导出不自动复用它们，也不搬用旧分数。事件定义改变的结果应按新版独立判读。',
        'generation_tasks.jsonl不含事件答案、临界距离或反演真值；annotation_tasks.jsonl不含参考结果标签，待新生成视频绑定哈希后走质量筛查、事件判读和人工复核。',
        '这是任务清单，不是已执行回执。实际模型、输出时长和执行环境仍需登记；不对参考窗口补帧或重定时。']
    (out/'README.md').write_text('\n'.join(text)+'\n',encoding='utf8')
    write_json(out/'MANIFEST.json',dict(roster_release=data['roster_release'],registry_sha256=sha(registry),
        required_new_inputs=15,default_prompt_variant=1,suggested_seeds=[0,1,2],generation_positions_per_model=45,
        old_results_modified=False,actual_generation_executed=False,export_code_sha256=sha(__file__),
        files={f.name:sha(f)for f in out.iterdir()if f.is_file()}))
    return dict(required_new_inputs=15,generation_positions_per_model=45,actual_generation_executed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--pointer',type=Path,default=POINTER)
    a=p.parse_args();print(json.dumps(export(a.out,a.pointer)))
