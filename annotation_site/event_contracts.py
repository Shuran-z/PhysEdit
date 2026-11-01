"""Versioned, source-linked observation contracts for the fixed Core100.

These definitions register what annotators observe. They do not grant reference,
boundary, calibration, time-alignment, or cross-boundary-pair admission.
"""
import copy
import hashlib
import json
from pathlib import Path

VERSION='core100-events-v2.0'
COMMON_ZH=('逐项记录实际画面，不按提示词猜结局，也不为满足预期顺序修改标签。'
 '接触须有可确认的几何/运动证据，像素重叠或靠近不够。发生填首次可确认时间；'
 '未发生须看完整观察窗，至少两个证据时间；遮挡、出画、身份不清填不可判/未观察到。'
 '末态事件只判断观察窗末帧，不能用曾经发生代替。数值阈值需定量测量与标定依据，不能把像素当米。'
 '生成窗口标签不自动等于原参考全长标签；时域、参考、边界和配对准入另查。')

SOURCES={
 'T01':['review/scene_family_completion_20261018/t01_current_sources/audit_t01_v2.py'],
 'T02':['review/scene_family_completion_20261018/t02_original_auditor/audit_t02_v2_causal_gate.py'],
 'T03':['review/annotation_event_contracts_20261023/merged_source_headers.json'],
 'T04':['scripts/five_scene_boundary_rules.py','review/scene_family_completion_20261018/original_completion_sources/audit_t04_v3.py'],
 'T05':['scripts/five_scene_boundary_rules.py','review/scene_family_completion_20261018/original_completion_sources/audit_t05_v2.py'],
 'T06':['scripts/supplement_t06_published_boundaries.py'],
 'T07':['docs/critical_boundary/T07_B_E4_CONTRACT.json','review/scene_family_completion_20261018/original_completion_sources/audit_t07_motion.py'],
 'T08':['scripts/five_scene_boundary_rules.py','review/scene_family_completion_20261018/original_completion_sources/build_t08_v4_formal_480p.py'],
 'T09':['docs/critical_boundary/T09_COLLAPSE_THRESHOLD.md','scripts/register_t09_table_contact_events.py'],
 'T10':['scripts/register_t06_t10_replay_distances.py'],
 'T11':['scripts/five_scene_boundary_rules.py','review/annotation_event_contracts_20261023/sources/0551ceeb1b_analyze_t11_r009_event_chain_probes.py'],
 'T12':['review/annotation_event_contracts_20261023/sources/t12_r002_formal_contract.json','review/annotation_event_contracts_20261023/exact_core_configs.json','scripts/supplement_t12_published_boundaries.py'],
 'T13':['review/annotation_event_contracts_20261023/sources/1133943c7f_build_t13_frozen_formal_v3.py','scripts/t13_current_boundary_worker.py'],
 'T14':['review/scene_family_completion_20261018/t14_analyzer_source.py'],
 'T16':['review/annotation_event_contracts_20261023/sources/ebc5c53c30_build_project.py','scripts/collect_t16_t20_published_events.py'],
 'T17':['review/annotation_event_contracts_20261023/sources/ebc5c53c30_build_project.py','scripts/collect_t16_t20_published_events.py'],
 'T18':['docs/critical_boundary/T18_TABLE_CONTACT_PROTOCOL.md','review/annotation_event_contracts_20261023/sources/ebc5c53c30_build_project.py'],
 'T19':['review/annotation_event_contracts_20261023/sources/ebc5c53c30_build_project.py'],
 'T20':['review/annotation_event_contracts_20261023/sources/ebc5c53c30_build_project.py','scripts/collect_t16_t20_published_events.py'],
}


def e(name,zh,en,actors=(),*,role='chain',minimum=1,final=False,rule=None,group=None,derived=None,notes=''):
    result={'name':zh,'definition':en,'definition_zh':notes or zh+'。'+COMMON_ZH,
      'minimum_evidence_times':minimum,'applicable':True,'actors':list(actors),'role':role,
      'time_semantics':'window_end_state' if final else 'first_confirmed_occurrence'}
    if rule:result.update(metric_rule=rule,minimum_evidence_times=max(2,minimum))
    if group:result['affected_actor_options']=list(group)
    if derived:result['derived_from']=derived
    return name,result


