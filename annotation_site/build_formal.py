"""Extend the previously frozen 3503 choices into 3600 remote-media task slots."""
import argparse
import collections
import hashlib
import json
import random
from pathlib import Path
from formal_protocols import TARGETS,observation_protocol
from store import ASSIGNMENT_QUOTAS
from workflow import validate_task


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build(root):
    out=Path(root);info=json.loads((out/'hf_blobs.json').read_text(encoding='utf-8'))
    old_info=json.loads((out/'hf_old_blobs.json').read_text(encoding='utf-8'))
    old_path=Path('review/label_site_deploy_20261021/random_sampling_plan_single_review_v2.json')
    old=json.loads(old_path.read_text(encoding='utf-8'))
    rows=[json.loads(l) for l in (out/'metadata.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    by=collections.defaultdict(list)
    for r in rows:by[r['model'],r['video_id']].append(r)
    blobs={r['rfilename']:r for r in info['siblings']};old_blobs={r['rfilename']:r for r in old_info['siblings']}
    chosen=collections.defaultdict(set)
    for s in old['slots']:
        if s['selected']:chosen[s['model'],s['clip_id']].add((s['selected']['seed'],s['selected']['annotation']))
    rng=random.Random(20261023);slots=json.loads(json.dumps(old['slots']));added=[]
    for s in slots:
        if s['selected']:continue
        candidates=sorted([r for r in by[s['model'],s['clip_id']] if (r['seed'],r['annotation']) not in chosen[s['model'],s['clip_id']]],key=lambda r:(r['seed'],r['annotation'],r['file_name']))
        if not candidates:raise ValueError('库存不足：'+str((s['model'],s['clip_id'])))
        s['selected']=rng.choice(candidates);s['status']='selected'
        chosen[s['model'],s['clip_id']].add((s['selected']['seed'],s['selected']['annotation']));added.append((s['model'],s['clip_id'],s['slot']))
    pilot=json.loads(Path('review/label_site_deploy_20261021/package_single_v2/pilot_manifest.json').read_text(encoding='utf-8'))
    t15=json.loads(json.dumps(pilot['tasks'][0]['protocol']));t15['target_en']='Track the initial closed gray laptop, the green book and the initial phone on the floor. Never substitute a newly appearing laptop.'
    tasks=[];changed=[]
    for i,s in enumerate(slots):
        r=s['selected'];scene=s['clip_id'][:3]
        catalog=json.loads((Path(__file__).parent/'resources/event_contracts.json').read_text(encoding='utf-8'))
        protocol=catalog['clips'][s['clip_id']]
        # Existing choices retain their original immutable bytes, even if a path was overwritten later.
        preserved=bool(old['slots'][i]['selected']);blob=(old_blobs if preserved else blobs)[r['file_name']]
        rev=old_info['sha'] if preserved else info['sha'];h=blob['lfs']['sha256']
        if preserved and r['file_name'] in blobs and blobs[r['file_name']]['lfs']['sha256']!=h:changed.append(r['file_name'])
        duration=(r['frames']-1)/r['fps'];window=min(5.,duration) if scene=='T15' else duration
        task={'id':f"f3600_{i+1:04d}",'model':r['model'],'clip_id':s['clip_id'],'seed':r['seed'],'prompt_variant':r['annotation'],
          'primary_id':s['primary_id'],'reviewer_id':'','review_policy':'vlm_human_dispute_only_v2',
          'fps':r['fps'],'duration_s':duration,'window_s':window,'frames':r['frames'],'video_sha256':h,'media_file':h+'.mp4',
          'remote_media':{'repository':'phy2/phy2-benchmark-generations','revision':rev,'path':r['file_name'],
                          'lfs_sha256':h,'size':blob['size'],'verification':'pinned_hf_lfs_metadata'},
          'protocol':protocol,'protocol_sha256':hashlib.sha256(json.dumps(protocol,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
          'vlm_required':True,'machine':{'pipeline_status':'pending','judge':'Qwen3.5-9B; scene-integrity-v2; 13 supplied frames'},
          'reference':{'admission':'pending','boundary':{'status':'unavailable'},'pair_status':'not_registered',
                       'scope':'No reference answer inferred from prompt, scene identifier or model output.'},
          'source':{'generation_metadata':r,'frozen_slot':s['slot'],'old_choice_preserved':preserved}}
        validate_task(task,out/'no-media');tasks.append(task)
    assert len(tasks)==3600 and len({(t['model'],t['clip_id'],t['seed'],t['prompt_variant']) for t in tasks})==3600
    assert dict(collections.Counter(t['primary_id'] for t in tasks))==ASSIGNMENT_QUOTAS
    package={'batch':{'id':'formal3600_v1','name':'正式3600条 · VLM辅助人工复核','mode':'formal',
      'note':'HF固定版本直连，服务器不保存正式视频。VLM先评，人工复核一次；仅争议随机抽样20%由管理员二审。临界事件合同、参考、边界与配对未齐备的场景不报临界成绩。',
      'selection':{'prior_plan_sha256':sha(old_path),'preserved':3600-len(added),'added':len(added),'extension_rng_seed':20261023,
                   'old_revision':old_info['sha'],'extension_revision':info['sha'],'metadata_sha256':sha(out/'metadata.jsonl'),
                   'quota':ASSIGNMENT_QUOTAS,'changed_paths_original_bytes_preserved':changed},
      'media_storage':'remote_hf_only'},'tasks':tasks}
    (out/'formal_manifest.json').write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'tasks':len(tasks),'per_person':dict(collections.Counter(t['primary_id'] for t in tasks)),
      'per_model':dict(collections.Counter(t['model'] for t in tasks)),'preserved':3600-len(added),'added':len(added),
      'unique_media_hashes':len({t['video_sha256'] for t in tasks}),'critical_contract_pending_tasks':sum(not t['protocol']['events'] for t in tasks),
      'manifest_sha256':sha(out/'formal_manifest.json'),'changed_paths_original_bytes_preserved':changed}
    (out/'BUILD_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);build(p.parse_args().root)
