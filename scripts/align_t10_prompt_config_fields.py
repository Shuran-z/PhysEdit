"""Align every represented T10 physical field against its bound configuration."""
from pathlib import Path
import collections
import gzip
import hashlib
import json
import math
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from physedit.compact_prompt import counts,MODEL_BUDGETS

SOURCE=ROOT/'review/t10_config_speed_resolution_20261102/videos.jsonl.gz'
EVIDENCE=ROOT/'review/t10_groundtruth_resolution_20261102'
OUT=ROOT/'review/t10_config_alignment_20261102'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_fields(c):
    objects={o['name']:o for o in c['dynamic_objects']}
    result={}
    result['gravity']=('Gravity',math.sqrt(sum(x*x for x in c['scene_overrides']['gravity'])),'m/s^2')
    for key,title in [('t10_supported_folder','Supported folder'),('t10_support_pen','Support pen'),('t10_tape_roll','Tape roll')]:
        for prop,unit in [('mass','kg'),('friction',''),('restitution','')]:
            result[key+'.'+prop]=(title+' '+prop,objects[key][prop],unit)
    folder=objects['t10_supported_folder']
    angle=abs(folder['pose']['euler_xyz'][1])
    assert math.isclose(angle,c['experiment']['t10_design']['folder_lean_deg_from_table'])
    result['t10_supported_folder.initial_angle']=('Supported folder initial angle',angle,'deg')
    for axis,value in zip('XYZ',objects['t10_support_pen']['pose']['position']):
        result['t10_support_pen.initial_'+axis]=('Support pen initial '+axis.lower(),value,'m')
    speed=math.sqrt(sum(x*x for x in objects['t10_tape_roll']['motion']['initial_velocity']))
    result['t10_tape_roll.initial_speed']=('Tape roll initial speed',speed,'m/s')
    slab=objects['frozen_tabletop_collision_slab']
    result['frozen_tabletop_collision_slab.friction']=('Surface friction',slab['friction'],'')
    return result


def pattern(label,unit):
    return re.compile(re.escape(label)+r' ([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)'+(r' '+re.escape(unit) if unit else '')+r'\.')