def rule(q,op,value,unit='m',*,extra=None,combine='all'):
    clauses=[{'quantity':q,'operator':op,'threshold':value,'unit':unit}]
    if extra:clauses+=extra
    return {'clauses':clauses,'combine':combine,'unit':unit}


def motion(key,label,actor,*,after=None):
    return e(key,label,('The same initial '+actor+' visibly translates relative to stable original scene geometry over at least two supplied times. '
      'Camera motion, a changed appearance, rotation alone, or a substitute actor is insufficient.'+((' The movement must follow confirmed '+after+'.') if after else '')),
      [actor],minimum=2,notes=label+'。需两个不同时间点的平移证据，排除镜头运动、仅旋转和新物体替代。'+(('需在确认'+after+'后。') if after else ''))


def contact(key,label,a,b):
    return e(key,label,'The same initial '+a+' visibly makes physical contact with the same initial '+b+' within the declared observation window. Proximity or pixel overlap alone is insufficient.',
      [a,b],notes=label+'。追踪原对象；仅靠近、遮挡或像素重叠不能确认接触。没有看清接触时填不可判。')


def departure(key,label,actor,support):
    return e(key,label,'The same initial '+actor+' completely loses support/contact from the original '+support+'. Partial overhang or tilting while still supported is insufficient; floor impact is a separate event.',
      [actor,support],notes=label+'。必须完全失去原支撑；仍接触边缘、局部越缘或倾斜不算。下落和落地另记，出画不自动判发生。')


def metric(key,label,en,actor,q,op,value,*,unit='m',final=False,origin='source_rule',notes=''):
    key,d=e(key,label,en,[actor],role='critical_target',final=final,minimum=2,rule=rule(q,op,value,unit),notes=notes or label+'。按登记量、单位和比较符测量；缺标定或不能测量时填不可判，不凭像素距离推算物理量。')
    d['definition_origin']=origin
    return key,d


