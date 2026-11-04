# 视频下载与使用说明

仓库：https://huggingface.co/datasets/phy2/phydataset

视频在 `data/T01/` 到 `data/T20/`，每个场景 **3,600 条独立 MP4**，共 **72,000 条**。

## 1. 下载视频

```bash
python -m pip install -U huggingface_hub
hf auth login
hf download phy2/phydataset --repo-type dataset --include "data/T*/*.mp4" --local-dir ./dataset
```

只下一个场景时，将 `data/T*/*.mp4` 改为 `data/T01/*.mp4`（其他场景同理）。下载后直接是 `dataset/data/T01/` 等目录，无需解压视频。

## 2. 下载提示词、配置对应信息和划分清单

在同一个工作目录运行：

```bash
hf download phy2/phydataset releases/physedit/downloads/physedit_metadata.zip --repo-type dataset --local-dir ./metadata_download
python -m zipfile -e ./metadata_download/releases/physedit/downloads/physedit_metadata.zip .
```

解压得到 `physedit/`，主要使用：

| 文件或字段 | 怎么对应 |
|---|---|
| `physedit/catalog/videos.jsonl.gz` | 全量清单，每行一条视频；`canonical_path` 就是视频在仓库中的路径，本地视频路径为 `dataset/` 加该路径。 |
| `canonical_video_id` | 当前视频文件名去掉 `.mp4`；用它关联划分表。不要用旧 `video_id` 拼接文件名。 |
| `prompt_variants_en` | 该视频的三条英文提示词，按顺序对应变体 1、2、3；`prompt_en` 是第 1 条。 |
| `parameter_facts`、`external_control_inputs`、`external_control_disclosure` | 该视频的物理参数、外部控制及说明；完整条件不能只从短提示词恢复。 |
| `current_render`（如有） | 当前重渲染的配置和来源，优先使用其中 `source_bundle`、`config_member`、`source_config_sha256` 读取并校验原始配置；不要把重渲染前的来源当成当前输入。 |
| `source_repo`、`source_revision`、`source_path`、`archive_member` | 原视频的来源追溯信息；`archive_member` 是视频成员名，不是配置成员名。配置应另查配置登记，不能靠替换文件后缀猜路径。 |
| `physedit/catalog/split_assignments.csv` | 用 `canonical_video_id` 关联；`split` 是训练或留出归属，`source_group_id` 是隔离同源组的标识。 |

新版 Genesis T19 的原始配置、轨迹及渲染元数据在 `physedit/provenance/t19_gen_new_20261030/source_metadata.zip`，逐条对应关系见同目录 `SOURCE_BINDINGS.jsonl`。其他来源的原始文件按其登记位置读取；元数据包不等于所有原始仿真文件的副本。

比较生成模型时，同一条案例使用相同提示词变体和 seed，保留完整提示词文本。

## 3. 训练与测试怎么用

- **训练：** `physedit/catalog/train_final.jsonl.gz`，45,357 条，覆盖 16 类；Genesis 与 Isaac 联合使用。
- **OOD 留出：** T03、T20、T11、T19 全部不训练，共 14,400 条。
- **测试、候补及同源组保护：** 其余受保护记录 12,243 条不训练；不等于 12,243 条固定测试样本。
- **正式测试：** 固定 Core100 为 80 ID + 10 OOD-1 + 10 OOD-2；另 80 条是候补。不另设验证集。

如果只需要训练视频，跳过第 1 步的全量下载，完成第 2 步后运行：

```bash
python physedit/tools/download_standardized.py --manifest physedit/catalog/train_final.jsonl.gz --output ./dataset
```

该命令按训练清单下载、校验视频哈希，并保持 `dataset/data/T01/` 等场景目录。不要把 72,000 条全量视频直接全部用于训练；直接使用上述训练清单即可。

当前 Core100 条件图及提示词单独导出：

```bash
python physedit/tools/prepare_core100_current.py --output ./core100_inputs
```

其中 T19 的 5 条使用当前 Isaac 参考，其余 95 条沿用已登记输入。新 T19 不沿用旧视频的成绩或标注。

复现实验时记录下载时的仓库提交号，后续下载可加 `--revision 提交号`。

## 原始配置下载

全量逐视频配置登记在 `physedit/catalog/config_bindings.jsonl.gz`，用 `canonical_video_id` 对应视频。`VERIFIED` 表示原始配置或明确标明类型的原始生成输入记录已核验，`config_download` 给出固定提交、归档成员和原始配置SHA256；未核实的记录明确标为 `UNRESOLVED`，不以参数表代替。

其中 T14 的924条 Isaac 视频使用原始生成矩阵记录（`config_document_type=original_generation_matrix_record`），不是独立配置文件。下载JSON保留原矩阵行的原始字节；配套原始矩阵、渲染脚本及启动脚本见 `physedit/provenance/t14s_original_inputs/`。另36条补生成视频使用已登记SHA256一致的原始执行任务JSON（`original_render_job_record`）。固定渲染器参数保留在脚本中；不把后期参数表拼成原始配置。

下载并解压本说明第2步的最新元数据包后，按视频编号导出原始配置：

```bash
python physedit/tools/download_original_configs.py --video-id physedit_genesis_t03_7b11b86fe8ac0134__cam01 --output ./dataset
```

得到 `dataset/configs/T03/physedit_genesis_t03_7b11b86fe8ac0134__cam01.json`。也可用 `--scene T03` 按场景导出；命令会检查请求的配置是否全部可用并逐条校验SHA256。

本轮检查72,000条：已核实配置绑定 69,360 条，待补 2,640 条；逐条缺口在 `physedit/checks/unresolved_configs.jsonl.gz`。先前抽查的4条缺口已全部补齐。

本次追溯纠正了399条T04的来源类型：它们只有元数据转换副本，单列在配置绑定表的 `auxiliary_config` 中，不算原始配置已找回。原始配置缺口为T04 2,628条、T01 12条；视频及训练资格不受影响。原日志与回执的哈希及来源逐条见 `physedit/checks/CONFIG_SOURCE_TRACE.jsonl.gz`。
