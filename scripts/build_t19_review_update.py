"""Apply only recorded hash-bound T19 adjudications; keep unresolved work explicit."""
import collections
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
from refresh_72000_inventory import admission
ROOT=REPO.parent/'release_72000_active'
OUT=ROOT/'t19_review_20261029'
PREFIX='releases/72000_release_candidate_20261029'


def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=True),encoding='utf8')


def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt',encoding='utf8') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=True)+'\n')


def main():
    active=json.loads((ROOT/'ACTIVE_CATALOG.json').read_text());raw=Path(active['manifest']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==active['manifest_sha256']
    rows=list(map(json.loads,gzip.decompress(raw).decode().splitlines()))
    results=json.loads((OUT/'results.json').read_text())
    evidence={v['video_id']:v for g in results for v in g['videos']}
    selected=json.loads((OUT/'selected_visual_reviews.json').read_text())
    # Explicitly inspected dense three-view sheets: never infer other decisions
    # from this small inspected set or from full-decode/state PASS.
    inspected={v['video_id'] for g in selected for v in g['videos']}
    assert len(inspected)==9
    audit_hash=hashlib.sha256((OUT/'results.json').read_bytes()).hexdigest()
    decisions=[];plan=[]
    for row in rows:
        v=evidence.get(row['video_id'])
        if v is None:continue
        assert row['engine']=='genesis' and row['scene']=='T19'
        assert row['sha256']==v['video_sha256']==v['expected_sha256']
        assert v['decoded_frames']==v['state_frames']==210 and v['all_state_finite']
        observed=row['video_id'] in inspected
        decision='accept' if observed else 'review'
        proof={'video_id':row['video_id'],'video_sha256':row['sha256'],
            'decision':decision,'reviewer':'assistant_visual_and_state_review_20261029' if observed else 'decode_state_audit_v1',
            'evidence':[{'path':'t19_review/results.json','sha256':audit_hash},
                        {'path':v['dense_sheet'],'sha256':v['dense_sheet_sha256']},
                        {'path':v['metadata_path'],'sha256':v['metadata_sha256']}],
            'checks':dict.fromkeys(['identity_geometry','contact_physics','declared_controls','event_visibility','temporal_coverage'],True if observed else None),
            'inspection_scope':'dense activation/contact frames, later temporal samples, synchronized three views and original state/config' if observed else 'full video decode/hash/state audit; visual adjudication not completed',
            'reason':'Objects retain identity; observed response and original state/config agree; no visible lasting penetration in inspected dense event sequence.' if observed else 'Full visual/physical adjudication remains pending; technical checks do not grant acceptance.',
            'frame_sampling_is_not_full_video_playback':True}
        row['visual_physics_adjudication']=proof
        row['quality_reactivation']={k:proof[k] for k in ['video_sha256','reviewer','evidence','decision']}
        row['quality_reactivation']['authorization']='author_20261029_review_genesis1830_keep_qualified'
        row['quality_reactivation']['original_admission']='UNUSABLE_RETIRED'
        row['quality_admission_status']=admission(row)
        decisions.append(proof)
        original=copy.deepcopy(row.get('source_download') or row['download'])
        plan.append({'video_id':row['video_id'],'sha256':row['sha256'],
                     'source_download':original,'destination':row['canonical_path']})
    assert len(decisions)==1830
    # Preserve original media bindings until the new destination has been verified.
    quality=collections.Counter(r['quality_admission_status'] for r in rows)
    summary={'total':len(rows),'usable':sum(n for s,n in quality.items() if s.startswith('USABLE_')),
             'pending':quality['PENDING_REVIEW'],'retired':quality['UNUSABLE_RETIRED'],
             'quality_states':dict(quality),'genesis_t19':{'technical_audit_complete':1830,'visual_accepted':9,'visual_pending':1821,'confirmed_rejected':0},
             'isaac_t19':{'retired':960,'replacement_performed':False},'full_visual_review_complete':False}
    assert summary['usable']+summary['pending']+summary['retired']==72000
    dest=OUT/'metadata'/PREFIX
    write(dest/'videos.jsonl.gz',rows);write(dest/'usable_videos.jsonl.gz',[r for r in rows if r['quality_admission_status'].startswith('USABLE_')])
    write(dest/'t19_review/adjudications.jsonl.gz',decisions)
    write(dest/'t19_review/technical_results.jsonl.gz',evidence.values())
    dump(dest/'t19_review/status.json',summary)
    dump(OUT/'summary.json',summary);dump(OUT/'copy_plan.json',plan)
    dump(OUT/'base_catalog.json',active)
    print(json.dumps(summary))


if __name__=='__main__':main()
