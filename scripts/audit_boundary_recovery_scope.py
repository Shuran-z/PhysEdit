"""Separate original-value recovery from supplemental computation, without promotion.

This audit reads the existing ledger; it never starts/stops a solver or changes
formal scoring. A sample with one original family does not imply all its events
have a boundary. Missing records are lookup work, not proof a search never ran.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def summarize(rows):
    scenes = []
    for scene in [f'T{i:02}' for i in range(1, 21)]:
        groups = collections.defaultdict(set)
        families = collections.defaultdict(lambda: collections.Counter())
        for row in rows:
            if row['scene_id'] != scene:
                continue
            category = row['reference_category']
            key = (row.get('engine'), row.get('repo_id'), row.get('revision'), row['sample_id'])
            groups[category].add(key)
            families[str(row.get('family_id'))][category] += 1
        original = groups['recovered_original']
        supplemental = groups['supplemental']
        stars = groups['rendering_star']
        scenes.append(dict(
            scene_id=scene, retired=scene == 'T19',
            original_reference_samples=len(original),
            supplemental_only_samples=len(supplemental - original),
            rendering_centre_only_samples=len(stars - original - supplemental),
            original_and_supplemental_overlap=len(original & supplemental),
            family_record_counts=dict(families),
            original_lookup_complete=False,
            necessary_recompute_count=None,
            note='Counts describe ledger coverage, not completeness or formal NearAcc admission. '
                 'Sample overlap alone cannot cancel event/context-specific searches.'))
    return scenes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('review/scene_family_completion_20261018'))
    args = parser.parse_args()
    source = args.root / 'original_value_distance_ledger/combined_distance_inputs.jsonl'
    payload = source.read_bytes()
    rows = [json.loads(line) for line in payload.decode('utf-8').splitlines() if line.strip()]
    scenes = summarize(rows)
    result = dict(source=str(source.resolve()), source_sha256=hashlib.sha256(payload).hexdigest(),
                  scope='Existing ledger only; no new publication revision verification', scenes=scenes,
                  necessary_recompute_total=None,
                  policy='Bind recovered original values first; keep refinement and reproducibility '
                         'separate; require documented original-source lookup before necessary recomputation.')
    target = args.root / 'original_first_scope_audit.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 原值优先：20场景工作范围核查', '',
             '仅核查当前距离登记快照；不把未找回认定为未计算，不把额外复现实验当作原值接入前置条件。',
             '以下为不同来源样本数，不是临界点数或正式 NearAcc 数。T19旧版单列停用。', '',
             '|场景|已有原值|仅补算距离|仅渲染中心待追溯|原值与补算重叠|',
             '|---|---:|---:|---:|---:|']
    for r in scenes:
        lines.append('|{scene_id}{retired_label}|{original_reference_samples}|{supplemental_only_samples}|'
                     '{rendering_centre_only_samples}|{original_and_supplemental_overlap}|'.format(
                         **r, retired_label='（停用）' if r['retired'] else ''))
    lines += ['', '## 执行顺序', '',
              '1. 原值已有：保留原值距离；按版本、参数族、事件、固定上下文对应，不等待复现实验。',
              '2. 仅补算距离：保留已完成结果，继续追溯原值，不为取得更细区间重复启动搜索。',
              '3. 仅渲染中心：追踪中心的生成代码及搜索结果；既不直接冒充求解值，也不自动启动补算。',
              '4. 全部未登记的发布样本：须另核对当前发布清单，不能从本登记表推断数量或补算需求。',
              '5. 必要补算：逐项记录原来源查找范围、目标事件及缺失原因后再确定。当前总数未知。',
              '', '原值与补算重叠只提示可能重复工作；参数族、事件或物理上下文不一致时不能取消任务。']
    (args.root / 'ORIGINAL_FIRST_SCOPE_AUDIT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(target), scenes=scenes), ensure_ascii=False))


if __name__ == '__main__':
    main()
