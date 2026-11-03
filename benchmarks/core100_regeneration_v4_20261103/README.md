# Core100 v4：15条独立重生成、重标注任务

名单：`core100-critical-pairs-v4-20261103`。这15条均不得套用旧视频、标签或分数。旧结果保留在原版本。

|案例|原因|主事件|状态|
|---|---|---|---|
|T03_C02|camera_cam03_to_cam02|phone_edge_fall_after_can_contact|待新生成及标注|
|T04_C01|eight_reference_replacements|original_full_chain|待新生成及标注|
|T04_C02|six_reference_replacements|original_full_chain|待新生成及标注|
|T04_C03|eight_reference_replacements|original_full_chain|待新生成及标注|
|T05_C01|eight_reference_replacements|gate_passage|待新生成及标注|
|T05_C03|eight_reference_replacements|gate_passage|待新生成及标注|
|T06_C02|six_reference_replacements|complete_required_contact_chain|待新生成及标注|
|T06_C03|six_reference_replacements|complete_required_contact_chain|待新生成及标注|
|T10_C01|eight_reference_replacements|support_pen_displacement_reaches_source_threshold|待新生成及标注|
|T10_C02|eight_reference_replacements|support_pen_displacement_reaches_source_threshold|待新生成及标注|
|T10_C05|six_reference_replacements|support_pen_displacement_reaches_source_threshold|待新生成及标注|
|T11_C01|eight_reference_replacements|t11_driver_eraser_edge_fall_begins|待新生成及标注|
|T11_C02|eight_reference_replacements|t11_driver_eraser_edge_fall_begins|待新生成及标注|
|T18_C01|six_reference_replacements|upper_nonpulled_book_on_table_at_end|待新生成及标注|
|T18_C02|six_reference_replacements|upper_nonpulled_book_on_table_at_end|待新生成及标注|

每个模型使用同一prompt变体和种子配额。变体1、三个种子时，这15条对应45个生成位置；若三个变体都跑则为135个。
正式Core100评分仍注册全部100条。其余85条仅在视频输入、模型、种子、帧率、观察窗口和prompt完全匹配时才有视频复用的可能；本导出不自动复用它们，也不搬用旧分数。事件定义改变的结果应按新版独立判读。
generation_tasks.jsonl不含事件答案、临界距离或反演真值；annotation_tasks.jsonl不含参考结果标签，待新生成视频绑定哈希后走质量筛查、事件判读和人工复核。
这是任务清单，不是已执行回执。实际模型、输出时长和执行环境仍需登记；不对参考窗口补帧或重定时。
