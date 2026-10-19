"""Export auditable event candidates and a review queue; never drop failures."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from physedit.boundary_window import route_observations

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--baseline');a=p.parse_args()
    root=Path(a.run)
    manifest={r['sample_id']:r for r in map(json.loads,(root/'inputs.jsonl').read_text().splitlines())}
    rows={r['sample_id']:r for r in map(json.loads,(root/'event_results.jsonl').read_text().splitlines())}
    queue=[];summary=[]
    for sid,entry in manifest.items():
        r=rows.get(sid,{})
        routing=r.get('routing',{'route':'review','reasons':[r.get('error','missing_result')]})
        trackfile=root.parent/'other_scene_window_probe_20261016'/f"{entry.get('tracking_id',sid)}_tracks.json"
        if r.get('status')=='ok' and trackfile.exists():
            tracks=json.loads(trackfile.read_text())['frames'];boxes={x['frame']:x['bbox_xyxy'] for x in tracks}
            routing=route_observations(r['judgement'],r['frame_indices'],boxes)
        candidate=routing.get('route')=='candidate_usable'
        item={'sample_id':sid,'route':routing.get('route'),'routing':routing,
              'video':entry['video'],'tracking_id':entry.get('tracking_id',sid),'window':entry['window'],
              'duration_s':entry['duration_s'],'target':entry['target'],
              'frame_indices':r.get('frame_indices',[]),'raw':r.get('raw'),
              'human_labels':{'departure':None,'descent':None,'ground_contact':None,'identity_valid':None},
              'human_status':'pending','reviewer_id':None,'review_reason':None,
              'applicability_note':'ground contact not_observed is not a universal negative; retain upstream events'}
        summary.append({'sample_id':sid,'status':r.get('status','missing'),**routing})
        if not candidate:queue.append(item)
    (root/'review_queue.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in queue),encoding='utf-8')
    counts={'total_registered':len(manifest),'completed_calls':len(rows),'candidate_usable':len(manifest)-len(queue),
            'human_review_pending':len(queue),'note':'Development routing counts, not independently validated accuracy. All registered inputs retained.'}
    counts['candidate_event_decisions']={k:sum(s.get('event_routes',{}).get(k)=='candidate_usable' for s in summary) for k in ('departure','descent','landing')}
    counts['ground_contact_not_observed']=sum(s.get('landing_observation')=='not_observed' for s in summary)
    (root/'routing_summary.json').write_text(json.dumps({'counts':counts,'samples':summary},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'counts':counts,'samples':summary},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
