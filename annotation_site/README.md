# PHY2轻量标注站

## 2026-10-31：人工评测不再等待VLM

人工保存、提交和任务可编辑性统一不依赖VLM是否回传，也不依赖旧任务是否带有`human_annotation_without_vlm`标记。VLM仅作可选参考；后到机器结果只更新机器字段，保留人工标签及状态。已提交锁定、账号权限、媒体/协议核验和明确的annotation_hold仍生效。修复与回归测试见`review/annotation_human_first_20261031/`。

## 2026-10-31：修复服务器隧道直连失败

p25直连标注服务器SSH端口返回Connection refused，导致50999未监听、视频接口503；页面与标注服务正常。已备份并更新p25的`phylabel-media-tunnel.service`，SSH使用已有`~/.ssh/phylabel_proxy.py`通过本机17891代理建立HTTP CONNECT，保留专用受限密钥、主机指纹检查和回环监听。RestartSec改为30秒，避免故障时每5秒重复连接。后续重部署须保留此ProxyCommand，不能直接重跑10月30日的旧隧道安装脚本覆盖配置。

服务已恢复active/running，50999正常监听；f3600_0090、1052、1058、1065公网媒体接口302及CDN Range 206核验通过。0090完整视频读取200，147414字节及SHA256与冻结任务绑定一致。未修改任务、视频绑定或人工标注；测试临时会话已注销。部署备份路径与核验结果见`review/annotation_bugfix_20261031/`。仍依赖p25及其17891代理；本次未进行全部任务浏览器播放验收。

## 2026-10-30：视频通道迁移到服务器常驻服务

本次503来自桌面转发进程退出，页面及标注后端仍在线。
当前媒体代理为标注服务器回环地址 `127.0.0.1:50999`，由 p25 的
`phylabel-media-tunnel.service` 转发到其已有 `127.0.0.1:17891` 代理。
systemd 用户服务已启用、Linger=yes、Restart=always；不再依赖桌面电脑或 `media_tunnel.py`。
专用SSH密钥留在p25，只允许指定端口转发，禁止交互命令；未复制个人私钥。
关闭桌面旧通道后，三条报错视频通过全新固定版本身份校验、65536字节Range读取及公网媒体302验证。
一次主动终止后的服务自动重启验证通过。未改应用、人工标签或任务视频绑定。
仍依赖p25网络及现有代理；不能据此保证上游永久可用。
检查与回滚说明：`review/annotation_bugfix_20261030/REPORT.md`。

## 2026-10-29：视频播放瞬时断线恢复

媒体解析新增有界重试及503临时错误；固定版本/哈希/大小不符仍拒绝。
页面最多自动重连两次，并提供“重试视频”按钮，重连保留表单草稿。
原报错任务及另外两条真实视频已通过302签名与206分段读取核验。
13项回归检查通过；只部署4个应用文件，未修改标注记录。
部署与验证见 `review/annotation_bugfix_20261029/REPORT.md`。
仍依赖已有桌面代理及SSH转发，未重复启动隧道。


## 2026-10-28：任务重分配与线上修复

r01 的240条未开始任务已分别转给 r03、r04、r05 各80条；已提交与草稿未迁移。
概览数量按数据库当前负责人统计，不再用初始520/500配额表示当前任务量。

媒体500错误来自桌面SSH代理退出；已恢复仅监听服务器回环地址的50998转发。
`media_tunnel.py`替代有72小时硬期限的旧助手，断线退避重连；仍依赖桌面网络及7897本地代理。
不要同时启动两个占用同一端口的助手。四条真实媒体已通过固定版本校验和206分段读取。

前端任务加载增加请求序号，快速切换、离开批次后的旧响应不再覆盖当前任务；
等待加载期间产生的编辑必须保存成功才能切换。回归测试：
`node annotation_site/tests/test_task_navigation.cjs`。
本次未修改人工标注协议；旧测试中强制填写时间和证据的断言已对齐现行简化表单。
部署及线上检查记录见`review/annotation_bugfix_20261028/`。

## 最新：已核验 v6 替代视频解除暂缓（2026-10-26）

