"""Collect original-GPU-backend repeat/convergence experiments, without launching jobs."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'review/t15_boundary_pilot_20261014'
TAGS = ['gpu128_r1', 'gpu128_r2', 'gpu256_r1', 'gpu512_r1']
remote = '''
import json,pathlib,hashlib
base=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t15_boundary_pilot_20261014')
out={}
for tag in TAGS:
 folder=base/tag
 if not (folder/'results.json').exists():
  out[tag]={'status':'not_finished'};continue
 out[tag]={'status':json.loads((folder/'pilot_status.json').read_text()) if (folder/'pilot_status.json').exists() else 'finishing',
           'provenance':json.loads((folder/'pilot_provenance.json').read_text()),
           'rows':json.loads((folder/'results.json').read_text())}
 for row in out[tag]['rows']:
  path=pathlib.Path(row['output'])/'metadata/physics.json'
  s=json.loads(path.read_text());row['state_file_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
  row['frames_sha256']=hashlib.sha256(json.dumps(s['frames'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
  row['recorded_solver']=s['physical_provenance']
print(json.dumps(out,indent=2))
'''.replace('TAGS', repr(TAGS))
p = subprocess.run(['ssh', 'p25', 'python3', '-'], input=remote, text=True, encoding='utf-8',
                   capture_output=True, timeout=120)
p.check_returncode()
raw = json.loads(p.stdout)
(OUT / 'gpu_results.json').write_text(p.stdout, encoding='utf-8')
events = ['book_contacts_laptop', 'laptop_crosses_support_boundary', 'laptop_falls_to_floor',
          'laptop_contacts_phone', 'phone_slides']
by_tag = {tag: {row['speed']: row for row in raw[tag].get('rows', [])} for tag in TAGS}
common = set.intersection(*(set(rows) for rows in by_tag.values()))
summary = []
for speed in sorted(common):
    rows = [by_tag[tag][speed] for tag in TAGS]
    vectors = [[int(row['audit']['event_frames'].get(e) is not None) for e in events] for row in rows]
    summary.append({'speed': speed, 'vectors': dict(zip(TAGS, vectors)),
                    'qa': {tag: by_tag[tag][speed]['audit']['valid'] for tag in TAGS},
                    'errors': {tag: by_tag[tag][speed]['audit']['errors'] for tag in TAGS},
                    'same_dt_repeat_events_agree': vectors[0] == vectors[1],
                    'same_dt_repeat_states_identical': rows[0]['frames_sha256'] == rows[1]['frames_sha256'],
                    'fall_agrees_all': len({v[2] for v in vectors}) == 1,
                    'all_events_agree': len({tuple(v) for v in vectors}) == 1,
                    'all_qa_valid': all(row['audit']['valid'] for row in rows)})
result = {'tags': TAGS, 'completed_runs': sum(len(rows) for rows in by_tag.values()),
          'points': summary, 'interpretation': 'Agreement on this tested grid only; not a proof of a unique physical threshold.'}
(OUT / 'gpu_comparison.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
if summary:
    safe_no = [r['speed'] for r in summary if r['all_qa_valid'] and r['fall_agrees_all']
               and r['vectors'][TAGS[0]][2] == 0]
    safe_yes = [r['speed'] for r in summary if r['all_qa_valid'] and r['fall_agrees_all']
                and r['vectors'][TAGS[0]][2] == 1]
    result['tested_stable_no_fall_points'] = safe_no
    result['tested_stable_fall_points'] = safe_yes
    result['repeat_event_agreement_count'] = sum(r['same_dt_repeat_events_agree'] for r in summary)
    result['step_sensitive_fall_points'] = [r['speed'] for r in summary if not r['fall_agrees_all']]
    (OUT / 'gpu_comparison.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    lines = [
        '# T15 原 GPU 后端复核', '',
        '日期：2026-10-14。仅复核地球重力、家庭背景、A 族固定上下文；不推广到全部 T15 或整个数据集。', '',
        '## 执行范围', '',
        f'完成 {result["completed_runs"]} 次新 GPU 仿真：11 个速度点，128 步/帧两次，256 和 512 步/帧各一次。',
        '使用原 GPU 源码的未修改副本，源哈希与原发布轨迹记录一致；Genesis 0.4.1、float64、box collision、自然静置 1 秒、接触时间常数 0.002 秒。',
        '在 p25 空闲窗口使用 RTX 4090，设备编号和源哈希记录在 gpu_results.json 的 provenance 中；运行之间可能使用不同同型号 GPU。',
        '仅产生独立诊断状态，不修改或覆盖正式视频。没有新渲染，也没有运行视频生成模型。', '',
        '## 事件与质量记录', '',
        '表格每格为“跌落/命中手机/手机移动”；× 表示该次未通过原 V11 全片 QA。事件位和全片 QA 分开保留。', '',
        '| 速度 m/s | 128 第一次 | 128 第二次 | 256 | 512 |',
        '|---:|---|---|---|---|',
    ]
    for row in summary:
        cells = []
        for tag in TAGS:
            cells.append('/'.join(map(str, row['vectors'][tag][2:])) + ('' if row['qa'][tag] else ' ×'))
        lines.append('| ' + f'{row["speed"]:.3f}' + ' | ' + ' | '.join(cells) + ' |')
    lines += ['', '## 稳定性判读', '',
              f'- 两次原步长运行事件向量一致：{result["repeat_event_agreement_count"]}/{len(summary)}。逐帧浮点状态哈希是否一致另外记录，不混同于标签一致。',
              f'- 所测设置下均不跌落且均通过 QA 的网格点：{safe_no} m/s。',
              f'- 所测设置下均跌落且均通过 QA 的网格点：{safe_yes} m/s。',
              f'- 跌落位随步长变化的点：{result["step_sensitive_fall_points"]} m/s。',
              '- 这些结论是有限网格、有限求解设置下的经验稳定性；不能推断未采样位置全部稳定，也不能自动认为存在唯一单调临界点。',
              '- 如果某点跨步长改变，当前证据支持“数值设置敏感”，尚不足以断言具体求解器 bug，也不能认证为真实物理分岔。', '',
              '## 本轮可以冻结的范围与用法', '',
              '本次网格中最接近的一对、且所有设置均通过 QA 的稳定跌落异侧点为 2.104 m/s（不跌落）与 2.160 m/s（跌落），间距 0.056 m/s。',
              '**[2.104, 2.160] 是稳定异侧端点构成的待认证局部区间，不是已经证明唯一阈值所在的精确区间。**局部已有非单调和步长敏感证据，不能直接取中点作为真值，也不能推断区间外全部具有固定标签。',
              '对于包括手机响应的五位事件向量，更保守的对照为 2.104 与 2.196 m/s：二者分别稳定为 (1,0,0,0,0) 与 (1,1,1,0,0)，且四次均通过 QA。',
              '2.160 m/s 可以用作“跌落”对照，但不能用作稳定的“手机命中”正例；2.304 m/s 的事件位稳定，但 256 步全片 QA 失败，不应不加区分地列入严格全片通过集。',
              '2.088、2.096、2.112、2.120、2.124 m/s 暂标为数值敏感，不进入硬临界真值。不能把其中看起来最顺眼的一次选出来作为唯一正确答案。',
              '本次未找到跨所测设置均通过 QA 且稳定命中手机的正例，故该固定上下文暂不认证手机命中边界。',
              '新点只有状态，没有新渲染及人工可见性复核；稳定对照仍须完成媒体绑定后才能加入视频测试。测试其余求解设置、更多近邻与物理扰动之前，不报告高精度 BoundaryError。', '',
              '## 对视频质量的含义', '',
              '本实验检查的是参考事件真值的数值稳健性，不是分辨率、材质或渲染观感。原发布锚点复现与新补采点敏感应分别报告。',
              'QA 不通过也需区分原因：手机离开冻结可见地板范围是场景/评测范围问题，不直接等同于违反物理；穿透等则需检查接触数值质量。所有具体原因见 gpu_comparison.json。',
              '适合普通事件学习或视觉展示，不自动意味着足以标定精确临界值。反之，个别临界点未收敛，也不能据此宣判整个视频数据集不合格。', '',
              '## 证据', '',
              '- [完整 GPU 输出及哈希](gpu_results.json)',
              '- [逐点稳定性与 QA 原因](gpu_comparison.json)',
              '- [执行脚本](run_gpu_reference_sweep.py)',
              '- [结果收集脚本](../../scripts/t15_gpu_boundary_report.py)', '']
    (OUT / 'GPU_RECHECK.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps(result, indent=2))
