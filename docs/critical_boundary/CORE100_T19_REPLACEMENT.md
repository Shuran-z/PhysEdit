# Core100 T19参考替换

当前版本为 `core100-t19-isaac-v1-20261031`。100个案例槽位保留；T19的5条参考改用Isaac视频，其余95条的冻结v6输入逐项保持一致。原T19参考、生成结果和人工标注保留，新版本不继承它们的成绩。

| 案例 | 参考视频 | 横向偏心 / m | 接触真值 | 归一化距离区间 |
|---|---|---:|---:|---|
| T19_C01 | 家居背景、更新视频、minus | -0.0940625 | 0 | [0, 0.00390625] |
| T19_C02 | 家居背景、保留原版、plus | -0.09296875 | 1 | [0, 0.00390625] |
| T19_C03 | 工作室背景、保留原版、minus | -0.0940625 | 0 | [0, 0.00390625] |
| T19_C04 | 工作室背景、保留原版、plus | -0.09296875 | 1 | [0, 0.00390625] |
| T19_C05 | 工作室背景、保留已核查原版、global | 0.14 | 0 | [0.125, 0.1875] |

5条来自5次不同轨迹，不将同步机位当作独立案例。C01/C02、C03/C04各为一组跨边界配对。前4条采用原搜索区间 `[-0.0940625, -0.09296875] m`，归一化跨度来自原输入域 `[-0.14, 0.14] m`。

C05位于接触带的右侧，采用同上下文已发布样本的转变区间 `[0.0875, 0.105] m`，没有错误沿用左侧边界。它的距离区间跨越mid/far界限，保留区间并参与普通事件评分，不强行分桶或计入NearAcc。这项恢复读取已有参数和原生接触记录，未启动额外仿真。

接触真值来自原Isaac `first_contacts_s`及事件深度记录，绑定配置、QA、视频哈希。5条视频均完整解码，已检查运动抽帧和对象局部视图；没有将解码通过等同于物理正确性证明。临界擦碰在生成视频中可能难以目视判断，应允许跟踪辅助和人工复核，不能直接把投影重叠判为接触。

新输入从参考第0帧开始，保留完整原观察窗至第209帧，即 `209/30` 秒。条件图、视频、三个英文短prompt及各自哈希均已冻结。原5秒生成视频不能冒充覆盖这个窗口。

统一入口为 `catalog/active_core100_conditions.json`。运行：

```powershell
python -m physedit.core100_release status
python -m physedit.core100_release prepare --model H3 --variant 1 --out runs/t19_h3_p1
python -m physedit.core100_release prepare --model H3 --variant 2 --out runs/t19_h3_p2
python -m physedit.core100_release prepare --model H3 --variant 3 --out runs/t19_h3_p3
```

每个目录包含可由现有 `physedit.boundary` 读取的5条输入、5条答案、`spec.json`和验证回执。默认是同种子配对，对应 `coupled_pair_accuracy`；使用 `--pairing-mode independent` 时两端使用互不重叠的种子流，对应 `independent_pair_accuracy`，两种结果分别报告。指定实际生成命令后沿用现有生成、筛查、事件标注和评分流程。

整套Core100导入支持 `python -m physedit.evaluation_split --source-dir SOURCE --reference-release active --out NEW`。旧源划分文件不修改。

标注管线按新版本、参考视频哈希、条件图哈希和prompt同时核验输入，并校验完整原生观察窗。网站的 `/api/active-core100-reference` 和临界结果中的 `active_reference_release` 返回当前绑定；旧任务不改标、不转移标签。参考替换完成不表示新5条的模型生成和人工标注已经完成。
