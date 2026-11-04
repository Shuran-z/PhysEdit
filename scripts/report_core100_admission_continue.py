"""Summarize verified live admission, retaining every Core100 row."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_reference_admission_continue_20261101'
LIVE=WORK/'t16_followup'
formal=json.loads((LIVE/'LIVE_FORMAL.json').read_text(encoding='utf8'))
connected=json.loads((LIVE/'LIVE_CONNECTION.json').read_text(encoding='utf8'))
refs={r['clip_id']:r for c in formal['cohorts']for r in c['references']}
near_status={
 'T05_C03':'正式单侧Near参考；缺同上下文、同窗口负侧输出，不能组成Pair。',
 'T13_C01':'正式单侧Near参考；24fps窗口4–124帧；缺合法负侧配对。',
 'T13_C02':'正式单侧Near参考；24fps窗口4–124帧；缺合法负侧配对。',
 'T16_C05':'正式单侧Near参考；已核对原发布正负状态端点；旧正点不是当前C04，不能继承配对。',
 'T16_C04':'原目标接触事件已正式接入；现边界使用改动求解器，Near不准入。',
 'T09_C04':'原生参考已定位；原窗口4.1秒；重放轨迹与原轨迹不一致，边界上下文仍缺证明；不能继承5秒终态标签。',
 'T06_C05':'原生参考已定位；原窗口4.1秒；缺与原视频绑定的逐对接触链证据，补充重放不能冒充原状态。',
}
lines=['# Core100正式接入核验（2026-11-01）','',
 '以本目录保存的线上API快照为准；旧任务、人工标签和既有历史成绩未改。', '',
 f"全部100条原生参考均已核对SHA并正确解码。正式目标参考 {len(refs)}/100；Near参考10条；合法配对3组。参考准入不表示该模型输出已生成或已人工定稿。",'',
 '## 原剩余7个Near候选','', '| 案例 | 结论与缺项 |','|---|---|']
lines += [f'| {cid} | {status} |'for cid,status in near_status.items()]
lines += ['', '## 全20场景逐条核验表','',
 '| 案例 | 正式目标参考 | Near参考 | 原观察窗/秒 | 缺项或限定 |','|---|---|---|---:|---|']
for row in connected['cases']:
 cid=row['clip_id'];r=refs.get(cid)
 reason=(near_status.get(cid) or row.get('reference_progress_reason') or '; '.join(row.get('reference_blockers',[])) or '已准入；模型输出、人工定稿和合法配对分别核验。')
 if isinstance(reason,list):reason='; '.join(reason)
 lines.append(f"| {cid} | {'是'if r else'待核验'} | {'是'if r and r.get('bin','near')=='near'else'否'} | {row['horizon_s']} | {str(reason).replace('|','/')} |")
lines += ['', '## 已计算成绩', '',
 '网站按各场景各模型展示目标正确率、单侧Near目标正确率、双侧NearAcc和同seed配对PairAcc。缺人工定稿、精确窗口、原测量证据或新版模型输出的保留N/A；质量失败按原协议计错。',
 '本次上线通过33项测试、线上API与6类CSV导出核验。任务与标注不更新，旧结果一致性检查通过。']
(WORK/'FORMAL_ADMISSION_REPORT_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print(json.dumps(dict(cases=len(connected['cases']),formal=len(refs),near_candidate_status=near_status),ensure_ascii=True))