原暂缓的1,116条中，988条已按原任务、原负责人、原seed和prompt变体绑定HF固定提交`6bcbd71c6a5a6acb05fb360a774f3d2a75056881`中的新版视频，并开放人工标注。当前开放3,472条，剩余128条因缺少对应v6替代视频继续暂缓。旧视频机器预评已失效，新预评pending；人工无需等待VLM。人工记录与独立观察表在事务内核对保持原样，旧任务payload及SQLite已备份。

七位成员新增可标任务分别为142、137、146、140、148、139、136条；当前开放总量分别为500、501、507、505、497、482、480条。原3,600条抽样成员和负责人不变，不将历史标签转移到新版视频。实站七人任务接口及三条新版媒体Range读取核验通过。回执见`review/release_v6_holds_20261026/deployment.json`，操作脚本及核验脚本同目录。下文“2484开放/1116暂缓”是此前状态，由本节覆盖。

## 新增：T17纸巾盒独立平移观察

180条T17正式任务新增“纸巾盒是否发生平移”，不要求罐子先接触，无2厘米阈值。原“接触后平移”及评分协议保留；新标签单独保存，不自动回填。可测记录的原负责人在逐事件页选择后自动保存；旧提交无需解锁即可补填。

管理员概览提供接触×平移四格表、每模型比例及缺失/不可判/不可测/待处理覆盖。final和preliminary分开；分母为0时显示N/A。导出增加box_translation_statistics.json、box_translation_by_model.csv、box_translation_observations.jsonl。技术化“命中分支”的显示名已改为“罐子接触纸巾盒，或纸巾盒末态位移超过2厘米（原判据）”，底层定义/hash不变。实现和上线回执见review/box_motion_observation_20261024/REPORT.md。


## 可测性简化（最新）

可测性表单只选“可测 / 不可测”，不再填写问题类型、时间或原因。新版记录为`measurability-binary-v5`；不可测且未分类时保存`failure=not_specified`，不伪造损坏类型。历史问题类型、原因及历史待定记录保留；新表单不新增待定选项。可测后按原已登记事件继续判读，不可测不提交事件标签。导出`quality_audit.csv`新增`human_measurability`（measurable/unmeasurable/unknown），原列和历史记录保留。31条任务暂缓和人工不等待VLM的阶段规则继续有效。


## 当前标注阶段：排除31条，人工先行（2026-10-23）

用户确认人工标注现在启动，不再等待VLM。formal3600_v1的原3600条登记保留，其中31个Core100任务对应1116条暂缓，其他69个任务对应2484条开放。暂缓任务不出现在普通成员队列，直接访问和提交也受后端限制；管理员可只读查看。

本轮任务：r01 358、r02 364、r03 361、r04 365、r05 349、r06 343、r07 344。原520/500配额作为登记历史保留，不重抽视频、不重新分配人员。

VLM不是人工提交前置条件；已有预评可参考。晚到机器结果只更新机器字段，不覆盖人工标签或提交状态。保存时记录流程和机器可用状态，这不证明标注者看过机器结论，也不宣称独立盲审。原账号、邀请及人工记录保留。

暂缓范围：T04/T06/T09/T11/T13/T16各C01–C05，加T18_C04。等待v6生成替代品后另行核验哈希与任务绑定，再恢复；禁止把旧标签直接套到新视频上。

当前部署及在线接口核对：`review/core100_prompt_hold_20261023/deployment.json`、`verification.json`。下文涉及“必须等VLM”和520/500当前工作量的旧说明是历史规则，由本节覆盖。


入口：https://label.yeegoods.cn/physics/ 。Python 3.10+标准库、SQLite WAL，保留域名根目录原应用。

## 当前协议v2

VLM预评 → 一次人工复核 → 仅争议池随机抽样二审。

