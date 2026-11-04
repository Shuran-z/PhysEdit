"""Rewrite the eight new sources; retain the other 92 independently bound drafts."""
import gzip
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import re
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from physedit.core100_rebalanced import load
from physedit.compact_prompt import counts
from build_core100_natural_rewrite_draft import clean_numbers

OUT=ROOT/'review/core100_rebalanced_natural_20261101'
OLD=ROOT/'review/core100_natural_rewrite_draft_20261101'
SUP=ROOT/'benchmarks/critical_supplement_v1_20261101'
sha=lambda b:hashlib.sha256(b).hexdigest()
def put(name,text):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8')
def jl(name,rows):put(name,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
def num(v):return clean_numbers(str(v))[0]

def materials(objects,names):
    return ' '.join(f"{display} has a mass of {num(objects[key]['mass'])} kg, a material friction coefficient of {num(objects[key]['friction'])}, and a coefficient of restitution of {num(objects[key]['restitution'])}." for key,display in names)

def rewrite(task):
    pid=task['supplement_point_id'];scene=task['clip_id'][:3]
    p=SUP/f'evidence/{pid}.json.gz';src=json.loads(gzip.decompress(p.read_bytes()))
    objects={o.get('spec',o)['name']:o.get('spec',o) for o in src['dynamic_objects']}
    facts={r[0]:r[-2] for r in task['parameter_facts']}
    clock=task['clock'];hold=str(Fraction(clock['remaining_static_frames'],round(clock['static_clock_hz'])))
    g=facts.get('gravity',-facts.get('gravity_vector',[0,0,-9.81])[2])
    lead='Use the supplied image as the initial scene and keep the camera fixed. '
    time=f'Keep the initial scene still for {hold} s after the supplied condition frame. '
    gravity=f'Gravity acts downward at {num(g)} m/s^2. '
    if scene=='T04':
        text=lead+'Three books are stacked on a fixed inclined folder ramp beside a removable support bar. Two cans and a mug stand farther along the tabletop. The ramp and its support remain fixed; the support bar, books, cans, and mug are separate dynamic objects.\n\n'
        force=src['runtime_forces'][0]
        assert force['target']=='t04v3_removable_support_bar' and force['force_world']==[0,.46,0]
        assert force['frame_start']==0 and force['frame_end']==32
        text+=time+f"Then give the support bar an initial velocity of {num(facts['t04v3_removable_support_bar.initial_speed'])} m/s along positive world y, and apply an off-screen force of {num(facts['support_pull_force_magnitude_n'])} N to that bar in the same direction for {num(facts['support_pull_force_duration_s'])} s. The extraction distance setting is {num(facts['commanded_extraction_distance_m'])} m; it is a command, not a guaranteed displacement. No continuing force is prescribed after the pull ends.\n\n"
        text+=gravity+f"The ramp inclination is {num(facts['ramp_angle_deg'])} degrees, and its material friction coefficient is {num(facts['ramp_friction_coefficient'])}. The tabletop material friction coefficient is {num(facts['table_friction_coefficient'])}. "
        text+=materials(objects,[(f't04v3_{k}',v) for k,v in [('removable_support_bar','The support bar'),('stack_book_bottom','The bottom book'),('stack_book_middle','The middle book'),('stack_book_top','The top book'),('chain_can_1','Can 1'),('chain_can_2','Can 2'),('chain_mug','The mug')]])
    elif scene=='T05':
        par=src['experiment']['parameter'];phone=objects['t05v2_moving_phone']
        v=phone['motion']['initial_velocity'];assert math.isclose(math.dist(v,[0,0,0]),facts['initial_speed_mps'],abs_tol=1e-12)
        assert v[0]>0 and v[1]==0 and v[2]<0
        text=lead+'A phone rests on an inclined tray in front of a narrow opening between two fixed guides. A can stands farther along the tray. Keep the tray and guides fixed; the phone and can are separate dynamic objects.\n\n'
        text+=time+f"Then give the phone a one-time initial speed of {num(facts['initial_speed_mps'])} m/s down the tray, toward positive world x. Its initial yaw relative to the tray's lengthwise direction is {num(facts['initial_yaw_deg'])} degrees. The can starts at rest. No continuing external push is applied.\n\n"
        text+=gravity+f"The tray is inclined at {num(facts['tray_angle_deg'])} degrees. The clear guide opening is {num(facts['gap_width_m'])} m, which is {num(par['gap_ratio'])} times the phone's nominal width of {num(par['phone_nominal_width_m'])} m. The tray material friction coefficient is {num(facts['phone_tray_friction_coefficient'])}; the guides' is {num(facts['guide_friction_coefficient'])}, and the tabletop's is {num(facts['table_friction_coefficient'])}. "
        text+=materials(objects,[('t05v2_moving_phone','The phone'),('t05v2_downstream_can','The can')])
    elif scene=='T10':
        roll=objects['t10_tape_roll'];v=roll['motion']['initial_velocity'];w=roll['motion']['initial_angular_velocity'];pos=objects['t10_support_pen']['pose']['position']
        assert v==[0,facts['t10_tape_roll.initial_speed'],0] and w[1:]==[0,0]
        text=lead+'A pen supports an inclined folder on the tabletop, with a tape roll nearby. The folder and pen are dynamic objects, not fixed supports.\n\n'
        text+=time+f"Then release the tape roll with an initial velocity of {num(v[1])} m/s along positive world y and an angular velocity of {num(w[0])} rad/s about world x. The folder and pen have zero prescribed initial linear velocity. No continuing external push is applied.\n\n"
        text+=gravity+f"The pen's initial world position is ({', '.join(num(z) for z in pos)}) m. The folder is initially inclined at {num(facts['t10_supported_folder.initial_angle'])} degrees; preserve the tilt direction shown in the image. "
        text+=materials(objects,[('t10_supported_folder','The folder'),('t10_support_pen','The pen'),('t10_tape_roll','The tape roll')])
        text+=f" The tabletop material friction coefficient is {num(facts['frozen_tabletop_collision_slab.friction'])}."
    else:
        assert scene=='T11'
        recipe=clock['conditional_force_recipe'];v=objects['t11_driver_eraser']['motion']['initial_velocity'];assert v==[0,0,0]
        assert recipe['first_contact_pair']==['t11_driver_eraser','t11_relay_pencil_case']
        assert recipe['stop_on_contact_pair']==['t11_relay_pencil_case','t11_eyeglasses_case']
        nominal=re.search(r'Nominal drive ([0-9.]+) m/s',task['prompt_en'])[1]
        text=lead+'An eraser, a rigid pencil case, and an eyeglasses case are arranged in that order along positive world x on the tabletop. They are separate dynamic objects.\n\n'
        text+=time+f"The eraser's actual initial linear velocity is zero. The source controller's nominal drive setting is {nominal} m/s; this is a controller setting, not the eraser's initial velocity. Apply an off-screen force to the eraser along positive world x, using the following conditional rule. Start with {num(recipe['force_world'][0])} N. If the eraser contacts the pencil case, switch to {num(recipe['force_world_after_first_contact'][0])} N. If the pencil case contacts the eyeglasses case, switch to {num(recipe['force_world_after_contact'][0])} N for {recipe['stop_after_contact_delay_frames']} controller frames, then stop. Force is enabled only during active controller frames {recipe['frame_start']}-{recipe['frame_end']} at 30 Hz, counted from the end of the initial hold. A switch is triggered only if its stated contact occurs; no contact or final motion is prescribed.\n\n"
        text+=gravity+materials(objects,[('t11_driver_eraser','The eraser'),('t11_relay_pencil_case','The pencil case'),('t11_eyeglasses_case','The eyeglasses case')])
        text+=f" The tabletop material friction coefficient is {num(objects['t11_tabletop_collision_slab']['friction'])}; the floor's is {num(objects['t11_floor_collision_slab']['friction'])}. "
        text+=f"The initial eraser-to-pencil-case gap is {num(facts['prescribed_parameters.driver_relay_gap_m'])} m, the pencil-case-to-eyeglasses-case gap is {num(facts['prescribed_parameters.relay_case_gap_m'])} m, and the configured eyeglasses-case edge margin is {num(facts['prescribed_parameters.case_edge_margin_m'])} m."
    checks=[]
    for key,value in facts.items():
        if '.' not in key:continue
        obj,field=key.rsplit('.',1)
        if obj in objects and field in ['mass','friction','restitution']:
            assert objects[obj][field]==value,(task['clip_id'],key)
            checks.append(key)
    # Keep only initial inputs in audit export: never export trajectories or outcomes to generation.
    safe={'objects':[{k:o[k] for k in ['name','size','pose','fixed','mass','friction','restitution','motion'] if k in o} for o in objects.values()],
          'runtime_forces':src.get('runtime_forces',[]),'declared_schedule':clock}
    evidence={'source_file':p.relative_to(ROOT).as_posix(),'sha256':sha(p.read_bytes()),'checked_body_fields':checks}
    return text,evidence,safe

def main():
    root,manifest,tasks,mapping=load();changed={x['clip_id']:x for x in mapping}
    prior={r['clip_id']:r for r in map(json.loads,(OLD/'drafts.jsonl').read_text(encoding='utf8').splitlines())}
    protected=[ROOT/'catalog/active_core100_conditions.json',ROOT/'catalog/core100_critical_pairs_v2.json',root/'known_conditions.json']
    before={str(p):sha(p.read_bytes()) for p in protected}
    rows=[];audit=[];comparisons=[]
    for t in tasks:
        cid=t['clip_id'];original=t['prompt_variants_en'][0]
        if cid in changed:
            text,evidence,safe=rewrite(t)
            assert t['sample_id']==changed[cid]['new_native_sample_id']
            assert t['reference']['sha256']==changed[cid]['new_reference_sha256']
            image=ROOT/t['condition_image'];assert sha(image.read_bytes())==t['condition_sha256']
            dest=OUT/f'conditions/{cid}.png';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(image,dest)
            safe['parameter_facts']=t['parameter_facts'];put(f'audit/{cid}_inputs.json',json.dumps(safe,ensure_ascii=False,indent=2))
            audit.append({'clip_id':cid,**evidence,'condition_sha256':t['condition_sha256']})
        else:
            old=prior[cid]
            assert old['sample_id']==t['sample_id'] and old['reference']['sha256']==t['reference']['sha256'],cid
            text=old['prompt'];evidence=old['evidence']
        assert not re.search(r'\bwill (?:hit|fall|collide|topple)|NearAcc|PairAcc|theta_star|expected_chain',text,re.I)
        assert not any(bad in text for bad in ['cf_stack_sliding','theta_minus','gate_passage_star'])
        put(f'prompts/{cid}.txt',text);put(f'originals/{cid}.txt',original)
        rows.append({'clip_id':cid,'sample_id':t['sample_id'],'roster_version':manifest['version'],
                     'reference':t['reference'],'prompt':text,'prompt_sha256':sha(text.encode()),
                     'original_prompt':original,'original_prompt_sha256':sha(original.encode()),
                     'replaced_case':cid in changed,'evidence':evidence,
                     'exact_parameter_facts':t['parameter_facts'],'clock':t.get('clock'),
                     'tokens_including_eos':counts(text),'status':'candidate_not_final_not_activated'})
        comparisons.append(f"## {cid}{'（本轮替换案例）' if cid in changed else ''}\n\n原版（当前名单绑定的文本）：\n\n```text\n{original}\n```\n\n新版：\n\n```text\n{text}\n```\n")
    jl('drafts.jsonl',rows);jl('audit/new_eight_checks.jsonl',audit)
    put('100组完整对照.md','\n'.join(comparisons))
    put('8条替换案例完整对照.md','\n'.join(c for c in comparisons if '（本轮替换案例）' in c))
    # Deliberately do not copy the outcome-bearing replacement_map into model inputs.
    jl('case_bindings.jsonl',[{'clip_id':t['clip_id'],'sample_id':t['sample_id'],'reference_sha256':t['reference']['sha256'],'replacement':t['clip_id'] in changed} for t in tasks])
    issues=[{'cases':['T11_C01','T11_C02'],'field':'eyeglasses_case_mass','body_spec_kg':.12,'prescribed_metadata_kg':.2,
             'draft_uses':'actual object spec 0.12 kg','status':'metadata conflict recorded; confirm intended final protocol before sealing'},
            {'cases':['T11_C01','T11_C02'],'field':'driver_force_after_second_contact_frames','registered_unit':'N','actual_semantics':'controller frames',
             'draft_uses':'frames, consistent with conditional_force_recipe; original registry unchanged'},
            {'scope':'other 92','status':'previous source-bound writing drafts retained, not a new exhaustive control/config audit'},
            {'scope':'tokenizer','status':'model input budget must be verified before final generation; no truncation or auto-expansion'}]
    put('FINALIZATION_ISSUES.json',json.dumps(issues,ensure_ascii=False,indent=2))
    assert all(sha(Path(p).read_bytes())==v for p,v in before.items())
    report={'roster_version':manifest['version'],'cases':len(rows),'replaced_cases':list(changed),'new_eight_reference_and_image_bindings_checked':8,
            'unchanged_case_drafts':92,'body_field_checks':sum(len(a['checked_body_fields']) for a in audit),
            'final':False,'activated':False,'old_results_modified':False,
            'token_ranges':{k:[min(r['tokens_including_eos'][k] for r in rows),max(r['tokens_including_eos'][k] for r in rows)] for k in rows[0]['tokens_including_eos']}}
    put('CHECK_REPORT.json',json.dumps(report,ensure_ascii=False,indent=2))
    put('README.md','''# 最新 Core100 自然提示词候选版

名单入口：catalog/core100_critical_pairs_v2.json。100条中8条已换新来源，另外92条保持来源一致。
100组完整对照.md：全部原版与新版；8条替换案例完整对照.md：本轮重点检查。
这里的“原版”是新名单已有的短提示词，不是已淘汰案例的提示词。
prompts/ 为新文本；originals/ 为对应原文；drafts.jsonl 保存来源、原始参数和控制时钟。
8条新案例附哈希核对的条件图，audit/只存初始物体及控制输入，不包含事件答案。
不把整个audit/drafts当成模型提示词：模型只读取prompt和绑定的condition，其他为实验登记。

新8条按来源物体配置补全质量、摩擦、恢复系数；T10补角速度；T11完整保留条件外力。
T11控制切换只写“如果接触”，不要求接触必然发生；名义驱动设置不冒充真实初速度。
尺寸、精确初始坐标、固定物体等保留在参数/输入登记中，正文用条件图表示布局；不是无记录删除。
数值只清理8 ULP以内的显示尾数，原始数值保持不变。

仍为候选版，未覆盖在线正式输入或原成绩。其余92条沿用上一版写作草稿，未声称重新完成逐帧/全控制审核。
T11物体配置质量0.12kg与prescribed元数据0.2kg冲突已单列；草稿按物体配置写0.12kg。
这一版本较长，必须检查各模型token上限，不得静默截断；不能保证所有12个模型可直接使用。
FINALIZATION_ISSUES.json列明封版前问题。未运行新视频、未检验提示词效果提升。
''')
    hashes={p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='MANIFEST_SHA256.json'}
    put('MANIFEST_SHA256.json',json.dumps(hashes,indent=2))
    with zipfile.ZipFile(OUT/'Core100_换8条后_提示词候选版.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob('*'):
            if p.is_file() and p.suffix!='.zip':z.write(p,p.relative_to(OUT))
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
