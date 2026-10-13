# 多机调度

PhysEdit的多机调度器按输入清单分配生成任务，回收视频并执行评测。单机流水线见[快速上手](phyediting/QUICKSTART.md)。多机环境通过独立配置指定任务、主机与共享存储。

## 私有部署配置

公开配置使用通用路径，默认远程主机列表为空。将自己的`SITES`、`HOSTS`、`MODELS`和`BENCHMARKS`保存在仓库外的Python文件，通过环境变量加载：

```bash
export PHYSEDIT_FLEET_CONFIG=/absolute/path/private_fleet.py
export BENCHMARK=my_benchmark
python -m physedit status "$BENCHMARK" --models all
python -m physedit run "$BENCHMARK" --models all --dry-run
```

`BENCHMARK`对应私有配置中`BENCHMARKS`的任务键。配置中的主机名称使用自己的SSH别名；共享存储、解释器、权重与评测路径由部署环境提供。配置文件和运行日志保存在本地。

## 执行

```bash
python -m physedit run "$BENCHMARK" --models ltx_i2v,cosmos3_nano
python -m physedit run "$BENCHMARK" --models all --watch 10
python -m physedit run "$BENCHMARK" --models ltx_i2v --limit 4
```

调度器检查GPU和已有任务，准备输入与互斥worker清单，执行生成，再将结果回收到评测主机。媒体通过完整解码、尺寸、帧数、时钟和完成记录校验后发布。共享文件系统可直接读取产物，其他站点通过调度主机回收。

该入口按部署配置管理空闲显存阈值和设备列表。worker异常由调度器的重启限制处理；达到限制后记录状态，`--retry`可显式恢复。单机PhyEditing使用独立运行目录和显式执行，不使用这套重启策略。

## 目录与字段

```text
<root>/tools/                         runner与构建脚本
<root>/<benchmark>/input/             条件图、提示与输入清单
<root>/<benchmark>/<run>/<model>/      manifest、generated、logs
<home-root>/<benchmark>/eval/          逐阶段结果与汇总
```

`SITES`描述文件系统、路径与环境；`HOSTS`描述SSH别名及设备；`MODELS`描述采样参数和runner命令；`BENCHMARKS`描述清单、输入、评测依赖及汇总命令。命令模板中的`{manifest}`、`{dir}`、`{tools}`、`{gpu}`、`{run}`和`{worker}`由调度器填写。

`--limit`自动建立单独试运行命名空间；`--tag`可显式命名。已有产物保持原采样配置，参数变化使用新命名空间。实际状态和逐例原因以运行目录为准。
