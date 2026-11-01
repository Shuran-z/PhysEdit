"""Prepare the six-video pilot, or freeze an equal-size random selection plan."""
import argparse
import hashlib
import json
import random
import shutil
from pathlib import Path
from store import ASSIGNMENTS, ASSIGNMENT_QUOTAS, MODEL_OWNER, Store, assign_formal_slots


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


ZH = {
 'book_contacts_laptop':('书本接触初始笔记本','观察窗内，指定绿色书本与初始灰色闭合笔记本发生可确认的物理接触。仅靠近、遮挡或像素重叠不足以确认。'),
 'laptop_leaves_table':('笔记本完全脱离原桌面支撑','初始灰色笔记本完全失去原桌面支撑。部分越缘、倾斜或仍与桌边接触不等于完全脱离。'),
 'laptop_descends':('脱离后下落','同一初始笔记本在完全脱离原桌面后，至少两个实际时间点显示向下运动。不要求落地；不能用后来新出现的笔记本替代。'),
 'laptop_contacts_phone':('笔记本接触初始地面手机','同一初始笔记本与初始位于桌子右下方地面的手机发生可确认接触。相邻或重叠不足以确认。'),
 'phone_moves_after_contact':('接触后手机移动','在可确认的笔记本—手机接触后，原地面手机相对初始位置发生可见移动。仅镜头运动不算。'),
}


def pilot(source, output):
    source=Path(source);out=Path(output);(out/'media').mkdir(parents=True,exist_ok=True)
    jobs=[json.loads(l) for l in (source/'event_jobs.jsonl').read_text(encoding='utf-8').splitlines()]
    quality={r['sample_id']:r for r in map(json.loads,(source/'quality_predictions.jsonl').read_text().splitlines())}
    routes={r['sample_id']:r['route'] for r in json.loads((source/'quality_routes.json').read_text())}
    events={r['sample_id']:r for r in map(json.loads,(source/'event_predictions.jsonl').read_text().splitlines())}
    sel=json.loads((source/'selected.json').read_text());tasklist=[]
    reviewer={('HunyuanVideo-1.5','T15_C03'):'r01',('HunyuanVideo-1.5','T15_C04'):'r02',('HunyuanVideo-1.5','T15_C05'):'r04',
              ('LTX-Video-2B','T15_C03'):'r06',('LTX-Video-2B','T15_C04'):'r07',('LTX-Video-2B','T15_C05'):'r01'}
    for j in jobs:
        sid=j['sample_id'];r=next(x for x in sel if x['model']+'__'+x['video_id']==sid)
        src=source/'media'/(sid+'.mp4');h=sha(src);assert h==j['video_sha256']
        dest=out/'media'/(h+'.mp4')
        if not dest.exists():shutil.copyfile(src,dest)
        protocol={'version':'t15-observation-pilot-v1','status':'diagnostic',
                  'target':'初始画面中，绿色书本右侧、桌面上的灰色闭合笔记本电脑。其他参与对象是该绿色书本，以及初始位于桌子右下方地面的黑色手机。请追踪最初这些对象，不要以后来出现的同类物体替代。',
                  'events':{key:{**d,'name':ZH[key][0],'definition_zh':ZH[key][1],'applicable':True} for key,d in j['events'].items()}}
        clip=r['video_id'];truth={'book_contacts_laptop':1,'laptop_leaves_table':1,'laptop_descends':1,
                               'laptop_contacts_phone':int(clip!='T15_C04'),'phone_moves_after_contact':int(clip!='T15_C04')}
        task={'id':('pilot_h' if r['model'].startswith('Hunyuan') else 'pilot_l')+clip[-2:],
              'model':r['model'],'clip_id':clip,'prompt_variant':r['annotation'],'seed':r['seed'],'primary_id':'r01' if r['model']=='HunyuanVideo-1.5' and clip=='T15_C03' else MODEL_OWNER[r['model']],
              'reviewer_id':'','review_policy':'vlm_human_dispute_only_v2','media_file':h+'.mp4','video_sha256':h,'fps':r['fps'],
              'duration_s':(r['frames']-1)/r['fps'],'window_s':5.0,'protocol':protocol,
              'protocol_sha256':hashlib.sha256(json.dumps(protocol,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
              'source':{'repository':'phy2/phy2-benchmark-generations','revision':'a9c487a6803a0e7e559d7a4bc60cbf41367780b0','file_name':r['file_name'],'condition_frame_index':4},
              'registration_sample_id':sid,
              'machine':{'quality_prediction':quality.get(sid),'event_prediction':events.get(sid),'quality_route':routes[sid],
                         'judge':'Qwen3.5-9B local; original quality/event prompts and 13-frame sampling',
                         'event_accepted_count':0,'source_artifact':'core100_boundary_pilot_20261021'},
              'reference':{'admission':'pending','target_event':'laptop_contacts_phone','events':truth,
                           'required_order':[['book_contacts_laptop','laptop_leaves_table'],['laptop_leaves_table','laptop_descends'],['laptop_contacts_phone','phone_moves_after_contact']],
                           'boundary':{'status':'unavailable'},'pair_status':'candidate_not_admitted','source_records_sha256':sha(source/'reference_source_records.json'),
                           'scope':'Original source audit plus sampled visual diagnostics; not admitted for formal NearAcc or full-chain claims'}}
        tasklist.append(task)
    batch={'id':'pilot6','name':'六条试跑 · T15','mode':'pilot','note':'六条诊断样本。VLM先评、一次人工复核；仅争议池随机抽样20%由管理员二审。未抽中的争议保留待定。'}
    package={'batch':batch,'tasks':tasklist};(out/'pilot_manifest.json').write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
    qa=json.loads(json.dumps(package));qa['batch']={'id':'qa6','name':'QA流程验收 · 不计分','mode':'qa','note':'模拟操作与标签，仅用于验证登录、保存、独立复审、仲裁和导出。不可合并正式人工标注。'}
    for t in qa['tasks']:t.update(id=t['id'].replace('pilot_','qa_'),primary_id='qa_primary',reviewer_id='qa_review',review_policy='legacy_dual_review')
    (out/'qa_manifest.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pilot_tasks':len(tasklist),'media_files':len(list((out/'media').glob('*.mp4')))}))


