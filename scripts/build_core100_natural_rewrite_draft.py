"""Build an isolated, source-bound writing draft; never activate generation inputs."""
from pathlib import Path
import hashlib
import json
import math
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from physedit.core100_release import load
from physedit.compact_prompt import counts

OLD = ROOT / 'review/prompt_length_natural_20261030'
OUT = ROOT / 'review/core100_natural_rewrite_draft_20261101'
sha = lambda b: hashlib.sha256(b).hexdigest()

def write(name, text):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf8')

def jl(name, rows):
    write(name, ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))

def clean_numbers(text):
    ledger = []
    def replace(m):
        raw = m[0]
        value = float(raw)
        # Only eliminate floating-point representation noise, not meaningful precision.
        display = raw
        for n in range(1, 17):
            candidate = format(value, f'.{n}g')
            if abs(float(candidate)-value) <= 8*math.ulp(value):
                display = candidate
                break
        if raw != display:
            ledger.append({'original_text':raw, 'display_text':display,
                           'absolute_difference':abs(float(display)-value),
                           'policy':'at most 8 binary64 ULP; raw source unchanged'})
        return display
    return re.sub(r'(?<![\w.])-?\d+\.\d+(?![\w.])', replace, text), ledger

def rewrite_legacy(text):
    text = text.replace('Continue the scene from the supplied image with a fixed camera. ', '')
    text = re.sub(r'The (can [12]|book \d\d)\b', lambda m:m[1].capitalize(), text)
    text = re.sub(r'the (can [12]|book \d\d)\b', r'\1', text)
    text = text.replace('frozen tabletop surface', 'tabletop surface')
    text = text.replace('The books are dynamic bodies rather than an animated sequence. ', '')
    text = text.replace('The stated extraction distance is a prescribed input, not a guaranteed displacement.',
                        'The extraction distance below is the actuator command.')
    text = text.replace('The phone is not another object on the tabletop. ', '')
    text = text.replace('Off-screen force acts on ', 'An off-screen force is applied to ')
    text = text.replace('Off-screen actuation tilts Book ', 'An off-screen actuator tilts the driver book ')
    text = text.replace('Off-screen actuation moves Support book ', 'An off-screen actuator moves the support book ')
    text = text.replace("The book's release position along the ramp is", "The book's initial along-ramp coordinate in the source configuration is")
    # Identify the instruction as image-conditioned continuation, not an invented edit pair.
    return ('Use the supplied image as the initial scene and keep the camera fixed. '+text.strip())

def t19(task):
    p=ROOT/f"benchmarks/core100_t19_isaac_v1_20261031/references/{task['clip_id']}/config.json"
    config=json.loads(p.read_text(encoding='utf8'))
    objects={o['name']:o for o in config['objects']}
    a,b=objects['t19_striker'],objects['t19_target']
    assert 'can' in a['asset_id'] and 'tissue_box' in b['asset_id']
    assert b['motion']['initial_velocity']==[0,0,0]
    v=a['motion']['initial_velocity'];assert v[1:]==[0,0]
    facts={f[0]:f[-2] for f in task['parameter_facts']}
    assert v[0]==facts['t19_striker.initial_speed']
    for obj in ('t19_striker','t19_target'):
        for field in ('mass','friction','restitution'):
            assert objects[obj][field]==facts[f'{obj}.{field}']
    offset=a['pose']['position'][1]-b['pose']['position'][1]
    assert math.isclose(offset,facts['impact_eccentricity_m'],abs_tol=1e-12)
    text=(f"Use the supplied image as the initial scene and keep the camera fixed. An upright beverage can and a tissue box stand on the tabletop. "
          f"The can starts behind the tissue box along the positive world x direction. At the start, give the can an initial velocity of {v[0]} m/s along that direction; the tissue box starts at rest. "
          f"Both objects remain free to move under gravity and contact forces, with no continuing prescribed push.\n\n"
          f"Gravity acts downward at {facts['gravity']} m/s^2. The can's initial center is offset by {offset} m along world y relative to the tissue box's center. "
          f"The can has a mass of {a['mass']} kg, a material friction coefficient of {a['friction']} and a coefficient of restitution of {a['restitution']}. "
          f"The tissue box has a mass of {b['mass']} kg, a material friction coefficient of {b['friction']} and a coefficient of restitution of {b['restitution']}. "
          f"The tabletop has a material friction coefficient of {facts['tabletop_collision_slab.friction']}.")
    return text, {'source_config_path':str(p.relative_to(ROOT)), 'source_config_sha256':sha(p.read_bytes()),
                  'source_read_mode':'current local original Isaac configuration', 'source_objects':list(objects)}

