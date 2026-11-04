"""Preserve originals; export explicit prompt holds and filtered candidate manifests."""
from pathlib import Path
import collections
import gzip
import hashlib
import json
import cv2

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'review/prompt_revision_20261102'
OUT = ROOT / 'review/t10_groundtruth_resolution_20261102'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    source = SRC / 'videos.jsonl.gz'
    initial_hash = sha(source)
    audit = json.loads((OUT / 'SOURCE_AUDIT.json').read_text())
    evidence = {r['canonical_video_id']: r for r in audit['rows']}
    assert len(evidence) == 120
    # New evidence requires individual review rather than automatic numeric replacement.
    assert not any(r['annotation_exists'] or r['same_directory_state_candidates'] for r in evidence.values())
    assert not audit['matching_logs']
    decoded = []
    for vid, r in evidence.items():
        path = OUT / 'groundtruth' / (vid + '.mp4')
        assert sha(path) == r['sha256']
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        declared = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        count = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            assert frame is not None and frame.size
            count += 1
        cap.release()
        assert count == declared and count > 0 and fps > 0, (vid, count, declared)
        decoded.append({'video_id': vid, 'sha256':r['sha256'], 'frames':count, 'fps':fps})
    totals = collections.Counter()
    holds = []
    outputs = ['videos_with_t10_gate.jsonl.gz', 'nonconflicting_prompt_candidates.jsonl.gz',
               'train_final_candidates_after_t10_hold.jsonl.gz']
    handles = [gzip.open(OUT / name, 'wt', encoding='utf8') for name in outputs]
    try:
        with gzip.open(source, 'rt', encoding='utf8') as f:
            for line in f:
                row = json.loads(line)
                vid = row['canonical_video_id']
                held = vid in evidence
                before = {k:row.get(k) for k in ['sha256','download','split','source_group_id','parameter_facts','prompt_variants_en','prompt_variant_sha256']}
                row['t10_groundtruth_gate'] = {
                    'status':'hold_unresolved_groundtruth_parameters' if held else 'no_t10_conflict',
                    'exact_parameter_use_blocked':held,
                    'audit':'SOURCE_AUDIT.json' if held else None,
                    'note':'This gate does not replace other data quality or split admission checks.'}
                assert before == {k:row.get(k) for k in before}
                text = json.dumps(row, ensure_ascii=False) + '\n'
                handles[0].write(text)
                totals['all'] += 1
                if held:
                    e = evidence[vid]
                    holds.append({'video_id':vid,'trajectory_id':vid.rsplit('__',1)[0],
                                  'video_sha256':row['sha256'],'split':row.get('split'),
                                  'blocked_uses':['new_exact_parameter_training','new_exact_parameter_evaluation'],
                                  'old_prompt_speed_mps':3.0,
                                  'published_config_velocity':next(o['motion']['initial_velocity'] for o in e['config']['dynamic_objects'] if o['name']=='t10_tape_roll'),
                                  'resolution':'original prompt retained as historical only; recover same-run states or prepare separately versioned simulation before readmission'})
                    totals['held'] += 1
                    totals['held_' + row.get('split','unknown')] += 1
                else:
                    handles[1].write(text)
                    totals['nonconflicting'] += 1
                    if row.get('split') == 'train_final':
                        handles[2].write(text)
                        totals['train_final_candidates'] += 1
    finally:
        for f in handles:
            f.close()
    assert totals['all'] == 72000 and totals['held'] == 120 and totals['nonconflicting'] == 71880
    assert len({r['trajectory_id'] for r in holds}) == 40
    assert totals['held_train_final'] == 48
    assert sha(source) == initial_hash
    (OUT / 'HOLD_120.json').write_text(json.dumps(holds,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT / 'VIDEO_DECODE_CHECK.json').write_text(json.dumps(decoded,indent=2),encoding='utf8')
    # Verify exported membership; flags alone are insufficient to enforce a hold.
    for name in outputs[1:]:
        with gzip.open(OUT/name,'rt',encoding='utf8') as f:
            rows=[json.loads(line) for line in f]
        assert not ({r['canonical_video_id'] for r in rows} & set(evidence))
        assert len({r['canonical_video_id'] for r in rows}) == len(rows)
    report={'status':'unresolved_videos_quarantined_in_new_candidate_views',
            'counts':dict(totals),'trajectories_held':40,'exact_numeric_prompt_corrections':0,
            'source_manifest_sha256':initial_hash,'source_manifest_unchanged':True,
            'verified_video_hashes':120,'fully_decoded_videos':len(decoded),
            'same_run_states_found':0,'matching_logs_found':0,
            'video_speed_estimates_used_as_exact_truth':False,
            'active_training_or_online_release_modified':False,
            'semantic_final_approval':False,
            'files':{n:sha(OUT/n) for n in outputs+['HOLD_120.json','VIDEO_DECODE_CHECK.json','SOURCE_AUDIT.json']}}
    (OUT/'REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    (OUT/'README.md').write_text('''# T10 ground truth 冲突处理

120个视频（40次仿真、各3视角）原始输出哈希全部一致，全部完整解码通过。逐条检查原输出目录及配置登记的annotation路径，并搜索项目和父目录logs/reports，未恢复同次执行状态或匹配日志。视频像素运动未被冒充精确米制速度，3与1.8 m/s均未强行写成真值。

使用入口：
- videos_with_t10_gate.jsonl.gz：72000条完整记录，含明确的T10使用限制。
- nonconflicting_prompt_candidates.jsonl.gz：71880条，已物理排除120条冲突记录。
- train_final_candidates_after_t10_hold.jsonl.gz：原train_final划分去掉48条冲突视频后的候选清单。
- HOLD_120.json：逐条列出视频哈希、原划分、冲突值和重新准入条件。

以上是本次审计生成的新候选入口，尚未接入线上或正在运行的训练。其它质量、来源族排除和新版prompt语义审查仍须按原规则执行；不代表71880条已通过全部数据质量审核。保留原prompt作历史记录，不将其视为已经核实。Core100独立的T10_C05位置参数冲突未由本次速度审计解决。

重新准入：恢复与ground truth视频同次执行的状态，或经相机和仿真时钟校准后提供有误差范围的测量证据；若需精确指定输入而仍无原始证据，另建有明确参数和完整状态记录的新仿真版本，不替换旧视频及已有模型结果。
''',encoding='utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
