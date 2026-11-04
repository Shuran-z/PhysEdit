"""Write a compact report from the verified live receipt and live scores."""
import collections,csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'review/core100_remaining74_admission_20261101'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
r=read(W/'LIVE_FORMAL.json');receipt=read(W/'DEPLOYMENT.json')
assert receipt['live_api_verified'] and receipt['old_scores_preserved']
old=read(W/'live_before/resources/core100_formal_cohorts.json')
old_ids={x['clip_id']for c in old['cohorts']for x in c['references']}
new=[x for x in r['outputs']if x['clip_id']not in old_ids]
with (W/'SCENE_MODEL_RESULTS.csv').open('w',encoding='utf-8-sig',newline='')as f:
    writer=csv.DictWriter(f,fieldnames=list(r['per_scene_model'][0]));writer.writeheader();writer.writerows(r['per_scene_model'])
rows=[]
for model in sorted({x['model']for x in r['outputs']}):
    matching=[x for x in r['outputs']if x['model']==model and not x.get('historical_input_excluded')]
    known=[x for x in matching if x['final_correct']is not None]
    rows.append(dict(model=model,matching_outputs=len(matching),scored=len(known),correct=sum(x['final_correct']for x in known),pending=len(matching)-len(known)))
with (W/'MODEL_SCORE_COVERAGE.csv').open('w',encoding='utf-8-sig',newline='')as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
text='''# Core100 原始参考准入与成绩

已部署到 https://label.yeegoods.cn/physics/ 。所有数字取自本目录 LIVE_FORMAL.json 与 DEPLOYMENT.json。

- 本轮核查剩余74条，新增54条原目标事件参考，累计80/100条。
- 其中40条具有正式准入的原边界区间；仅声明原始固定仿真协议下已观察的局部区间，不声明全局唯一边界。
- Near参考10点，合法配对3组；本轮不制造新的配对或采用区间中点强行分桶。
- 当前关联2880条模型输出，909条已有完整评分证据，其中正确99条。本轮新增641条可判定输出、其中正确73条。这是覆盖数，不是完整Core100准确率。
- 旧26条参考所在21个评分组的定义、逐视频结果与模型成绩逐项对比一致；未更新任务、人工标签、prompt或物理参数。
- 原始参考为自动化源证据复核与AI画面核验，不冒充独立人工金标准。多事件场景仅准入登记的具体目标，不等同完整事件链EventExact。

逐场景逐模型正式目标成绩见 SCENE_MODEL_RESULTS.csv；完整分母未齐时 TargetAccuracy 为空，accuracy_on_scored 只描述已判定部分。
模型输出可判定覆盖见 MODEL_SCORE_COVERAGE.csv；各窗口、各目标分开报告，不合并成一个总准确率。

已出双侧NearAcc：旧T17的6.4秒窗口，Cosmos3-Nano为0%，LTX-Video-2B为0%。同seed PairAcc仅Cosmos3-Nano可出，为0%；LTX配对不完整，保留N/A。其余Near点/配对缺匹配生成、完整窗口或定稿证据时不报满分母成绩。

## 仍未准入的20条

- T06_C01/C02/C03/C05、T09_C01–C05：已经找到原状态及候选视频，但尚未将其与当前参考视频的原父SHA/解码帧一致绑定。同名文件不足以继承事件和边界。
- T10_C01–C05：已检查已知原始输出及候选，缺与当前参考身份一致的原状态。候选视频哈希不一致或未找到。
- T11_C01–C05：原状态与五秒原判据已恢复，末帧目标离开当前视野；缺从当前参考RGB核验末态的可观察性证据。
- T15_C04：原全子步接触记录已恢复为未接触，额外核查了36–71连续帧；原路径有遮挡，尚未完成整个观察窗的负例可观察性证据闭环。

未因上述问题排除训练视频、修改既有标签或要求全部重生成。状态与原因已同步网站100条登记。

## 验证

36项针对性测试通过。线上服务active，公开页面HTTP200，六项认证导出成功，匿名导出被拒绝。视频继续通过Hugging Face链接评测，本轮未上传视频到网站数据盘。
'''
(W/'RESULTS_ZH.md').write_text(text,encoding='utf8')
print(json.dumps(dict(new_references=len({x['clip_id']for x in new}),new_scored=sum(x['final_correct']is not None for x in new),live_summary=r['summary'])))
