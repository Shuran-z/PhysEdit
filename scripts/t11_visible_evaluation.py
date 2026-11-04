"""Export and score the author-approved observable-event supplement locally."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from annotation_site.t11_visible_events import CONTRACT,EVENTS,VERSION,digest,compare

def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def export(snapshot,audit_path,out):
    snapshot=load(snapshot)
    audits={x['id']:x for x in map(json.loads,audit_path.read_text(encoding='utf8').splitlines())}
    tasks=[t for t in snapshot['tasks']if t['payload']['clip_id'].startswith('T11_')]
    assert len(tasks)==180 and len({t['id']for t in tasks})==180
    refs={};outputs=[]
    for task in tasks:
        p=task['payload'];a=audits[task['id']];cid=p['clip_id']
        # One fixed five-second window for the supplement, including long outputs.
        # Short clips are registered as incomplete; they do not acquire a negative.
        horizon=5.0
        if cid not in refs:
            # Clock is the original native reference, not a generated proxy.
            refs[cid]=dict(id=cid,role='reference',video_sha256=a['reference_video_sha256'],
                protocol_sha256=digest(CONTRACT),start_frame=a['condition_frame_index'],
                end_frame=a['condition_frame_index']+math.floor(horizon*30+1e-6),
                fps=30,native_frames=210,horizon_s=horizon,labels={},
                admission='new_visible_event_reference_review_required',legacy_labels_inherited=False)
        assert refs[cid]['horizon_s']==horizon
        outputs.append(dict(id=task['id'],clip_id=cid,role='output',model=p['model'],
            seed=p['seed'],prompt_variant=p['prompt_variant'],video_sha256=p['video_sha256'],
            protocol_sha256=digest(CONTRACT),start_frame=0,end_frame=math.floor(horizon*p['fps']+1e-6),
            fps=p['fps'],native_frames=p['frames'],horizon_s=horizon,
            original_protocol_sha256=p['protocol_sha256'],original_annotation_window_s=p['window_s'],
            original_annotations_sha256=digest(task['annotations']),labels={}))
    result=dict(version=VERSION,protocol=CONTRACT,protocol_sha256=digest(CONTRACT),
        references=list(refs.values()),outputs=outputs,original_labels_modified=False,
        source_task_snapshot_sha256=digest(snapshot['tasks']),scope='local_visible_event_supplement',
        legacy_numeric_scores_replaced=False,NearAcc=None,PairAcc=None)
    out.mkdir(parents=True,exist_ok=True)
    (out/'REGISTRY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    templates=[]
    for b in result['references']+outputs:
        for event,rule in EVENTS.items():
            templates.append(dict(id=b['id'],event=event,**{k:b[k]for k in ['video_sha256','protocol_sha256','start_frame','end_frame','fps']},
                actor_ids=rule['actors'],label=None,frames=[],occurrence_frames=[],artifacts=[],
                reviewer_type='Codex_visual_review_not_independent_human_gold'))
    (out/'OBSERVATION_TEMPLATE.json').write_text(json.dumps(templates,ensure_ascii=False,indent=2),encoding='utf8')
    return result

def observations(path,registry,artifact_root):
    if path is None:return {}
    bindings={x['id']:x for x in registry['references']+registry['outputs']};seen={};root=artifact_root.resolve()
    for r in load(path):
        key=(r['id'],r['event'])
        if key in seen:raise ValueError('Duplicate observation')
        if r['id']not in bindings or r['event']not in EVENTS:raise ValueError('Unregistered member/event')
        if r.get('reviewer_type')!='Codex_visual_review_not_independent_human_gold':raise ValueError('Missing reviewer provenance')
        witnesses=r.get('artifacts',[]);witness_frames=set()
        if not witnesses:raise ValueError('No native evidence artifacts')
        for a in witnesses:
            p=(root/a['path']).resolve()
            if not p.is_relative_to(root)or not p.is_file()or sha(p)!=a['sha256']:raise ValueError('Artifact missing or changed')
            if a['source_video_sha256']!=bindings[r['id']]['video_sha256']:raise ValueError('Artifact video identity mismatch')
            witness_frames.update(a['frames'])
        if not set(r['frames']).issubset(witness_frames):raise ValueError('Unwitnessed claimed frames')
        seen[key]={**r,'evidence_artifacts_verified':True}
    return seen

def score(registry,reviews):
    refs={x['id']:x for x in registry['references']};rows=[]
    for b in registry['outputs']:
        for e in EVENTS:
            r=refs[b['clip_id']];a=reviews.get((r['id'],e));o=reviews.get((b['id'],e))
            status=(dict(correct=None,status='insufficient_native_window')if b['end_frame']>=b['native_frames']else
                compare(a,o,e,r,b)if a is not None and o is not None else dict(correct=None,status='new_reference_review_missing'if a is None else 'new_output_review_missing'))
            rows.append(dict(id=b['id'],clip_id=b['clip_id'],model=b['model'],event=e,**status))
    return dict(version=VERSION,registered_outputs=len(registry['outputs']),registered_event_slots=len(rows),
        scored_event_slots=sum(x['correct']is not None for x in rows),
        quality_failure_slots=sum(x['status']=='quality_failure_physical_score'for x in rows),
        quality_policy='Strict foreign-actor/identity-loss gate: physical correctness 0; event labels remain null, never relabeled as negative.',rows=rows,
        original_labels_modified=False,legacy_numeric_scores_replaced=False,NearAcc=None,PairAcc=None)

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--snapshot',type=Path);p.add_argument('--audit',type=Path)
    p.add_argument('--reviews',type=Path);p.add_argument('--artifact-root',type=Path,default=ROOT/'annotation_site')
    a=p.parse_args()
    registry=export(a.snapshot,a.audit,a.out)if a.snapshot and a.audit else load(a.out/'REGISTRY.json')
    result=score(registry,observations(a.reviews,registry,a.artifact_root))
    (a.out/'RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items()if k!='rows'}))

if __name__=='__main__':main()