def sample(metadata, output, rng_seed):
    """Equal per-model AND per-test-case coverage; no quality-dependent reselection."""
    rng=random.Random(rng_seed);rows=[json.loads(l) for l in Path(metadata).read_text(encoding='utf-8').splitlines() if l.strip()]
    buckets={};duplicates=set()
    for r in rows:
        key=(r['model'],r['video_id'],r['seed'],r['annotation'])
        if key in duplicates:raise ValueError('清单含重复生成组合')
        duplicates.add(key)
        if r['model'] not in MODEL_OWNER or r['annotation'] not in (1,2,3):continue
        buckets.setdefault((r['model'],r['video_id']),[]).append(r)
    slots=[];owners=list(ASSIGNMENTS)
    for model in MODEL_OWNER:
        owner=MODEL_OWNER[model];reviewer=owners[(owners.index(owner)+1)%len(owners)]
        for scene in range(1,21):
            for case in range(1,6):
                clip=f'T{scene:02d}_C{case:02d}';available=sorted(buckets.get((model,clip),[]),key=lambda r:(r['seed'],r['annotation'],r['file_name']))
                chosen=rng.sample(available,min(3,len(available)))
                for i in range(3):
                    slots.append({'model':model,'clip_id':clip,'slot':i+1,'primary_id':owner,'reviewer_id':reviewer,
                                  'status':'selected' if i<len(chosen) else 'inventory_shortfall','selected':chosen[i] if i<len(chosen) else None})
    assign_formal_slots(slots)
    assert all(not s['reviewer_id'] for s in slots)
    payload={'policy':{'total_target':3600,'per_model':300,'per_source':3,'selection_rng_seed':rng_seed,
                       'assignment_version':'quota-520-500-single-v2','assignment_quotas':ASSIGNMENT_QUOTAS,
                       'review_assignment':'one VLM-assisted human review per video; 520/500 TOTAL per member; uniform 20% dispute sample reviewed by admin; other disputes remain pending',
                       'metadata_sha256':sha(metadata),'without_replacement':True,'generation_seed_prompt':'random_from_available_unique_combinations',
                       'shortfall_policy':'retain vacant slots; no cross-source/model substitution; next inventory extension requires a new version and does not resample existing choices'},
             'selected_count':sum(s['status']=='selected' for s in slots),'slots':slots}
    Path(output).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'target':3600,'selected':payload['selected_count'],'shortfall':3600-payload['selected_count']}))


def main():
    p=argparse.ArgumentParser();sp=p.add_subparsers(dest='command',required=True)
    a=sp.add_parser('pilot');a.add_argument('--source',required=True);a.add_argument('--output',required=True)
    a=sp.add_parser('sample');a.add_argument('--metadata',required=True);a.add_argument('--output',required=True);a.add_argument('--rng-seed',required=True,type=int)
    a=sp.add_parser('init');a.add_argument('--data-dir',required=True);a.add_argument('--invitations',required=True);a.add_argument('--qa',action='store_true')
    a=sp.add_parser('import');a.add_argument('--data-dir',required=True);a.add_argument('--manifest',required=True)
    a=p.parse_args()
    if a.command=='pilot':pilot(a.source,a.output)
    elif a.command=='sample':sample(a.metadata,a.output,a.rng_seed)
    elif a.command=='init':
        # Private one-time invitation delivery file; never served by the web application.
        f=Path(a.invitations)
        if f.exists():raise FileExistsError('邀请文件已存在，不能覆盖')
        f.parent.mkdir(parents=True,exist_ok=True)
        invitations=Store(Path(a.data_dir)/'annotations.sqlite3').provision(a.qa)
        f.write_text(json.dumps(invitations,ensure_ascii=False,indent=2),encoding='utf-8');f.chmod(0o600)
        print(json.dumps({'created_accounts':len(invitations)}))
    else:
        Store(Path(a.data_dir)/'annotations.sqlite3').import_batch(json.loads(Path(a.manifest).read_text(encoding='utf-8')),Path(a.data_dir)/'media')
        print('IMPORTED')


if __name__=='__main__':main()
