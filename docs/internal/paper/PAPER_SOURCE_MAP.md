# 论文源码入口与当前审阅范围

用户已确认：之前提供的Overleaf项目是论文主稿。GitHub中的以下文件是可供同步或对照的章节片段，不能替代Overleaf全文。当前只读网络访问尚未取得Overleaf的TeX源码，整篇稿件的审阅仍待源码可读。

主稿入口：[Overleaf 项目](https://www.overleaf.com/8444556745xxbgfcmdfnxx#1a27e4)。主稿身份已由作者确认；链接确认不等于已取得或审阅完整源码。

2026-11-02补查：匿名HTTP可以取得正常分享入口页面；按该页面实际token-access脚本提交链接自带的短校验码、`confirmedByUser=false`后，服务返回200 JSON，但redirect为`/restricted`且包含`anonWriteAccessDenied`。没有取得项目ID或源码ZIP，未执行额外加入确认、登录或受限路径探测。证据保存在`review/cvpr_experiments_20261031/paper_source_http_checks/1793602122811067100_RESULT.json`。这是访问限制，不能据此认定作者主稿不存在。后续仍待可直接审阅的完整源码；不反复要求作者确认主稿身份。

|用途|现行文件|说明|
|---|---|---|
|数据集章节|`docs/internal/paper/dataset_description.tex`|整体benchmark定位、双引擎、固定Core100、输入绑定；发布数量仍需冻结清单支持|
|评测章节|`docs/internal/paper/evaluation_protocol.tex`|分支、临界、事件链、GravTrace；原生观察窗、VLM与人工、覆盖率及统计单位|
|补充参考文献|`docs/internal/paper/cvpr_related_work_addendum.bib`|已有文献片段；不等于完整稿件的全部引用|
|历史数据集草稿|`docs/internal/dataset_description.tex`|保留原文，不作为现行入口；含已停用的80/10/10划分和72,960容量描述|

不要同时插入两个数据集片段：它们重复定义`sec:dataset`，且历史稿的划分已被作者后续决定覆盖。

本轮通过只读Git远端查询取得10个分支的当前head，再按对应Git对象逐棵检查文件树和6份TeX源码。没有发现包含`\documentclass`与`\begin{document}`的LaTeX主文件，也没有发现PDF、DOCX、LTX或明显的论文源码压缩包。GitHub main仍是`e0aa358fe930946e784f605040a0026db39ee2bc`。这一结论只适用于已核查的仓库材料；未据此推断私有Overleaf或同事未同步的稿件不存在。

可复核记录在`review/cvpr_experiments_20261031/PAPER_SOURCE_AUDIT_CURRENT.json`及`PAPER_ALL_BRANCH_TREE_AUDIT.json`。查询未切换分支、合并或提交，也没有覆盖作者原稿。

实验和证据状态以`docs/internal/CVPR_EXPERIMENTS_20261031.md`及其时间戳为准。逐条Core100缺项见`review/cvpr_experiments_20261031/CORE100_CVPR_EVIDENCE_100_20261101.md`。参考准入、区间准入、生成覆盖与已有分数字段分别统计；机器观察不能填作独立人工准确率，排队不能填作生成完成。

整篇稿件尚未完成的审阅包括：主张与所有结果的一致性、主表与补充实验的取舍、完整图表引用、页数和最终编译。这些项目需要完整稿件源码，不能靠当前章节片段宣告通过。