def scene_events(scene,header):
    exp=header.get('experiment',{});items=[];order=[];notes=[]
    if scene=='T01':
        b,c1,c2,m='t01v2_sliding_book','t01v2_chain_can_1','t01v2_chain_can_2','t01v2_chain_mug'
        items=[motion('book_motion','书本沿原斜面/桌面平移',b),contact('book_can_1_contact','书本接触第1罐',b,c1),contact('can_1_can_2_contact','第1罐接触第2罐',c1,c2),contact('can_2_mug_contact','第2罐接触原杯子',c2,m),
          metric('mug_final_displacement_gt_3cm','杯子末态三维位移 > 3 cm','Euclidean distance between the original mug center at observation end and at observation start is strictly greater than 0.03 m. This is final displacement, not path length or maximum displacement.',m,'mug_final_displacement_m','>',.03,final=True),
          e('full_chain','原T01 full_chain判据',['can2/mug contact AND mug final displacement >0.03 m'][0],role='critical_target',derived={'all':['can_2_mug_contact','mug_final_displacement_gt_3cm']})]
        order=[['book_can_1_contact','can_1_can_2_contact'],['can_1_can_2_contact','can_2_mug_contact']]
    elif scene=='T02':
        s,b,p,g='t02v2_striker_eraser','t02v2_gate_book','t02v2_probe_marble','t02v2_signal_brass_ball'
        items=[contact('A1_striker_book_contact','撞击橡皮接触竖书',s,b),
          contact('E4_blocked_marble_contacts_book','探针球接触原闸门书',p,b),
          metric('E4_open_marble_passes_book','探针球质心越过原通过平面','The maximum world x coordinate of the original probe-marble center reaches at least +0.170 m after release. This is the original center-plane criterion, not merely seeing an edge beyond the book.',p,'probe_max_center_world_x_m','>=',.170),
          contact('E5_open_marble_contacts_signal','探针球接触原信号球',p,g),
          metric('C2_signal_displaced_0p05m','信号球沿+x最大位移 ≥ 5 cm','Maximum forward world-x displacement of the original signal ball, relative to the settled release baseline, reaches 0.050 m. Do not use total 3D distance or ordinary settling drift.',g,'signal_max_forward_dx_m','>=',.05)]
        order=[['A1_striker_book_contact','E4_blocked_marble_contacts_book'],['E4_open_marble_passes_book','E5_open_marble_contacts_signal'],['E5_open_marble_contacts_signal','C2_signal_displaced_0p05m']]
    elif scene=='T03':
        b,c,p='t03v5_impulsed_book','t03v5_upper_edge_can','t03v5_lower_edge_phone'
        items=[motion('book_inertial_slide','原书本开始滑动',b),contact('book_contacts_upper_can','书本接触上层边缘罐',b,c),
          departure('can_leaves_upper_support','罐体完全脱离上层支撑',c,'@upper_support'),contact('can_lands_on_lower_shelf','罐体与下层斜架发生接触',c,'@lower_shelf'),
          contact('can_contacts_lower_phone','罐体接触原下层手机',c,p),departure('phone_leaves_lower_support','手机完全脱离下层支撑（二次跌落分支）',p,'@lower_shelf'),
          contact('phone_terminal_floor_contact','原手机接触最下层地面',p,'@terminal_floor')]
        order=[['book_contacts_upper_can','can_leaves_upper_support'],['can_leaves_upper_support','can_lands_on_lower_shelf'],['can_lands_on_lower_shelf','can_contacts_lower_phone'],['can_contacts_lower_phone','phone_leaves_lower_support'],['phone_leaves_lower_support','phone_terminal_floor_contact']]
    elif scene=='T04':
        b='t04v3_removable_support_bar';books=['t04v3_stack_book_'+x for x in ['bottom','middle','top']];c1,c2,m='t04v3_chain_can_1','t04v3_chain_can_2','t04v3_chain_mug'
        threshold=exp.get('parameter',{}).get('estimated_support_release_threshold_m')
        items=[motion('support_bar_moves','原支撑条被抽出',b),
          metric('support_bar_displacement_reaches_original_release_clearance','支撑条位移达到原配置释放间隙','Maximum absolute world-y displacement of the original support bar reaches the release-clearance value declared in this exact source configuration.',b,'support_bar_max_abs_dy_m','>=',threshold),
          e('stack_motion','书堆达到原stack_motion判据','At least one original stack book has maximum forward x displacement >0.12 m OR maximum downward center displacement >0.025 m. Do not equate any visible wobble with this numeric criterion.',books,role='critical_target',minimum=2,
            rule=rule('max_stack_book_forward_dx_m','>',.12,extra=[{'quantity':'max_stack_book_downward_dz_m','operator':'>','threshold':.025,'unit':'m'}],combine='any')),
          e('stack_book_can_1_contact','至少一本原堆叠书接触第1罐','At least one of the original bottom/middle/top stack books physically contacts can 1. Name the actual contacting book(s).',books+[c1],group=books),
          contact('can_1_can_2_contact','第1罐接触第2罐',c1,c2),contact('can_2_mug_contact','第2罐接触原杯子',c2,m),
          metric('mug_rotation_ge_18deg','原杯子相对初态最大三维旋转 ≥ 18°','Maximum quaternion/geodesic orientation change of the original mug relative to its initial pose reaches 18 degrees; camera-projected yaw is not automatically the same quantity.',m,'mug_max_3d_rotation_deg','>=',18.,unit='deg'),
          e('can2_mug_contact_and_rotation_ge_18deg','原末端传递判据：接触且杯子旋转 ≥18°','Can 2/mug contact AND mug maximum 3D rotation >=18 degrees.',role='critical_target',derived={'all':['can_2_mug_contact','mug_rotation_ge_18deg']})]
        order=[['support_bar_moves','stack_book_can_1_contact'],['stack_book_can_1_contact','can_1_can_2_contact'],['can_1_can_2_contact','can_2_mug_contact']]
    elif scene=='T05':
        p,c='t05v2_moving_phone','t05v2_downstream_can';v=exp.get('geometry_contract',{}).get('phone_center_full_pass_x_m')
        items=[motion('phone_motion','原手机沿托盘平移',p),contact('phone_left_guide_contact','手机接触原左导板',p,'t05v2_guide_left'),contact('phone_right_guide_contact','手机接触原右导板',p,'t05v2_guide_right'),
          metric('gate_passage','手机质心越过原完整通过判定平面','Maximum original-phone center world x reaches the exact source phone_center_full_pass_x_m. This is a fixed center-plane rule, not just the leading edge reaching the gate.',p,'phone_max_center_world_x_m','>=',v),
          contact('terminal_contact','手机接触原下游罐',p,c),motion('can_moves_after_phone_contact','下游罐在手机接触后平移',c,after='phone/can contact')]
        order=[['gate_passage','terminal_contact'],['terminal_contact','can_moves_after_phone_contact']]
    elif scene=='T06':
        pairs=exp.get('required_contact_pairs') or [[f't06_book_{i:02d}',f't06_book_{i+1:02d}'] for i in range(9)]
        items=[contact('adjacent_contact_'+str(i),f'相邻原书本接触：{a} → {b}',a,b) for i,(a,b) in enumerate(pairs)]
        items.append(e('complete_required_contact_chain','原登记的全部相邻接触链完成','Every original required adjacent-book pair has a recorded/confirmed contact. This criterion adds no tilt-angle, displacement or toppling-count threshold.',role='critical_target',derived={'all':['adjacent_contact_'+str(i) for i in range(len(pairs))]}))
        notes.append('T06采用原相邻接触合同；不把外力记成冲量，不自行添加倒伏角阈值。完整链的原判据不要求逐帧严格先后，观察顺序另记。')
    elif scene=='T07':
        p='t07_smartphone';items=[motion('phone_translation_observed','原手机相对原斜坡平移',p),
          metric('motion_ge_1cm','原手机最大三维位移 ≥ 1 cm','Maximum 3D displacement of the same original phone center from its initial position reaches 0.01 m; path length is not displacement.',p,'phone_max_displacement_m','>=',.01),
          departure('phone_leaves_ramp','原手机完全脱离原斜坡支撑',p,'@original_ramp'),
          contact('phone_table_contact_after_release','释放后原手机与桌面发生接触',p,'@original_tabletop'),
          e('phone_ramp_contact_at_end','观察窗末帧手机仍与原斜坡接触','At the last observable native frame of the declared window, the same original phone is in physical contact with its original ramp. Earlier ramp contact alone is insufficient.',[p,'@original_ramp'],final=True)]
        notes.append('B位置族按既有E4桌面接触定义；斜坡接触不能替代桌面接触。')
    elif scene=='T08':
        lo,up,m='t08_lower_impactor_book','t08_upper_payload_book','t08_target_mug'
        items=[motion('lower_book_translation','原下层驱动书平移',lo),motion('upper_book_translation','原上层载荷书平移',up),contact('lower_book_mug_contact','原下层书接触杯子',lo,m)]
        for actor,label in [(lo,'下层书'),(up,'上层书'),(m,'杯子')]:
            items.append(metric(actor+'_below_table_8cm',label+'质心低于原桌面超过8 cm','At some time in the observation window the original '+actor+' center has world z < original tabletop z -0.08 m. This is not a floor-contact label.',actor,actor+'_min_z_minus_tabletop_m','<',-.08))
        order=[['lower_book_translation','lower_book_mug_contact']]
    elif scene in ('T09','T18'):
        if scene=='T09':pull='t09_book_03';upper=exp.get('supported_book_names') or [f't09_book_{i:02d}' for i in range(4,8)]
        else:pull=exp.get('extracted_book_name');upper=exp.get('supported_book_names') or []
        if not pull or not upper:raise ValueError('Book extraction identity not recovered: '+scene)
        items=[motion('selected_book_extraction','指定原书本被抽取：'+pull,pull),
          e('upper_books_lose_original_layer_support','至少一本指定上层书完全失去抽取层支撑','At least one listed original upper supported book fully loses contact/support from the named extraction layer. Do not substitute the pulled book or an original lower book.',upper+[pull],group=upper),
          e('upper_nonpulled_book_contacts_table_during_window','至少一本指定上层非抽取书在窗内曾触桌','At any time in the declared window at least one listed original upper non-pulled book visibly contacts the original tabletop. This is an auxiliary ever-contact label, distinct from the last-frame target.',upper+['@original_tabletop'],group=upper),
          e('upper_nonpulled_book_on_table_at_end','末帧至少一本指定上层非抽取书触桌','At the last native frame of the declared observation window, at least one listed original upper non-pulled book contacts the original tabletop. The pulled book and lower books are excluded. Earlier transient contact, coherent one-layer sinking, rotation or displacement alone is insufficient.',upper+['@original_tabletop'],role='critical_target',final=True,group=upper,
            notes='只看观察窗末帧；须填写实际触桌的上层书实体ID。抽取书和下层书不计。曾经触桌不等于末帧触桌；13.5mm下沉代理、整体滑动和任意旋转均不能替代。')]
        order=[['selected_book_extraction','upper_nonpulled_book_contacts_table_during_window']]
    elif scene=='T10':
        tape,pen,folder='t10_tape_roll','t10_support_pen','t10_supported_folder';v=exp.get('support_ejection_threshold_m')
        items=[motion('tape_roll_motion','原胶带卷滚动/平移',tape),contact('tape_pen_contact','胶带卷侧向接触原支撑笔',tape,pen),
          metric('support_pen_displacement_reaches_source_threshold','支撑笔最大位移达到原阈值（原登记0.04m）','Maximum 3D original support-pen center displacement from the initial position reaches the exact source support_ejection_threshold_m. This is NOT the folder-support-loss event.',pen,'support_pen_max_displacement_m','>=',v),
          departure('folder_loses_pen_support','原文件夹完全失去原笔的支撑',folder,pen),
          e('folder_descends_after_support_loss','失去支撑后原文件夹向下运动','After complete loss of original pen support, the same initial folder shows downward motion across at least two supplied times. Pen motion alone, rotation with remaining support, or a substitute folder is insufficient.',[folder],minimum=2)]
        order=[['tape_pen_contact','folder_loses_pen_support'],['folder_loses_pen_support','folder_descends_after_support_loss']]
    elif scene=='T11':
        a,b,c='t11_driver_eraser','t11_relay_pencil_case','t11_eyeglasses_case'
        items=[contact('driver_pencil_case_contact','原橡皮接触原笔盒',a,b),contact('pencil_case_eyeglasses_case_contact','原笔盒接触原眼镜盒',b,c)]
        for actor,label in [(a,'橡皮'),(b,'笔盒'),(c,'眼镜盒')]:
            items.append(departure(actor+'_leaves_table',label+'完全失去原桌面支撑',actor,'@original_tabletop'))
            items.append(metric(actor+'_final_center_below_minus_20cm',label+'末态质心世界z < −0.20m','At the last native frame, the original '+actor+' center has world z strictly below -0.20 m, using the source world origin. Do not substitute edge crossing, any downward motion, or uncalibrated screen height.',actor,actor+'_final_center_world_z_m','<',-.20,final=True))
        order=[['driver_pencil_case_contact','pencil_case_eyeglasses_case_contact']]
    elif scene=='T12':
        a,b='t12_stapler','t12_tissue_box';items=[motion('stapler_slides_on_table','原订书机沿原桌面滑动',a),contact('stapler_contacts_tissue_box','原订书机接触原纸巾盒',a,b),
          motion('tissue_box_moves_after_contact','纸巾盒在订书机接触后平移',b,after='stapler/tissue-box contact'),
          metric('tissue_box_max_displacement_ge_1cm','原纸巾盒最大三维位移 ≥ 1 cm','Maximum original tissue-box center 3D displacement from the observation baseline reaches 0.01 m. For this frozen R002 source this is the v2 benchmark observation criterion; later R005 reference answers and boundaries are NOT imported.',b,'tissue_box_max_displacement_m','>=',.01,origin='benchmark_observation_v2; requires_R002_reference_recomputation')]
        order=[['stapler_contacts_tissue_box','tissue_box_moves_after_contact']]
        notes.append('本集使用R002。1cm是本轮明确登记的观察判据，不声称旧R002曾按此值标注；R005真值/边界不得迁入，须对同版本参考重算。')
    elif scene=='T13':
        a,b,c='t13_driver_book','t13_falling_book','t13_drink_box';items=[motion('driver_book_motion','原驱动书运动',a),contact('driver_to_falling_book_contact','原驱动书接触原接力书',a,b),contact('falling_book_to_drink_contact','原接力书接触原饮料盒',b,c),
          departure('drink_loses_original_support','原饮料盒完全失去原桌面支撑',c,'@original_tabletop'),
          metric('t13_drink_box_motion_ge_1cm','原饮料盒最大三维位移 ≥ 1 cm','Maximum original drink-carton center 3D displacement from the declared observation baseline reaches 0.01 m. This v2 observation criterion is registered for the actual T13F5 source; answers from a different T13_BG source cannot be transplanted.',c,'drink_box_max_displacement_m','>=',.01,origin='benchmark_observation_v2; exact_F5_reference_window_pending'),
          metric('drink_drop_ge_5cm','原饮料盒最大向下位移 ≥ 5 cm','Original drink-carton baseline center z minus minimum center z within the declared window reaches 0.05 m. This is neither floor contact nor arbitrary horizontal displacement.',c,'drink_box_max_downward_dz_m','>=',.05,origin='benchmark_observation_v2; exact_F5_reference_window_pending')]
        order=[['driver_to_falling_book_contact','falling_book_to_drink_contact'],['falling_book_to_drink_contact','drink_loses_original_support']]
        notes.append('按这100条实际的T13F5来源登记，不用T13_BG同类样本的距离或标签替代；数字阈值需对该版本和时域重新绑定参考。')
    elif scene=='T14':
        a,l,r,z='t14v2_marker','t14v2_corridor_book_left','t14v2_corridor_book_right','t14v2_terminal_eraser';c=exp.get('classification_contract',{})
        items=[motion('marker_motion','原长笔运动',a),contact('contacted_left_book','长笔接触原通道左书',a,l),contact('contacted_right_book','长笔接触原通道右书',a,r),
          metric('passed_channel','长笔质心越过原通道通过平面','Maximum original marker-center world x reaches classification_contract.channel_exit_center_x_m. This fixed center-plane criterion does not mean any part of the marker has crossed the outlet.',a,'marker_max_center_world_x_m','>=',c.get('channel_exit_center_x_m')),
          contact('contacted_eraser','原长笔接触末端橡皮',a,z),
          e('terminal_contact_after_full_exit','达到原通过平面后才接触末端橡皮','Both passed_channel and contacted_eraser are yes, and first eraser-contact time is not earlier than the first confirmed pass-plane time.',role='critical_target',derived={'all':['passed_channel','contacted_eraser'],'order':[['passed_channel','contacted_eraser']]})]
        notes.append('原passed_channel使用质心固定平面，和物体整段穿出/视觉前缘越口分开；通道左/右书及末端橡皮独立记录。')
    elif scene=='T16':
        a,b,c='t16_support_book','t16_folder','t16_downstream_box';items=[motion('support_withdrawal','原支撑书撤出',a),departure('folder_loses_original_support','原文件夹完全失去原支撑书支撑',b,a),
          e('folder_rotation_after_support_loss','失去支撑后原文件夹发生转动','The same original folder visibly changes orientation after complete original support loss. A camera rotation or substituted object is insufficient.',[b],minimum=2),
          contact('folder_table_impact','原文件夹接触原桌面',b,'@original_tabletop'),contact('folder_downstream_contact','原文件夹接触原下游盒子',b,c),motion('box_moves_after_folder_contact','原盒子在文件夹接触后平移',c,after='folder/box contact')]
        order=[['support_withdrawal','folder_loses_original_support'],['folder_loses_original_support','folder_rotation_after_support_loss'],['folder_downstream_contact','box_moves_after_folder_contact']]
        notes.append('不借用Isaac传播深度标签作为当前Genesis文件夹接触真值。')
    elif scene=='T17':
        a,b='t17_can','t17_tissue_box';items=[motion('can_rolls_or_slides','原罐体沿原斜坡滚动/滑动',a),contact('can_tissue_box_contact','原罐体接触原纸巾盒',a,b),
          departure('can_leaves_table','原罐体完全失去原桌面支撑',a,'@original_tabletop'),contact('can_floor_contact','原罐体接触地面',a,'@terminal_floor'),motion('tissue_box_moves_after_can_contact','纸巾盒在罐体接触后平移',b,after='can/tissue-box contact')]
        order=[['can_tissue_box_contact','tissue_box_moves_after_can_contact'],['can_leaves_table','can_floor_contact']]
    elif scene=='T19':
        a,b='t19_can1','t19_can2';items=[motion('can1_motion','原第1罐运动',a),contact('can_contact','原第1罐与第2罐接触',a,b),motion('can2_motion_after_contact','原第2罐在接触后运动',b,after='can1/can2 contact'),
          departure('can1_leaves_table','原第1罐完全失去桌面支撑',a,'@original_tabletop'),departure('can2_leaves_table','原第2罐完全失去桌面支撑',b,'@original_tabletop')]
        order=[['can_contact','can2_motion_after_contact']]
        notes.append('本批生成条件实际来自旧Genesis双罐版本。可登记其实际接触/越缘观察；不得接入后来Isaac/多物体版本的参考、边界或配对，正式资格单列。')
    elif scene=='T20':
        b,c,x,m='t20_book','t20_can','t20_box','t20_cup'
        items=[motion('book_motion','原书本运动',b),contact('contact_book_can','原书本接触原罐体',b,c),motion('can_motion_after_contact','原罐体在书本接触后平移',c,after='book/can contact'),
          contact('contact_can_box','原罐体接触原盒子',c,x),motion('box_motion_after_contact','原盒子在罐体接触后平移',x,after='can/box contact'),
          contact('contact_box_cup','原盒子接触原杯子',x,m),motion('cup_response','原杯子在盒子接触后平移',m,after='box/cup contact'),
          e('complete_observed_propagation','可见完整接力链（接触与后续运动）','All three named contact links and each named receiver translation are observed. This is an observation-vector conjunction, not an inferred force or an Isaac propagation-depth label.',role='critical_target',derived={'all':['contact_book_can','can_motion_after_contact','contact_can_box','box_motion_after_contact','contact_box_cup','cup_response']})]
        order=[['contact_book_can','contact_can_box'],['contact_can_box','contact_box_cup'],['contact_box_cup','cup_response']]
    else:raise ValueError('Unsupported scene '+scene)
    return dict(items),order,notes


