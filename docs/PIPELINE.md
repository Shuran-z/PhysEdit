# 多机调度

多机调度器按清单分配生成任务，回收视频并执行评测。单机使用[快速上手](phyediting/QUICKSTART.md)中的配置入口。

## 配置

将主机、存储、模型命令和评测任务写入自己的配置文件：

```bash
export PHYSEDIT_FLEET_CONFIG=/path/to/fleet.py
export BENCHMARK=my_benchmark
```

| 配置项 | 内容 |
| :---: | :---: |
| `SITES` | 文件系统、解释器与权重路径 |
| `HOSTS` | SSH别名与GPU设备 |
| `MODELS` | 采样参数与生成命令 |
| `BENCHMARKS` | 输入清单、评测步骤与汇总命令 |

`BENCHMARK`对应配置中的任务键。部署配置和日志保存于本地。

## 检查与运行

```bash
physedit status "$BENCHMARK" --models all
physedit run "$BENCHMARK" --models all --dry-run
physedit run "$BENCHMARK" --models ltx_i2v,cosmos3_nano
```

调度器检查设备和已有任务，建立分工清单，执行生成并回收结果。视频检查尺寸、帧数、时钟和完整解码；共享存储直接读取，独立存储通过调度主机回收。

## 任务目录

```text
<root>/tools/                     生成脚本
<root>/<benchmark>/input/         条件图、提示与清单
<root>/<benchmark>/<run>/<model>/  视频、清单与日志
<home>/<benchmark>/eval/          评测结果
```

命令模板支持`{manifest}`、`{dir}`、`{tools}`、`{gpu}`、`{run}`和`{worker}`。任务状态与逐例原因保存在对应目录。

<details>
<summary>持续调度与试运行</summary>

```bash
physedit run "$BENCHMARK" --models all --watch 10
physedit run "$BENCHMARK" --models ltx_i2v --limit 4
```

`--watch`按分钟重复调度，`--limit`建立独立试运行目录，`--tag`指定名称。worker异常按配置的重启上限处理，`--retry`用于显式恢复。

</details>
