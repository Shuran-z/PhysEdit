# Core100第四版：100条临界参考接入

生成输入请使用[实际提交文本绑定修订版v5](CORE100_ACTUAL_PROMPT_BINDINGS_V5.md)。本页保留第四版的参考、机位和物理协议记录；运行核对发现的57条prompt恢复文本绑定已在独立版本修复，100条参考及临界距离不变。

名单版本：`core100-critical-pairs-v4-20261103`。协议版本：`core100_critical_protocol_v6_20261103`。

20个场景、每场景5条，共100条。临界数值、原参数族、主事件、观察窗口、归一化距离及视觉参考已全部接入。数值待完成0条，视觉参考待完成0条，判为不适用0条。上述数量是参考接入结果，不是生成模型成绩。

本版已在本地封存并接入独立生成、筛查、复核及评分入口。线上旧任务、旧模型成绩和旧标注未迁移，也未宣称本版已发布至Hugging Face。

## 本次只改T03_C02的机位

作者于2026-11-03确认“换成cam02，补齐100条参考”。相对第三版，99条输入逐字段保留；T03_C02从cam03换为同一原始轨迹配置的cam02。两份原配置取回后逐项比较，差异仅为相机身份、视角和图像输出位置。物体、随机种子、求解设置、初始条件和控制完全一致。未重新求解或渲染。

新视频为854×480、210帧、30 fps，已完成全解码、原生时间戳和哈希检查；条件图与视频原生第4帧逐像素一致。观察窗口仍为从条件帧起5秒。三种prompt逐字沿用，未添加结果提示。

主事件是“罐接触原手机后，手机越过支撑边缘并开始下落”，不要求接触地面。cam02的110、114、118帧可见该过程。画面复核记录由助手完成，不冒充独立多人金标。原物理状态来源继续保留；不声称另有一份独立录制的cam02状态文件。

|项目|绑定值|
|---|---|
|参数族|`lower_phone_com_edge_distance_m`|
|参考参数|0.1 m|
|临界观察区间|[0.1, 0.4] m|
|原归一化域|[0.006, 0.1] m，跨度0.094 m|
|归一化距离区间|[0, 3.1914893617]|
|距离分层|区间跨越多个分层，保留不确定；不计为Near|
|主事件参考标签|1：发生越缘下落|

区间、事件定义和归一化没有因换机位改变。原cam03的视频、参数、标签和模型输出留在旧版。cam03的生成结果、人工标签或反演相机标定均不能移交给cam02。

## 指标适用范围

|指标或统计|本版参考范围|
|---|---|
|主事件准确率及距离分层|100条参考已绑定，正式分数仍需生成结果和最终标注|
|NearAcc|14条Near参考：负类6条、正类8条；两类各占一半|
|独立生成PairAcc|5组跨界配对，两端成功率相乘后按组聚合|
|共享生成种子PairAcc|8组跨界配对，按同种子两端联合成功统计；与独立配对分开报告|
|完整EventExact|本版未登记完整链条及全部时序真值，输出空值；主事件或目标向量命中不替代它|
|BoundaryError|未登记模型响应网格及阈值估计，输出空值；参考两侧对照不替代响应曲线|
|物理反演|适用窗口与验证凭据独立登记；不能因为临界事件可评就自动准入|

筛查确认失败的生成结果保留在注册总分母，事件和反演分别报告覆盖率。机器高置信度仅作预标注；不确定、证据不足或字段矛盾保留人工复核入口。参考准入不等于生成质量通过。

T08三条保留作者批准的CPU64细化设置与不确定性披露；它们不称为原渲染时计算的临界值。T11_C03使用原联合G扫描的无量纲路径距离，不解释成单个参数的效应。

## 版本入口与命令

- 名单：`catalog/core100_critical_pairs_v4.json`
- 协议：`catalog/prepared_core100_critical_protocol_v4.json`
- 机位来源与作者确认：`benchmarks/core100_critical_pairs_v4_20261103/evidence/`
- [15条必须独立重生成、重标注的任务清单](../../benchmarks/core100_regeneration_v4_20261103/README.md)：包含生成输入、盲标任务和版本／文件哈希绑定；每模型以变体1、三个种子执行时共45个生成位置。
- 20场景及100条逐项核查：`review/core100_camera_completion_audit_20261103/`

```powershell
python -m physedit.core100_critical status `
  --registry benchmarks/core100_critical_protocol_v6_20261103/registry_a9716a0d452e.json `
  --expected-registry-sha256 a9716a0d452ecdc3667bf97c7b23c940238c5637804e00aaf8dcb2b1e53f213c

python -m physedit.core100_critical prepare `
  --out review/core100_v4_new_run --model <模型登记名> `
  --fps 24 --variant 1 --seeds 0 1 2 `
  --registry benchmarks/core100_critical_protocol_v6_20261103/registry_a9716a0d452e.json `
  --expected-registry-sha256 a9716a0d452ecdc3667bf97c7b23c940238c5637804e00aaf8dcb2b1e53f213c

python -m scripts.audit_prepared_core100_critical `
  --pointer catalog/prepared_core100_critical_protocol_v4.json `
  --out review/core100_v4_reference_audit_new
```

`prepare`只准备输入，不加载生成模型。执行前仍须通过[原生模型时长检查](CORE100_SIX_REPLACEMENTS_V3.md#生成模型的时长检查)：现登记H3仅86条窗口兼容，剩14条不能通过缩短参考窗口解决。本次300个生成位置的通用预检通过，不代表实际模型推理已完成。

使用两步裁判入口：

```powershell
python -m physedit.core100_critical judge `
  --run-dir <本版已注册生成目录> --protocol review/core100_v4_new_run/judge_protocol.json `
  --quality-predictions <质量筛查JSONL> --event-predictions <逐事件预标注JSONL> `
  --reviews <最终人工复核JSONL> --out-dir <新的评分输出目录>
```

相对线上旧版，继承8条替换、随后6条替换及本次1条机位替换，共15条需独立生成和标注；100条参考接入完成不等于这15条已有新模型成绩。原线上入口保持原版本，正在进行的任务不受影响。

从干净Git检出使用时，直接读取已封存的协议和清单即可，不需要本机`review/`目录。重建原始仿真证据的维护脚本另需其注明的源数据。可重新导出15条任务：

```powershell
python -m physedit.core100_tasks --out review/core100_v4_regeneration_new
python -m pytest -q tests/test_core100_camera_revision.py tests/test_core100_tasks.py tests/test_registered_judge_contract.py tests/test_boundary_registered_native.py tests/test_core100_protocol_status.py
```

公开Git检出的测试验证输入绑定、失败分母、复核及评分接口；不会加载生成模型，也不是模型准确率实验。

独立工作树验证为132项通过、3项本地证据检查跳过，详见[发布检查记录](CORE100_V4_PUBLICATION_CHECK.md)。