def main():
    OUT.mkdir(exist_ok=True)
    audit={r['canonical_video_id']:r for r in json.loads((EVIDENCE/'SOURCE_AUDIT.json').read_text())['rows']}
    verified_hashes=json.loads((EVIDENCE/'CONFIG_HASH_RECHECK.json').read_text())
    source_hash=sha(SOURCE);stats=collections.Counter();changes=[];examples=[]
    targets={}
    for vid,e in audit.items():
        targets[vid]=expected_fields(e['config'])
        assert e['config_path'] in verified_hashes
    with gzip.open(SOURCE,'rt',encoding='utf8') as src,gzip.open(OUT/'videos.jsonl.gz','wt',encoding='utf8',compresslevel=1) as dst,gzip.open(OUT/'train_final_candidates.jsonl.gz','wt',encoding='utf8',compresslevel=1) as train:
        for line in src:
            row=json.loads(line);original=json.loads(line);vid=row['canonical_video_id']
            if vid in targets:
                fields=targets[vid];e=audit[vid];assert row['sha256']==e['observed_video_sha256']
                before=row['prompt_variants_en'][:];new=before[:];delta=[]
                facts={f[0]:f for f in row['parameter_facts']}
                assert set(facts)<=set(fields),(vid,set(facts)-set(fields))
                for key,fact in facts.items():
                    label,value,unit=fields[key]
                    if not math.isclose(float(fact[-2]),value,rel_tol=1e-12,abs_tol=1e-12):
                        delta.append({'key':key,'old':fact[-2],'new':value})
                    fact[-2]=value
                selected=row.get('selected_parameter_keys',[])
                for key in selected:
                    assert key in fields,(vid,key)
                    label,value,unit=fields[key];p=pattern(label,unit)
                    clause=label+' '+format(value,'.15g')+(' '+unit if unit else '')+'.'
                    for i,text in enumerate(new):
                        assert len(list(p.finditer(text)))==1,(vid,key,i)
                        new[i]=p.sub(lambda _:clause,text)
                opening_changes=[]
                for i,text in enumerate(new):
                    if any(counts(text)[m]>cap for m,cap in MODEL_BUDGETS.items()):
                        lead,tail=text.split('. ',1);assert 'camera' in lead.lower()
                        replacement=['Fixed camera.','Keep camera fixed.','Camera stays fixed.'][i]
                        new[i]=replacement+' '+tail
                        opening_changes.append({'variant':i+1,'before':lead+'.','after':replacement})
                    assert all(counts(new[i])[m]<=cap for m,cap in MODEL_BUDGETS.items()),(vid,i,counts(new[i]))
                row['prompt_variants_en']=new;row['prompt_en']=new[0]
                row['prompt_variant_sha256']=[hashlib.sha256(t.encode()).hexdigest() for t in new]
                row['prompt_sha256']=row['prompt_variant_sha256'][0]
                row['prompt_variant_token_counts']=[counts(t) for t in new];row['prompt_token_counts']=counts(new[0])
                row['config_parameter_alignment']={'status':'all_represented_fields_aligned','authority':'user_selected_configuration',
                    'config_path':e['config_path'],'config_sha256':verified_hashes[e['config_path']],
                    'verified_parameter_fact_keys':list(facts),'verified_prompt_keys':selected,
                    'changes':delta,'camera_opening_changes':opening_changes,
                    'original_prompt_hashes':original['prompt_variant_sha256'],
                    'independent_video_parameter_measurement_claimed':False}
                changes.append({'video_id':vid,**row['config_parameter_alignment'],'old_prompts':before,'new_prompts':new})
                stats['aligned_videos']+=1;stats['aligned_parameter_facts']+=len(facts)
                stats['checked_prompt_values']+=len(selected)*3
                for d in delta:stats['corrected_'+d['key']]+=1
                if len(examples)<2 and (not examples or examples[0]['changes']!=delta):
                    examples.append({'video_id':vid,'changes':delta,'before':before[0],'after':new[0]})
            else:assert row==original
            for key in ['sha256','download','split','source_group_id','config_download','canonical_video_id']:
                assert row.get(key)==original.get(key)
            encoded=json.dumps(row,ensure_ascii=False)+'\n';dst.write(encoded);stats['videos']+=1
            if row.get('split')=='train_final':train.write(encoded);stats['train_final_candidates']+=1
    assert stats['aligned_videos']==120 and stats['videos']==72000 and stats['train_final_candidates']==45357
    # Verify emitted text and metadata independently after closing the export.
    seen=set();checked=0
    with gzip.open(OUT/'videos.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);vid=r['canonical_video_id'];assert vid not in seen;seen.add(vid)
            if vid not in targets:continue
            checked+=1;fields=targets[vid]
            for fact in r['parameter_facts']:
                assert math.isclose(fact[-2],fields[fact[0]][1],rel_tol=1e-12,abs_tol=1e-12)
            assert r['prompt_variant_sha256']==[hashlib.sha256(t.encode()).hexdigest() for t in r['prompt_variants_en']]
            for text in r['prompt_variants_en']:
                for key in r['selected_parameter_keys']:
                    label,value,unit=fields[key];match=list(pattern(label,unit).finditer(text));assert len(match)==1
                    assert math.isclose(float(match[0].group(1)),value,rel_tol=1e-12,abs_tol=1e-12),(vid,key)
                assert all(counts(text)[m]<=cap for m,cap in MODEL_BUDGETS.items())
    assert checked==120 and sha(SOURCE)==source_hash
    (OUT/'CHANGES_120.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf8')
    report={'status':'passed_for_120_bound_t10_videos','counts':dict(stats),'remaining_mismatches_in_checked_fields':0,
        'old_source_preserved_sha256':source_hash,'examples':examples,'active_jobs_or_online_release_changed':False,
        'scope':'120 audited T10 videos; no claim of full 72000 config audit or independent groundtruth measurement',
        'files':{n:sha(OUT/n) for n in ['videos.jsonl.gz','train_final_candidates.jsonl.gz','CHANGES_120.json']}}
    (OUT/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'README.md').write_text('''# T10全部已表达参数与配置对齐

本次修复覆盖已绑定配置的120条T10（40次仿真、三视角）。逐条映射重力、质量、摩擦、恢复系数、文件夹倾角、支撑笔XYZ位置和胶带卷初速；所有parameter_facts逐项核对，三个prompt中全部已选字段逐项核对。修正文本、数值元数据、哈希和tokenizer长度，不只替换单个速度字符串。

入口：videos.jsonl.gz为72000条完整修订目录；train_final_candidates.jsonl.gz为45357条原训练划分候选。CHANGES_120.json记录每条配置路径/哈希、逐字段差异和完整新旧文本，REPORT.json记录复读导出后的校验结果。

配置仍为用户指定的数值依据；没有声称视频独立测量已经完成。本次未改变视频、划分、已有模型结果或在线任务。其余71880条没有被此次配置对齐审计覆盖；Core100独立候选的T10_C05须按其自己的配置绑定单独处理，不能用本批修正覆盖。
''',encoding='utf8')
    pointer={'status':'superseded_by_full_field_config_alignment','manifest':str((OUT/'videos.jsonl.gz').resolve()),'sha256':report['files']['videos.jsonl.gz'],'report':str((OUT/'REPORT.json').resolve())}
    (SOURCE.parent/'FULL_CONFIG_ALIGNMENT.json').write_text(json.dumps(pointer,indent=2),encoding='utf8')
    (ROOT/'review/prompt_revision_20261102/CONFIG_SPEED_RESOLUTION.json').write_text(json.dumps(pointer,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='examples'}))


if __name__=='__main__':main()
