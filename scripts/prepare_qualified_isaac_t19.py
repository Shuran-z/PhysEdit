"""Admit the explicitly inspected existing Isaac T19 triplet; no batch approval."""
import collections
import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO/'scripts'))
from refresh_72000_inventory import admission
ROOT=REPO.parent/'release_72000_active';REVIEW=ROOT/'t19_review_20261029'
OUT=REVIEW/'isaac_admission';PREFIX='releases/72000_release_candidate_20261029'


def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=True,indent=2),encoding='utf8')


def write(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,'wt',encoding='utf8') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=True)+'\n')


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    base=load(ROOT/'ACTIVE_CATALOG.json');path=Path(base['manifest'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==base['manifest_sha256']
    rows=list(map(json.loads,gzip.open(path,'rt',encoding='utf8')))
    selected=load(REVIEW/'isaac_existing_selection.json');audit=REVIEW/'isaac_existing_review'
    records={r['camera']:r for r in load(audit/'records.json')};checks=load(audit/'parameter_check.json')
    assert len(selected)==3 and all(not r['mismatches'] for r in checks)
    source_receipt=load(audit/'complete.json');source_request=load(audit/'request.json')
    input_hash=hashlib.sha256((audit/'config.json').read_bytes()).hexdigest()
    assert input_hash==source_request['signature']['config_sha256']==source_receipt['files']['input.json']
    assert hashlib.sha256((audit/'qa.json').read_bytes()).hexdigest()==source_receipt['files']['qa.json']
    ids={r['video_id']:r for r in selected};decisions=[];media=[]
    evidence=OUT/'metadata'/PREFIX/'isaac_admission_20261029'
    evidence.mkdir(parents=True,exist_ok=True)
    for p in audit.iterdir():
        if p.is_file():shutil.copy2(p,evidence/p.name)
    for row in rows:
        if row['video_id'] not in ids:continue
        assert row['engine']=='isaac' and row['scene']=='T19' and row['quality_admission_status']=='UNUSABLE_RETIRED'
        rec=records[row['camera']];assert rec['video_sha256']==row['sha256'] and rec['decoded_frames']==210
        assert rec['video_sha256']==source_receipt['files'][row['camera']+'.mp4']
        assert hashlib.sha256((audit/(row['camera']+'_dense.jpg')).read_bytes()).hexdigest()==rec['dense_sheet_sha256']
        proof={'video_id':row['video_id'],'video_sha256':row['sha256'],'decision':'accept',
            'reviewer':'assistant_dense_rgb_review_20261029',
            'evidence':[{'path':'isaac_admission_20261029/'+row['camera']+'_dense.jpg','sha256':rec['dense_sheet_sha256']},
                        {'path':'isaac_admission_20261029/config.json','sha256':hashlib.sha256((audit/'config.json').read_bytes()).hexdigest()},
                        {'path':'isaac_admission_20261029/qa.json','sha256':hashlib.sha256((audit/'qa.json').read_bytes()).hexdigest()}],
            'checks':dict.fromkeys(['identity_geometry','contact_physics','declared_controls','event_visibility','temporal_coverage'],True),
            'method':'dense motion-frame RGB review across synchronized cameras plus original source physics QA and exact input comparison',
            'rgb_frame_indices':list(range(0,32,2))+[40,50,60,90,120,150,180,200,209],
            'reason':'A single coherent can bypasses the tissue box and settles; target remains supported. No persistent duplicated can bodies, identity loss, scene corruption or visible intersection in reviewed motion sequence. Ordinary transient motion softness is not counted as object duplication.',
            'limits':'Full 210-frame decode; RGB inspection uses dense motion frames and temporal samples, not full-frame-by-frame playback. Original source QA is carried over, not recomputed physics. Original state file not present in delivered directory; no new state-based score or critical truth granted.'}
        row['visual_physics_adjudication']=proof
        row['quality_reactivation']={k:copy.deepcopy(proof[k]) for k in ['video_sha256','decision','reviewer','evidence']}
        row['quality_reactivation'].update(authorization='author_20261029_use_qualified_isaac_t19',original_admission='UNUSABLE_RETIRED',mode='exact_existing_video_reactivation_not_new_render')
        row['quality_admission_status']=admission(row)
        row['state_availability_note']='Original state SHA receipt retained; state file not present in delivered directory. Recover state before state-dependent evaluation.'
        decisions.append(proof);media.append({'video_id':row['video_id'],'source':row['local_source'],'sha256':row['sha256'],'destination':row['canonical_path']})
    assert len(decisions)==3
    c=collections.Counter(r['quality_admission_status'] for r in rows)
    summary={'total':72000,'usable':sum(n for k,n in c.items() if k.startswith('USABLE_')),'pending':c['PENDING_REVIEW'],'retired':c['UNUSABLE_RETIRED'],'quality_states':dict(c),'isaac_t19_newly_accepted':3,'isaac_t19_remaining_retired':957,'new_render_substitution':False,'original_video_and_prompt_hashes_preserved':True,'core100_changed':False}
    assert summary['usable']==32880 and summary['pending']==38163 and summary['retired']==957
    write(OUT/'metadata'/PREFIX/'videos.jsonl.gz',rows);write(OUT/'metadata'/PREFIX/'usable_videos.jsonl.gz',[r for r in rows if r['quality_admission_status'].startswith('USABLE_')])
    write(evidence/'decisions.jsonl.gz',decisions);dump(evidence/'status.json',summary)
    dump(OUT/'base_catalog.json',base);dump(OUT/'media_plan.json',media);dump(OUT/'summary.json',summary)
    print(json.dumps(summary))


if __name__=='__main__':main()