- r01–r05个人总配额520，r06–r07总配额500，共3600条；不再全量双审。跨模型混合分配，每模型300、每100个测试样本各3个不同seed/prompt组合。
- VLM原判在人工复核前可见，机器结果不自动变成人类标签，需实际视频证据。method为vlm_assisted_human_review，不称独立盲审金标。
- 无争议提交直接resolved。可测性待定、事件uncertain/not_observed、有效VLM判定与人工相反或主动申请，进入disputed。
- 缺证据/格式错误的机器事件不作为有效冲突判定；机器转人工本身不强制二审，人工可根据画面作明确结论。
- reviewer_id为空，不预分配全量复审。管理员从尚未抽样的争议池均匀随机抽20%（可调、向上取整），自行二审，不增加七人任务。
- 冻结候选池、seed、媒体哈希及抽中ID；旧池不重抽。未抽中的争议继续pending，不记通过或零分；正式报告需列完成数和覆盖率。争议池抽样不代表总体VLM准确率。

## 六条与历史

当前六条Hunyuan/LTX的T15_C03/C04/C05，人员1复核Hunyuan T15_C03，人员3复核其余两条Hunyuan，人员5复核三条LTX。其他人不预分配复审。正式四指标因参考尚未准入保持N/A。

未开始且无人工记录的真实任务升级v2，已有人工记录不覆盖；旧QA双审保持历史版本。七人邀请不重置，QA账号保持禁用。旧QA验收不能证明v2已完成真实人工评测。

最新分工计划：review/label_site_deploy_20261021/random_sampling_plan_single_review_v2.json。基于旧库存快照3503已选、97缺额，不是当前库存，也未导入正式3600条。保留原seed/prompt选择，仅取消预分配复审；补齐库存后冻结完整版本。

## 标注与导出

目标身份、事件定义、观察窗、原生时间和至少8字理由；质量失败至少两证据时间并阻断本目标事件/反演。错误物理本身不算垃圾。未知不填0。

管理员ZIP包含manifest、annotations、reviews、screening、quality_audit.csv、events.csv、all_stage_records、machine_predictions、audit、metrics、checksums和dispute_samples.jsonl。最终标签只含已解决结果；未抽中和未解决争议在manifest及阶段记录中保留。

JSONL采用registration_sample_id（如有），另存site_task_id/batch_id；QA永远用自己的ID。回填冻结run前核对身份与哈希，NearAcc/PairAcc仍需真实边界及配对绑定，不伪造正式分数。

## 本地及正式导入

    python annotation_site/prepare.py pilot --source review/core100_boundary_pilot_20261021 --output review/pilot-package
    python annotation_site/prepare.py init --data-dir annotation_site/data --invitations annotation_site/.private/invitations.json --qa
    python annotation_site/prepare.py import --data-dir annotation_site/data --manifest review/pilot-package/pilot_manifest.json
    python annotation_site/server.py --data-dir annotation_site/data --port 18231 --prefix / --insecure-cookie
    python annotation_site/prepare.py sample --metadata metadata.jsonl --output selection.json --rng-seed 20261022

导入前复制package/media至data/media。正式清单使用review_policy=vlm_human_dispute_only_v2、reviewer_id为空，primary_id按520/500分配，包含VLM原始记录。按SHA256命名上传媒体到/srv/phylabel/data/media，绑定真实登记ID、事件协议及观察窗。正式导入强制12模型各300、同100测试样本各3组合、组合唯一和总配额，拒绝预分配全量复审。

## 运维

phylabel.service监听127.0.0.1:13081，Nginx HTTPS代理/physics/。/srv/phylabel/current指向release，data保存SQLite及媒体，private保存邀请和备份，不公开读取。SQLite用在线backup API备份，不能直接复制正在写入的单个数据库文件。更新保留已有人工记录和旧版本标识。

会话HttpOnly/Secure/SameSite，POST校验Origin+CSRF，媒体Range及导出均需权限。邀请逐人私发。Store.rotate_invite(uid)可重发个人邀请并撤销会话。回滚current指向旧release并重启，数据库与导出版本不可降格混合。


## VLM事件统计与仓库评分器（已接入）

