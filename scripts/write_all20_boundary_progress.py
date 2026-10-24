"""Write evidence-tiered progress; configuration retrieval is not threshold completion."""
import csv,json
from pathlib import Path
from datetime import date
OUT=Path('review/scene_family_completion_20261018')
NOTES={
'T01':('A斜面/书面摩擦；B罐间距；C链条摩擦','540条反事实参数匹配原合同，原中心距离已保存','核对媒体身份及原标定目标事件；C保留非单调记录'),
'T02':('A横向命中位置；B撞击初速；C探针初速','880条发布配置与45份原运行metadata物理上下文匹配；15个族×重力组的事件转变区间已接入距离登记','870条真实状态完成数值真值核验，63条near；已目视15条，渲染上下文及遮挡对应待核对；10条状态仍缺'),
'T03':('原A/B/C三族，r014与r032/r034分别处理','原任务矩阵及早期因果审计已找回','155条后修复配置已全部回收，474/474配置齐全；修订后的边界尚需逐族核对'),
'T04':('support_release；stack_sliding；terminal_transfer','原正式构建器已恢复：support_release=抽取速度、stack_sliding=书/坡面摩擦、terminal_transfer=杯位置；按实际物理字段校验','发布旁文件持续恢复；原star是设计值，不能替代三族各自的事件边界求解'),
'T05':('motion_activation；gate_passage；terminal_transfer','880条配置；正式构建器的motion_activation=初速、gate_passage=间隙比、terminal_transfer=导轨摩擦已核对','105条配置含contact_stability_fix，实际间隙与原设计不同；已分别记录请求值/有效值/修复版本，须按修复后固定上下文求界'),
'T06':('impact_force；gap','正式发布配置已按固定revision回收；bg01/地球原后端端点复算完成','按实际连续施力参数分族，不能把文件名J当冲量；数值搜索待接'),
'T07':('A_surface_friction；B_initial_longitudinal_position_m；C_ramp_angle_deg','880条配置；找回旧五重力和后续细扫描报告','重建出现yaw/offset另一套族；须核对当前发布采用的版本'),
'T08':('A初速；B碰撞偏心；C杯体总质量','880条配置；旧标定与V4/V6来源已定位','872条存在多个配置候选，须判定是否仅渲染变化并核对边界目标'),
'T09':('pull_force；layer_friction','正式发布配置已按固定revision回收；bg01/地球原后端端点复算完成','按实际抽取力分族，不沿用pull=抽取距离的假设；数值搜索待接'),
'T10':('v_roll；support_x','10点原后端复算完成；支撑笔位移4cm事件区间：support_x=[.1779,.217]m、v_roll=[1.7428571,2.3142857]m/s；已接距离','这是支撑笔位移事件，不等同文件夹失去支撑；其余背景/重力未外推'),
'T11':('原四族：速度、接力间距、边缘距离、接力质量','240条历史发布配置；补找回r010四结局验收报告','r011速度名字段对应零初速+分段外力，需恢复实际控制映射'),
'T12':('速度×摩擦×目标质量联合网格，按实际重力分层','正式发布配置已按固定revision回收','不能虚构A/B/C；需在固定其他参数的切片内建立边界'),
'T13':('旧冻结校准来源与Isaac r4重建分别登记','旧构建器有44条校准来源；新版r4来源路径已知','历史冻结清单未收录；新版发布身份及临界任务仍待逐条核对'),
'T14':('A通道宽度；B偏航；C冲量（以实际质量换算）','880条三机位媒体哈希匹配；bg03/地球A族正式后端两端点补验成功，区间[.018,.019]m','原标定timeconst=.005，正式=.001；其余背景/重力及B/C仍需同配置验证'),
'T15':('A_force_transfer；B_support_loss；C_floor_target','恢复60原族条件组；原后端补算152次；4条H3已绑定区间并重评分','本次补算仅bg01/地球；A多转变，B/C已细化，其余上下文未补齐'),
'T16':('Genesis接触位置/支撑角；Isaac d1/d2/d3','Genesis1196条配置候选；Isaac原8组/72条搜索与交付哈希匹配，已登记区间距离','原Isaac d2 72条cam01画面核验后已接入NearAcc答案；Genesis及修复版本仍待核对'),
'T17':('Genesis初速/横向偏移；Isaac d1/d2/d3','Genesis1079条配置候选；Isaac修复版30条配置/QA哈希与原生产记录匹配，已登记修复搜索区间','原Isaac60组未找到转变，不代表后修复版本仍如此；需重查/补搜'),
'T18':('Genesis摩擦/重叠长度；Isaac d1/d2/d3','Genesis630条配置候选；Isaac修复版10条配置/QA哈希匹配并登记搜索区间','原搜索未通过组需按当前抽取/传播事件重核，不直接拼接旧新参数'),
'T19':('Genesis偏心/质量比/恢复系数；Isaac d1/d2/d3','Genesis712条配置候选；Isaac原32组/288条搜索记录已找回，但旧渲染已停用','旧288条因用户确认画面不合格标记retired_render，不进入正式评测；等待正在重渲染的新版本，再重新绑定及审核'),
'T20':('Genesis三段间隙、书初速、杯边距；Isaac d1/d2/d3','Genesis1190条配置候选；Isaac原28组252条输入哈希匹配，已接入原搜索区间距离，单列于旧库存之外','原Isaac记录与当前发布/新划分分开；Genesis数值边界尚未绑定')}
def write_historical_progress():
 measured_path=OUT/'t04_measured_published_events.json'
 if measured_path.exists():
  measured=json.loads(measured_path.read_text(encoding='utf-8'))
  transition_path=OUT/'t04_transition_candidates.json'
  transitions=[t for r in json.loads(transition_path.read_text()) for t in r['transitions']] if transition_path.exists() else []
  NOTES['T04']=(NOTES['T04'][0],f"原三族定义已核对；{len(measured)}条发布状态已提取事件；{sum(t.get('fixed_context_matches',False) for t in transitions)}个相邻异侧区间通过固定物理上下文检查；bg01/月球4点原后端复算完成；两端事件与发布一致；局部区间[0.1225,0.13125]已绑定3条原视频及分桶",'其余上下文/参数族补算、边界重复核验和画面审核未完成；不把观测区间称为精确临界点')
 NOTES['T07']=(NOTES['T07'][0],'880条配置；已从原audit_t07_motion恢复最大位移≥1cm规则，并在同版本发布状态试跑','批量状态核验、原三族边界及画面审核未完成')
 NOTES['T08']=(NOTES['T08'][0],'880条配置；已从原V4审计器恢复三物体下落/接触规则并在发布状态试跑，落地与离桌分开','批量状态、参数族边界、版本和画面审核未完成；不将8cm下落阈值冒充支撑失效瞬间')
 NOTES['T05']=(NOTES['T05'][0],'880条配置已核对；105条物理配置偏离原构建器，其中54条有显式修复记录、51条无标记；都已要求独立求界','继续恢复发布状态和原族目标；检查实际固定上下文，不仅依据修复标记配对')
 NOTES['T12']=(NOTES['T12'][0],'880条发布配置恢复出实际联合参数切片：速度260、摩擦268、目标质量228个多值切片','这些多值切片均包含不同随机种子；事件核验与固定上下文搜索未完成，不能直接当作单个确定性边界')
 progress=json.loads((OUT/'all20_progress.json').read_text(encoding='utf-8'))
 rows=[]
 for p in progress:
  family,done,next_step=NOTES[p['scene_id']]
  rows.append(dict(scene=p['scene_id'],original_families=family,
   historical_genesis_config_candidates=p['genesis_config_candidates'],historical_genesis_inventory=p['genesis_inventory'],
   recovered_evidence=done,remaining=next_step,all_families_completed=False,completion_status='未完成（全场景全部参数族）'))
 (OUT/'all20_evidence_progress.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 with (OUT/'all20_evidence_progress.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 lines=['# T01–T20 原参数族临界搜索与发布绑定进度（2026-10-18）','',
 '**这是完整20场景的进度表，不是“20场景已经全部完成”的声明。** 本轮实际补算覆盖T15的bg01/地球条件、T14的bg03/地球A族两端点，以及T06/T09/T10的bg01/地球六轴12端点和T10两轴6个中间点。其余未闭环任务保留，不把未找到写成从未搜索。',
 '', '配置计数来自冻结历史发布清单（dataset_splits_v2），用于身份匹配，不替代joint_split_v3划分，也不代表所有新版Isaac库存。配置候选数不等于质量通过数，更不等于可评分临界距离数。T13的0表示此历史清单未收录。', '',
 '|场景|完成状态|按原参数族|Genesis配置候选/历史轨迹|已完成证据|剩余事项|','|---|---|---|---:|---|---|']
 for r in rows:lines.append(f"|{r['scene']}|{r['completion_status']}|{r['original_families']}|{r['historical_genesis_config_candidates']}/{r['historical_genesis_inventory']}|{r['recovered_evidence']}|{r['remaining']}|")
 lines+=['','“未完成”针对全场景全部版本/参数族的任务范围；T16 Isaac d2 的72条参考准入子任务已经完成。没有把局部完成冒充全场景完成。']
 ledger=json.loads((OUT/'nearacc_readiness_summary.json').read_text(encoding='utf-8'))
 lines+=['','## 可评分登记计数','',f"历史轨迹登记{ledger['total_historical_trajectories']}条；已接入事件区间距离{ledger['measured_interval_distance_registered']}条（T02 880、T04补算绑定3、T10补算10、Isaac原版T16 72/T19 288、修复版T17 30/T18 10/T19 19、T14 2；另有旧库存之外T20原来源252条）。正式NearAcc参考登记{ledger['completed_formal_near_reference_registrations']}条：目前事件真值/发布身份、边界确认或归一化登记尚未全部闭环。这是管线完成数，不是数据可用性的否定。每条阻塞原因见nearacc_readiness_ledger.jsonl。",'', f"数值真值、版本和归一化已核验{ledger['numerical_reference_verified']}条，其中near桶确定{ledger['near_numerical_eligible']}条。数值资格与参考RGB观察资格分开，尚未完成后者的记录不自动进入正式生成评测。candidate_reference_answers.jsonl保留答案和逐条待办；admitted_near_reference_answers.jsonl只导出完成准入的记录。", '', '## 已实际接入评分','',
 'T15：`h3_supplemental_bindings.json`通过参考state哈希、固定物理上下文、目标事件和参数值核对，把4条H3输出接入已有`--boundary-bindings`接口。`h3_supplemental_refined_score.json`为最新实际评分结果（旧score为细化前快照）。新计算的是观测转变区间距离；保留多次翻转，不伪装唯一精确阈值。',
 '', 'T14：`t14_formal_probe_distance_registry.json`保存两条正式配置复算记录，经过现有distance函数实际计算区间距离。原renderer在p25/p26的SHA256一致，配置哈希与发布核验记录一致；只降低渲染分辨率并停用视频输出，保留正式物理设置和7秒观测时长。两条分别为two_sided_wedge与passed_and_hit_eraser，确认该条件下[.018,.019]m仍跨越passed_channel事件。不外推所有族；未生成新的模型输出，尚无T14模型分数。',
 '', '原合同中心点距离（T01/T02）、原搜索区间距离（T14）、本轮原后端补算区间（T15）分开保存；前两类尚待上述闭环，不能因为字段有数字就自动进入NearAcc。',
 '', '## T15 补算范围与结果','',
 '沿用V11原Genesis脚本及其原配置：float64、每视频帧128求解步、dt=1/3840、timeconst=.002、box检测、1秒settle。28次粗扫+70次扩展重复+54次细化=152次，143次通过原QA。失败记录全部保存。重复使用原确定性设置，不能替代跨求解精度收敛实验。',
 '', '- A初速：细扫中[2.142,2.151] m/s为跌落→不跌落，[2.151,2.160] m/s为不跌落→跌落；另有QA失败点阻断相邻区间恢复。不能声称只存在一个阈值。',
 '- B支撑参数：跌落→不跌落区间[0.103125,0.1075] m；该轮每点两次，18/18通过原QA。',
 '- C手机声明扫描坐标：未命中→命中区间[-0.125,-0.1140625] m，命中→未命中区间[0.165,0.175] m；36/36通过原QA。该坐标与实际手机世界坐标的仿射对应已核对，不能混写。',
 '', '这些是该背景/重力/其余固定参数下的数值转变区间，不外推至全部60组。未改变现有视频或删除两侧样本。',
 '', '## 本轮核验','', '已回收原报告/脚本1171份，另扩展报告树348份（214份此前未读取）；配置文件按来源保留路径和哈希。T14进一步读取192份实际标定配置，确认接触时间常数与正式版本不同。',
 '', '边界恢复、绑定、评分及参考准入共40项unittest通过。H3继续使用已有开发标注，没有新增独立人工标签或生成模型实验。']
 (OUT/'ALL20_PROGRESS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print('wrote all20 evidence progress: 20 rows')
def main():
 ledger=OUT/'original_value_distance_ledger/combined_all20_summary.json'
 if not ledger.exists():return write_historical_progress()
 combined=json.loads(ledger.read_text(encoding='utf-8'))
 def load(name):
  p=OUT/name
  return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
 snapshot=load('LATEST_EXECUTION_STATUS_20261019.json')
 additional={r['scene']:r for r in snapshot.get('additional_numerical_jobs',[])}
 t15_refined=max(additional.get('T15_refined',{}).get('statuses',{}).get('refined_local_interval',0),additional.get('T15_event_tail_refinement',{}).get('statuses',{}).get('refined_local_interval',0))
 metadata=load('t16_t20_contact_summary_20261020.json')
 t09=load('original_value_distance_ledger/t09_table_contact_refinement_summary.json')
 t09_pull=load('original_value_distance_ledger/t09_pull_refinement_summary.json')
 t12=load('original_value_distance_ledger/t12_refinement_binding_summary.json')
 t12_remaining=load('t12_remaining_grid_summary_20261022.json')
 t13=load('t13_current_solver_binding_summary.json')
 t13_seeded=load('t13_seeded_supplement_summary_20261021.json')
 t07_B=load('t07_B_E4_preparation_summary_20261022.json')
 t07_B_refined=load('t07_B_E4_refinement_summary_20261022.json')
 t18=load('t18_table_contact_preparation_summary_20261020.json')
 search18=load('t18_event_distance_summary_20261020.json')
 supplemental=load('supplemental_scan_state_summary_20261020.json')
 replay_scans=load('t06_t10_replay_distance_summary_20261020.json')
 t03=load('original_value_distance_ledger/t03_binding_summary.json')
 t14=load('t14_all_context_distance_summary_20261020.json')
 t14_complete=t14.get('planned_contexts')==180 and t14.get('completed_contexts')==180 and t14.get('failed_contexts')==0
 t02=load('t02_published_scoring_registry.json')
 t02_complete=isinstance(t02,list) and len(t02)==880 and all(r.get('numerical_reference_verified') and r.get('mapping_status')=='matched' and r.get('boundary',{}).get('status')=='verified' for r in t02)
 overrides={
  'T09':(f"真实末帧触桌事件：580条原状态；摩擦轴细化{t09.get('refined_intervals',0)}/12，抽取力轴细化{t09_pull.get('refined_intervals',0)}/{t09_pull.get('planned',8)}；两轴距离均已接入",f"缺失300条pull状态已回收{supplemental.get('completed_states',{}).get('T09',0)}/300；抽取力待完成{t09_pull.get('pending',0)}项、失败{t09_pull.get('failed',0)}项；补算来源单列，下沉代理不计事件边界；无观测翻转的上下文保留原记录"),
  'T12':(f"新版880条配置与状态对应；已细化{t12.get('refined_intervals',0)}/76个已识别切片区间；原后端副本与各主机执行环境分别登记",'已登记的76项求解已结束；其余联合参数切片的边界覆盖尚未闭环，不能表述为仍在运行；两侧样本保留'),
  'T13':(f"原发布147个异侧区间均已接回；已细化{t13.get('completed_refined_intervals',0)}/147；740条不同参考样本有区间；seed0补充扫描{t13_seeded.get('completed_jobs',0)}/8，另存{t13_seeded.get('local_intervals',0)}个条件区间",f"原8项端点未复现：原初始化seed=None，复跑标签存在差异；保留原发布区间。两项seed0完整网格完成{t13_seeded.get('full_grid_completed_jobs',0)}/{t13_seeded.get('full_grid_planned_jobs',2)}；新种子结果不覆盖原发布真值"),
  'T14':(f"旧正式版已完成{t14.get('completed_contexts',0)}/180组；{t14.get('bound_distinct_samples',0)}条不同参考样本已接细化距离",f"选定180组任务已全部结束，失败{t14.get('failed_contexts',0)}项；其中{t14.get('contexts_without_observed_flip',0)}组三点内未观测翻转，保留样本且不捏造边界；T14S另列"),
  'T15':('原范围60组与扩展40组已扫描；原发布反事实参数对应和原范围归一化已接入',f"79个已观测局部区间已细化{t15_refined}个、剩余{79-t15_refined}个；尾部未静止任务已运行，余下原审计失败项继续定位，出界等错误原样保留"),
  'T18':(f"630份Genesis发布metadata已对应；567条多书原配置/事件已恢复，567套原干预配方全部精确重建；新搜索已完成{search18.get('completed_contexts',0)}/567",f"旧显存不足错误跳过的200项已修复等待逻辑并置于队列前部，已完成{search18.get('resource_recovery_cohort',{}).get('completed',0)}/200；总待算{search18.get('pending_contexts',0)}、实际失败{search18.get('failed_contexts',0)}。按原版本/拓扑/种子分别求界，旧两书版及Isaac另列"),
  'T19':('旧渲染按用户要求停用；不计当前可用距离参考','等待新T19完成渲染并交付/发布；已知旧文件不能重新启用')}
 for scene in ['T16','T17','T20']:
  overrides[scene]=(f"Genesis发布metadata已全部逐字节对应：{metadata.get('verified_metadata',{}).get(scene,0)}条；原参数扫描已登记{metadata.get('unique_bound_samples',{}).get(scene,0)}条不同样本的接触事件区间",'保留各原参数轴和修复版本；已有扫描区间与精确原求解值分列，其余命名事件/上下文继续处理')
 overrides['T07']=(f"A摩擦和C坡角120个原条件组已完成；360条分支已接距离；B采用用户确认E4桌面接触，{t07_B.get('reference_videos',0)}条真值已绑定，{t07_B.get('bound_distinct_samples',0)}条有原区间距离",f"B原60组三点中{t07_B.get('contexts_without_observed_flip',0)}组未观测到E4翻转，均保留；已观测{t07_B.get('original_intervals',0)}组区间，细化成功{t07_B_refined.get('refined',0)}、端点复现失败{t07_B_refined.get('failed',0)}；原0.16–0.22m区间不因复跑失败删除")
 if (OUT/'t12_remaining_grid_launch_20261022.json').exists():
  done,_=overrides['T12']
  queue_count=len(load('t12_remaining_grid_launch_20261022.json'))
  overrides['T12']=(done,f"剩余1572个原单点/无翻转切片已启动{queue_count}路全发布取值网格补算；完成{t12_remaining.get('completed',0)}、失败{t12_remaining.get('failed',0)}、待算{t12_remaining.get('pending',1572)}。新补算单列，不覆盖原标签，归一化使用本批实际完整发布轴范围")
 overrides['T03']=(f"880份选定原状态均已回收；{t03.get('recovered_state_bindings',0)}条已绑定状态身份及实际求解设置；{t03.get('normalized_interval_records',0)}条原事件区间记录已补齐归一化",'原报告中的64个相邻事件区间保留；其余原参数族和没有观测翻转的上下文继续处理，不把渲染star当求解边界')
 preparation=load('conditional_family_preparation_summary_20261023.json')
 conditional=load('conditional_family_progress_20261023.json')
 scans=load('remaining_family_scan_summary_20261023.json')
 if preparation:
  done,left=overrides['T03']
  overrides['T03']=(done+f"；A/B/C共{preparation.get('by_scene',{}).get('T03',0)}个上下文已备齐补算输入，包括15个r035修复配置，按发布状态恢复步长和子步数",
   left+f"；输入准备未完成{preparation.get('pending',0)}项；实际补算状态见conditional_family_progress_20261023.json，任务登记不算求解完成")
 if scans:
  for scene in ['T16','T17','T20']:
   done,left=overrides[scene]
   overrides[scene]=(done+f"；原族扫描覆盖{scans.get('contexts',{}).get(scene,0)}个上下文、{scans.get('intervals',{}).get(scene,0)}个局部事件区间，完整链的逐段接触单列",
    left+'；固定来源种子的补算已接入回收流程；旧library_shelf_v1.json缺失的上下文保留失败记录，不能用新版背景替代')
  restoration=load('original_library_background_restore_20261023.json')
  if restoration:
   for scene in ['T16','T17','T20']:
    done,left=overrides[scene]
    overrides[scene]=(done+'；已由原v1生成器恢复书架网格，SHA256与历史配置一致',
     left.replace('旧library_shelf_v1.json缺失的上下文保留失败记录，不能用新版背景替代','旧背景已重建到独立目录，45个受影响上下文单独重试；原失败记录保留，不与旧运行混记'))
 failure18=load('t18_failure_diagnostics_20261023.json')
 if failure18:
  done,left=overrides['T18'];diagnosis=failure18['summary']
  overrides['T18']=(done,left+f"；已诊断{diagnosis.get('examined',0)}项失败；原720p光追对照{len(failure18.get('controls',[]))}次仍未复现，不能归因于低清数值渲染；底层执行/资产差异尚未唯一定位")
 five=load('five_scene_refinement_summary_20261020.json')
 for scene,values in five.get('scenes',{}).items():
  overrides[scene]=(f"原发布异侧区间任务{values.get('planned',0)}项；已接入原后端细化区间{values.get('refined_local_interval',0)}项",
   f"待运行{values.get('pending',0)}项；端点未复现或执行失败{values.get('failed',0)}项保留原区间及两侧样本，继续诊断；固定来源种子的条件边界单独标记")
 if 'T11' in overrides:
  done,left=overrides['T11'];audit=load('t11_failed_endpoint_audit_summary_20261021.json')
  overrides['T11']=(done,left+f"；已核查{audit.get('compared_endpoints',0)}个端点，{audit.get('changed_event_labels',0)}个结果改变，配置匹配，接触后轨迹/触发施力存在差异")
  original_runtime=load('t11_original_runtime_endpoint_audit_20261023.json')
  if original_runtime:
   done,left=overrides['T11']
   overrides['T11']=(done,left+f"；新增原p29运行时复核{len(original_runtime)}个端点，{sum(r['original_label']!=r['replay_label'] for r in original_runtime)}个结果变化，动态物体和物理场景配置匹配")
 source_searches=load('five_scene_conditional_source_preparation_20261023.json')
 if source_searches:
  for scene,count in source_searches['by_scene'].items():
   done,left=overrides[scene]
   overrides[scene]=(done+f"；新增{count}个端点来源配置的原种子条件搜索已启动",
    left+'；新搜索覆盖原发布轴范围，不强迫另一个种子的端点复现原标签；每个来源仍须先复现自身事件，结果自动绑定且保留原区间')
 shifted=load('t13_conditional_boundary_shift_20261024.json')
 if shifted:
  done,left=overrides['T13'];s=shifted['summary']
  overrides['T13']=(done,left+f"；逐项比较发现{s['outside_original_interval']}/8个新seed0转变区间在原区间之外，{s['overlap_or_touch']}/8个仍重叠或相接；不能据此断言唯一根因")
 for scene,count in [('T06',600),('T10',880)]:
  item=next(r for r in combined['scenes'] if r['scene_id']==scene)
  gpu=1 if scene=='T10' and (OUT/'t10_parallel_state_replay_launch_20261020.json').exists() else 4
  completed=supplemental.get('completed_states',{}).get(scene,0)
  state='此批状态补算已完成' if completed>=count else f'GPU{gpu}继续补算剩余{count-completed}条'
  overrides[scene]=(f"已登记{item['unique_samples_with_numerical_reference']}条不同参考样本的原值/补算区间；新补算事件区间已绑定{replay_scans.get('bound_distinct_samples',{}).get(scene,0)}条不同样本",f"缺失状态补算{completed}/{count}条；{state}；原参考视频及补算来源分别记录")
 if t02_complete:overrides['T02']=('选定发布880/880条的三参数族、事件真值、版本、边界区间及归一化已完成数值对应','此选定版本的数值对应已完成；参考画面准入与模型评分单列')
 remaining={
  'T01':'继续核对其余原任务及其明确目标事件，保留C族非单调转变记录',
  'T03':'按当前发布的三个原参数族补齐剩余固定物理上下文的边界',
  'T04':'补齐其余support_release、stack_sliding、terminal_transfer上下文；渲染star另列',
  'T05':'分别补齐原版及105条物理修复配置所属的条件边界',
  'T06':'按impact_force和gap补齐其余背景/重力条件的原值或求解区间',
  'T08':'按初速、偏心、质量三族继续处理原版及修复后的物理上下文',
  'T10':'补齐余下两轴上下文；4cm运动事件不改称支撑失效',
  'T11':'按实际四族核对新版驱动及其边界，接力质量族不遗漏',
  'T14':'已选旧笔穿通道正式版；180组原任务继续求解，T14S另列',
  'T15':'原范围60组及扩展40组已扫描；保留未细化原区间，8个原审计失败区间另记'}
 rows=[]
 for item in combined['scenes']:
  scene=item['scene_id'];family,old_done,old_next=NOTES[scene]
  if scene=='T13':family='当前发布：桌缘距离；书簇位移；驱动枢轴间隙'
  done,next_step=overrides.get(scene,(old_done,remaining.get(scene,old_next)))
  if scene not in overrides:done=f"已登记{item['unique_samples_with_numerical_reference']}条不同参考样本的原值/补算区间；其余来源继续恢复"
  rows.append(dict(scene=scene,original_families=family,recovered_evidence=done,remaining=next_step,
   numerical_reference_samples=0 if item['retired'] else item['unique_samples_with_numerical_reference'],
   retired_historical_samples=item['unique_samples_with_numerical_reference'] if item['retired'] else 0,
   publication_metadata_mapping_completed=scene in ['T16','T17','T18','T20'],
   all_families_completed=(scene=='T02' and t02_complete) or (scene=='T14' and t14_complete),
   completion_status='数值对应完成' if scene=='T02' and t02_complete else '选定180组任务完成' if scene=='T14' and t14_complete else '等待新渲染' if scene=='T19' else '仍有未完成任务'))
 (OUT/'all20_evidence_progress.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 with (OUT/'all20_evidence_progress.csv').open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
 target=OUT/'ALL20_PROGRESS.md';historical=OUT/'ALL20_PROGRESS_20261018_HISTORICAL.md'
 if target.exists() and not historical.exists():historical.write_text(target.read_text(encoding='utf-8'),encoding='utf-8')
 lines=['# T01–T20 临界搜索与发布参数对应：'+date.today().isoformat(),'',
  '此表只报告原值恢复、参数/版本对应、数值求解和距离接入。视频质量准入与生成模型打分另行统计，不作为找回临界值的额外门槛。',
  '', '| 场景 | 原参数族 | 当前有数值参考的不同样本 | 已完成事项 | 未完成事项 |', '|---|---|---:|---|---|']
 for r in rows:lines.append(f"|{r['scene']}|{r['original_families']}|{r['numerical_reference_samples']}|{r['recovered_evidence']}|{r['remaining']}|")
 lines+=['',f"当前活动版本共有{sum(r['numerical_reference_samples'] for r in rows)}条不同样本有数值参考。各场景按引擎、版本和样本ID去重；一个样本可能含多个事件或局部区间，不能累加记录行数当视频数量。原渲染star和T09旧下沉代理均不计入此数。",'',
  '原参数网格没有观测到事件翻转时记录无已观测边界，不捏造阈值，不删除原参考视频。不同物理结构不能仅按相邻参数编号配对。', '',
  '运行中的求解详见LATEST_EXECUTION_STATUS_20261019.json（文件名保留历史命名，内部date为当前快照日期）。数值参考数量不是生成模型NearAcc分数。']
 target.write_text('\n'.join(lines)+'\n',encoding='utf-8');print('wrote current all20 search progress: 20 rows')


if __name__=='__main__':main()
