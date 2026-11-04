"""Apply the author's configuration authority decision, preserving old releases."""
from pathlib import Path
import collections
import gzip
import hashlib
import json
import math
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from physedit.compact_prompt import counts, MODEL_BUDGETS

SRC=ROOT/'review/prompt_revision_20261102/videos.jsonl.gz'
OLD=ROOT/'review/t10_groundtruth_resolution_20261102'
OUT=ROOT/'review/t10_config_speed_resolution_20261102'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    source_hash=sha(SRC)
    audit={r['canonical_video_id']:r for r in json.loads((OLD/'SOURCE_AUDIT.json').read_text())['rows']}
    published={r['video_id']:r for r in json.loads((ROOT/'review/prompt_revision_20261102/T10_conflict_audit.json').read_text())['rows']}
    receipt=[];stats=collections.Counter();over=[]
    with gzip.open(SRC,'rt',encoding='utf8') as src, gzip.open(OUT/'videos.jsonl.gz','wt',encoding='utf8',compresslevel=1) as dst,gzip.open(OUT/'train_final_candidates.jsonl.gz','wt',encoding='utf8',compresslevel=1) as train:
        for line in src:
            r=json.loads(line);vid=r['canonical_video_id'];original=json.loads(line)
            if vid in audit:
                e=audit[vid];config=e['config'];assert e['observed_video_sha256']==r['sha256']
                obj=next(o for o in config['dynamic_objects'] if o['name']=='t10_tape_roll')
                velocity=obj['motion']['initial_velocity'];speed=math.sqrt(sum(x*x for x in velocity))
                assert math.isclose(speed,1.8)
                bound=next(p for p in published[vid]['published_configs'] if p['path']==e['config_path'])
                assert bound['upload_config_record_matches']
                assert bound['motions'][0]['motion']==obj['motion']
                prior=r['prompt_variants_en'][:]
                assert all(t.count('Tape roll initial speed 3 m/s.')==1 for t in prior)
                new=[t.replace('Tape roll initial speed 3 m/s.',f'Tape roll initial speed {speed:g} m/s.') for t in prior]
                shortened=[]
                for i,text in enumerate(new):
                    if any(counts(text)[m]>cap for m,cap in MODEL_BUDGETS.items()):
                        lead,tail=text.split('. ',1)
                        assert 'camera' in lead.lower()
                        replacement=['Fixed camera.','Keep camera fixed.','Camera stays fixed.'][i]
                        new[i]=replacement+' '+tail
                        shortened.append({'variant':i+1,'before':lead+'.','after':replacement})
                assert all(all(counts(t)[m]<=cap for m,cap in MODEL_BUDGETS.items()) for t in new)
                r['prompt_variants_en']=new;r['prompt_en']=new[0]
                r['prompt_variant_sha256']=[hashlib.sha256(t.encode()).hexdigest() for t in new]
                r['prompt_sha256']=r['prompt_variant_sha256'][0]
                r['prompt_variant_token_counts']=[counts(t) for t in new];r['prompt_token_counts']=counts(new[0])
                facts=[f for f in r['parameter_facts'] if f[0]=='t10_tape_roll.initial_speed'];assert len(facts)==1
                facts[0][-2]=speed
                record={'video_id':vid,'video_sha256':r['sha256'],'old_speed_mps':3.0,'new_speed_mps':speed,
                        'config_path':e['config_path'],'config_sha256':bound['sha256'],'velocity_world_mps':velocity,
                        'authority':'user_directed_published_configuration','independently_measured_from_video':False,
                        'original_prompts':prior,'original_prompt_hashes':original['prompt_variant_sha256'],
                        'camera_opening_shortened_for_budget':shortened,
                        'new_prompt_hashes':r['prompt_variant_sha256'],'split':r['split']}
                r['config_speed_resolution']=record
                rev=r.get('prompt_revision',{})
                rev['issues']=[i for i in rev.get('issues',[]) if i!='parameter_conflict_original_values_preserved']
                rev['status']='revised' if not rev['issues'] else 'needs_review'
                rev['speed_conflict_resolved_by']='author_selected_config_authority'
                r['prompt_revision']=rev
                r['t10_speed_use_status']='configuration_value_adopted_hold_withdrawn'
                for i,tc in enumerate(r['prompt_variant_token_counts']):
                    if any(tc[m]>cap for m,cap in MODEL_BUDGETS.items()):over.append({'video_id':vid,'variant':i+1,'token_counts':tc})
                receipt.append(record);stats['corrected']+=1;stats['restored_'+r['split']]+=1
                assert all('Tape roll initial speed 3 m/s.' not in t for t in new)
            for key in ['canonical_video_id','sha256','download','split','source_group_id','config_download']:
                assert r.get(key)==original.get(key)
            encoded=json.dumps(r,ensure_ascii=False)+'\n';dst.write(encoded);stats['all']+=1
            if r.get('split')=='train_final':train.write(encoded);stats['train_final_candidates']+=1
    assert stats['all']==72000 and stats['corrected']==120 and stats['restored_train_final']==48
    assert stats['train_final_candidates']==45357
    assert source_hash==sha(SRC)
    # Reopen exports and verify actual membership and corrected triples.
    for filename in ['videos.jsonl.gz','train_final_candidates.jsonl.gz']:
        seen=set();fixed=0
        with gzip.open(OUT/filename,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);vid=r['canonical_video_id'];assert vid not in seen;seen.add(vid)
                if vid in audit:
                    fixed+=1;assert len(r['prompt_variants_en'])==3
                    assert r['prompt_variant_sha256']==[hashlib.sha256(t.encode()).hexdigest() for t in r['prompt_variants_en']]
                    assert all('Tape roll initial speed 1.8 m/s.' in t for t in r['prompt_variants_en'])
        assert fixed==(120 if filename=='videos.jsonl.gz' else 48)
    (OUT/'CHANGES_120.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'TOKEN_BUDGET_REVIEW.json').write_text(json.dumps(over,indent=2),encoding='utf8')
    report={'counts':dict(stats),'speed_mps':1.8,'authority':'user_selected_published_configuration',
            'video_measurement_claimed':False,'speed_holds_withdrawn':120,'previous_versions_preserved':True,
            'old_source_manifest_sha256':source_hash,'active_jobs_or_online_release_changed':False,
            'token_budget_review_variants':len(over),'core100_t10_c05_position_conflict_resolved':False,
            'files':{n:sha(OUT/n) for n in ['videos.jsonl.gz','train_final_candidates.jsonl.gz','CHANGES_120.json']}}
    (OUT/'REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    (OLD/'HOLD_WITHDRAWAL.json').write_text(json.dumps({'status':'superseded','withdrawn_speed_holds':120,'authority':'user instructed adoption of configuration values','replacement_directory':str(OUT),'report':str(OUT/'REPORT.json')},indent=2),encoding='utf8')
    (OUT/'README.md').write_text(f'''# T10配置速度修正

按用户明确决定，以发布配置为数值依据。120个视频三种prompt中的胶带卷初速从3改为1.8 m/s，parameter_facts、文本哈希及真实tokenizer计数同步更新。该值来自配置，没有声称由视频独立测得。

videos.jsonl.gz保留72000条；train_final_candidates.jsonl.gz恢复48条，包含45357条原训练划分候选。撤销此前120条因速度冲突而设置的暂停。旧包和隔离清单保留作历史，以本目录为本次修正入口；旧目录HOLD_WITHDRAWAL.json记录撤销。

CHANGES_120.json保留原prompt、新旧哈希、配置哈希和数值来源。本次只修正速度，视频、来源族及划分不变；未切换现有训练或线上数据。其它原有准入规则继续适用。Core100 T10_C05的独立位置参数冲突未由此次速度修正解决。

速度替换后有{len(over)}个变体超过原短文本预算，详见TOKEN_BUDGET_REVIEW.json；未静默截断或声称全量语义审核完成。
''',encoding='utf8')
    print(json.dumps(report))


if __name__=='__main__':main()