def main():
    audits={r['clip_id']:r for r in map(json.loads,(OLD/'audit/per_case_source_checks.jsonl').read_text(encoding='utf8').splitlines())}
    tasks=load()[2]['tasks'];rows=[];numbers=[];chapters=[]
    protected=[ROOT/'catalog/active_core100_conditions.json',ROOT/'benchmarks/core100_t19_isaac_v1_20261031/known_conditions.json']
    before={str(p):sha(p.read_bytes()) for p in protected}
    for task in sorted(tasks,key=lambda t:t['clip_id']):
        cid=task['clip_id']
        original=task['prompt_variants_en'][0]
        if cid.startswith('T19'):
            text,evidence=t19(task)
        else:
            a=audits[cid];assert a['sample_id']==task['sample_id'],cid
            p=OLD/f'prompts/long/{cid}.txt'
            assert sha(p.read_bytes())==a['long_sha256'],cid
            text=rewrite_legacy(p.read_text(encoding='utf8'))
            evidence={'source_config_path':a['source_config_path'], 'source_config_sha256':a['source_config_sha256_recorded'],
                      'source_read_mode':a['source_read_mode'], 'source_role':a['source_role'],
                      'source_audit_path':str((OLD/'audit/per_case_source_checks.jsonl').relative_to(ROOT)),
                      'source_snapshot_sha256':a['source_snapshot_sha256'],
                      'note':'Reuses prior per-case source audit; not a fresh remote render/config identity audit.'}
        text,changes=clean_numbers(text)
        assert not re.search(r'\bwill (?:hit|fall|collide|topple)|NearAcc|PairAcc|expected_chain|theta_star',text,re.I),cid
        write(f'prompts/{cid}.txt',text+'\n')
        write(f'originals/{cid}.txt',original)
        row={'clip_id':cid,'sample_id':task['sample_id'],'status':'writing_draft_not_activated',
             'task_type':'image_conditioned_physical_continuation','prompt':text,
             'prompt_sha256':sha(text.encode()),'original_prompt_sha256':sha(original.encode()),
             'original_prompt':original,'reference':task['reference'],
             'exact_active_parameter_facts':task['parameter_facts'], 'evidence':evidence,
             'tokens_including_eos':counts(text),
             'edit_pair_status':'not_created_no_verified_source_target_pair_bound'}
        rows.append(row);numbers.extend({'clip_id':cid,**x} for x in changes)
        chapters.append(f'## {cid}\n\n原正式文本（保留）：\n\n```text\n{original}\n```\n\n重写草稿：\n\n```text\n{text}\n```\n')
    assert len(rows)==100 and len({r['clip_id'] for r in rows})==100
    assert all(sha(Path(p).read_bytes())==h for p,h in before.items())
    jl('drafts.jsonl',rows);jl('numeric_display_changes.jsonl',numbers)
    write('100组完整对照.md','\n'.join(chapters))
    report={'drafts':len(rows),'scenes':20,'current_isaac_t19_rewritten':5,
            'previous_source_audits_reused':95,'new_verified_edit_pairs':0,
            'numeric_display_changes':len(numbers),'protected_catalogs_unchanged':True,
            'activated':False,'generated_videos':0,
            'token_ranges':{k:[min(r['tokens_including_eos'][k] for r in rows),max(r['tokens_including_eos'][k] for r in rows)] for k in rows[0]['tokens_including_eos']}}
    write('CHECK_REPORT.json',json.dumps(report,ensure_ascii=False,indent=2))
    write('README.md','''# Core100 自然描述重写草稿

100条、20场景，每条一版自然描述。先交付规范主文本，不再生成只换开头的三个版本。
这是首帧条件下的物理续写；没有把它冒充为源视频物理编辑。

`100组完整对照.md`查看全文，`prompts/`取单条新文本；`originals/`保留当前正式文本。
`drafts.jsonl`保存当前参考绑定、原参数、文本哈希和来源依据。
95条沿用已有逐案例来源审计的场景/控制描述并润色，不声称本轮重新核验了远程原始渲染。
T19五条从当前Isaac配置重写：易拉罐与纸巾盒，不再沿用旧双罐场景。

仅清除8个binary64 ULP以内的浮点显示尾数，逐项差异见`numeric_display_changes.jsonl`；真实参数与临界阈值不变。
有实际精度意义的长小数仍保留。坐标原点未确认的量保留原配置坐标表述，不猜空间方向。

本包是写作草稿，未上线、未调用模型、未改变原正式提示词或成绩，也不是已经测出提升的新输入。
新增控制说明意味着与旧版的比较是输入表述/信息完整性比较，不能宣称仅检验字数。
需按具体模型核对token长度，禁止静默截断。此包没有复制旧条件图，生成前必须从当前reference绑定取对应首帧。

物理编辑另需绑定源视频、原值、目标值、介入时间及保持不变的条件；本包不编造这些配对。
编辑指令结构：Edit the source video by changing [physical parameter] from [source value] to [target value] at [verified execution time]. Keep [verified unchanged conditions]. Generate the subsequent motion under the edited condition.
方括号模板不能直接提交模型；必须有真实配对来源后填入。全量72000条尚未覆盖或替换。
''')
    manifest={str(p.relative_to(OUT)).replace('\\','/'):sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='MANIFEST_SHA256.json'}
    write('MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(OUT/'Core100_自然描述重写草稿.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob('*'):
            if p.is_file() and p.suffix!='.zip':z.write(p,p.relative_to(OUT))
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