def make_protocol(clip,header,prior):
    scene=clip[:3]
    if scene=='T15':return copy.deepcopy(prior)
    events,order,notes=scene_events(scene,header)
    primary={
      'T01':['book_can_1_contact','can_1_can_2_contact','full_chain'],
      'T02':['A1_striker_book_contact','E4_blocked_marble_contacts_book','C2_signal_displaced_0p05m'],
      'T03':['can_leaves_upper_support','phone_leaves_lower_support'],
      'T04':['support_bar_displacement_reaches_original_release_clearance','stack_motion','can2_mug_contact_and_rotation_ge_18deg'],
      'T05':['gate_passage','terminal_contact'],'T06':['complete_required_contact_chain'],
      'T07':['motion_ge_1cm','phone_table_contact_after_release'],
      'T08':[k for k in events if k.endswith('_below_table_8cm')],
      'T09':['upper_nonpulled_book_on_table_at_end'],'T10':['support_pen_displacement_reaches_source_threshold','folder_loses_pen_support'],
      'T11':[k for k in events if k.endswith('_final_center_below_minus_20cm')],
      'T12':['tissue_box_max_displacement_ge_1cm'],'T13':['t13_drink_box_motion_ge_1cm','drink_drop_ge_5cm'],
      'T14':['passed_channel','terminal_contact_after_full_exit'],'T16':['folder_downstream_contact'],
      'T17':['can_tissue_box_contact'],'T18':['upper_nonpulled_book_on_table_at_end'],
      'T19':['can_contact','can2_leaves_table'],'T20':['contact_book_can','contact_can_box','contact_box_cup','complete_observed_propagation']}
    for key in primary[scene]:events[key]['role']='critical_target'
    # Source descriptions, never source event outcomes, go into the judge prompt.
    names=sorted({a for d in events.values() for a in d['actors']})
    objects={o['name']:o.get('spec',o) for o in header.get('dynamic_objects',[])}
    actors=[]
    for name in names:
        spec=objects.get(name,{})
        actors.append({'id':name,'anchor':'原首帧对象；按空间连续性追踪，不能由新物体替代' if not name.startswith('@') else name[1:],
          'initial_position_m':spec.get('pose',{}).get('position'),'color_rgb':spec.get('color'),
          'source_actor_present':name in objects if not name.startswith('@') else None})
    source_files=[]
    for p in SOURCES[scene]:
        source_files.append({'path':p,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()})
    specific={
      'T02':('原撞击橡皮、竖立闸门书、探针小球和末端黄铜信号球。','the initial striker eraser, upright gate book, probe marble and terminal brass signal ball'),
      'T04':('原可抽取支撑条、下/中/上三本堆叠书、第1罐、第2罐及末端杯子。','the initial removable support bar, bottom/middle/top stack books, can 1, can 2 and terminal mug'),
      'T19':('原双罐场景中的第1驱动罐和第2接收罐。','the original driving can 1 and receiving can 2 in this frozen two-can scene')}
    target,target_en=prior['target'],prior['target_en']
    if scene in specific:
        zh,en=specific[scene];target='仅追踪'+zh+'按首帧外观和空间连续性识别；新出现的同类物体不能替代原对象。';target_en='Track '+en+' by initial appearance and spatial continuity; never substitute newly appearing objects.'
    return {'version':VERSION+'-'+clip,'status':'frozen','freeze_scope':'observation_definitions_only',
      'critical_contract_status':'observation_registered_reference_admission_separate','scene_id':scene,
      'target':target,'target_en':target_en,'actors':actors,'events':events,'critical_targets':primary[scene],
      'required_order':order,'order_scope':'expected causal ordering only; annotate actual order, do not force labels or times to fit it',
      'notes':notes,'annotation_policy_zh':COMMON_ZH,
      'source_binding':{'sample_id':header.get('sample_id'),'config_or_header_sha256':header.get('sha256'),
        'binding_role':header.get('source_role','source_configuration_unavailable'),'reference_admission':'pending'},
      'definition_sources':source_files,'scoring_admission':'separate_reference_boundary_pair_and_window_registration_required'}