管理页新增VLM事件核验表：原始二分类标签一致率与证据合格统计分开，展示Precision/Recall/F1、微平均、事件宏平均、可判覆盖和样本数。final只含已解决记录；preliminary包含已提交但仍争议的初步判断，避免在统计里隐藏分歧。无人工标签显示N/A，不计零。证据必须绑定视频哈希、实际送入VLM的时间点、登记最少证据数和置信度/矛盾合同。人工可见机器结果，不能写成独立盲审准确率。

临界成绩由scorer_runtime内逐字节复制的仓库评分器计算，SOURCE.json保存源文件哈希和代码版本。网站没有另写一套评分公式。每模型一个完整冻结run；后台计算，自动更新，按模型分表。标签、配置、评分器或媒体文件变化时缓存失效。未完成人工判读的run只保留诊断原始输出，四项正式成绩N/A。只有目标事件的登记不能冒充完整EventExact链条。

### 绑定评分包

1. 先完成科学准入，取得原冻结run：inputs.jsonl、answers.jsonl、registered.json、snapshot_hashes.json、observed_rows.jsonl。不能从网站标签或VLM结果造参考答案。
2. 网站对应任务协议须frozen；按原sample_id、模型、seed、原生时间窗、媒体SHA256及协议SHA256构造task-mapping.json。映射必须覆盖整个冻结run，不能删掉失败或待审任务。
3. 每个mapping对象含task_id、sample_id、video_sha256、protocol_sha256。协议哈希为JSON sort_keys=True、ensure_ascii=False编码UTF8的SHA256。
4. 打包后在管理员“校验并绑定冻结评分包”上传，再点击“计算/更新临界成绩”。

    python annotation_site/scoring_bridge.py --run-dir ORIGINAL_RUN --task-mapping task-mapping.json --output scoring-package.json --scope "已冻结的参考资格子集及排除原因"

如需边界侧文件，加--boundary-bindings FILE；工具按哈希打包原始证据，评分时调用原boundary_binding校验，冻结答案不改写。多个模型可把各run条目合入同一个runs数组；不平均成一个模型成绩。

下载ZIP新增vlm_event_metrics.json/csv、boundary_scoring.json、core100_readiness.json/csv、CORE100_READINESS.md。评分回执包含配置、标注版本和评分器源哈希。对应API均限管理员，普通标注者看不到参考答案或100条的边界登记。

### 固定100条核查

    python annotation_site/audit_core100.py --core ../small_test_selection_20261014/hf_fixed100_publish/core100.jsonl --output review/core100_site_audit_20261022

核对冻结清单SHA256后，精确匹配已列明的本地登记/冻结答案文件和T15状态诊断。12条有匹配登记证据，3条另有T15状态诊断；当前NearAcc与PairAcc准入均0。其他样本或版本存在边界不自动转移到固定100。逐条缺项及候选配对保留；未找到评分登记不等于原始状态不存在。

验收用review/scorer_bridge_qa_20261022为隔离的合成标签，不是六条真实人工观察或模型成绩，禁止导入真实评测。既有七人配额和人工记录不变。


## 正式3600条 HF直链批次

当前 formal3600_v1 已导入；默认进入正式批次。每模型300，r01–r05各520、r06–r07各500。正式媒体使用remote_media固定repository/revision/path/LFS SHA256/size；/media鉴权并验证HF响应后302至临时CDN地址，不保存视频。hf_read_token和vlm_worker_key仅位于服务器data目录权限受限文件中，不进入manifest或导出。

formal_vlm_worker.py在已有GPU上运行，逐条在/dev/shm核验媒体并预评，使用受限/api/worker/result回传机器字段。人工可直接保存和提交，无需等待VLM；网络失败不阻塞人工。T15保留现有五事件合同；其他场景在逐事件合同未登记前只评质量，界面与导出明确标记临界事件待登记。边界、配对和参考缺项仍不报分。

服务器不能直连HF主站；当前签名请求临时借用用户电脑已有代理，经回环SSH转发。仅传小型签名请求，视频由浏览器/GPU直接从HF下载。电脑离线后不能刷新链接；长期使用须改为独立代理。部署/分工/冻结版本见review/formal3600_hf_20261023/DELIVERY.md。