def build_catalog(root):
    from formal_protocols import observation_protocol
    root=Path(root);headers=json.loads((root/'merged_source_headers.json').read_text(encoding='utf-8'))
    original=json.loads(Path('review/formal3600_hf_20261023/formal_manifest.json').read_text(encoding='utf-8'))
    old={t['clip_id']:t['protocol'] for t in original['tasks']}
    protocols={}
    for scene in range(1,21):
        for case in range(1,6):
            clip=f'T{scene:02d}_C{case:02d}';protocols[clip]=make_protocol(clip,headers.get(clip,{}),old[clip])
    catalog={'schema':'phy2-core100-event-contracts-v2','version':VERSION,'policy_zh':'简化复核：只选择质量与事件标签，不填写时间和文字理由；完整观看并核对末帧，数值判据需标定。','human_review_policy':{'version':'label-review-v3','manual_timestamps':False,'manual_rationale':False},'clips':protocols,
      'summary':{'scenes':20,'clips':100,'event_fields':sum(len(p['events']) for p in protocols.values()),
                 'source_header_matches':len(headers),'reference_admission_granted':False}}
    readiness=Path('annotation_site/resources/core100_readiness.json')
    if readiness.exists():
        rows=json.loads(readiness.read_text(encoding='utf-8'))['rows']
        keys=['reference_blockers','boundary_blockers','pair_registration_blockers','window_alignment','measurement_calibration','nearacc_eligible','pairacc_eligible']
        catalog['registration_gaps']={r['clip_id']:{k:r[k] for k in keys if k in r} for r in rows}
    Path('annotation_site/resources/event_contracts.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'event_contracts.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    return catalog


if __name__=='__main__':
    from audit_original_contracts import build
    print(json.dumps(build()))
