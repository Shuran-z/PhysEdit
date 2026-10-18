"""Two independent judge calls, immutable roster, human-confirmed scoring export."""
import argparse
import json
import math
import subprocess
from pathlib import Path
from .boundary import digest, read_rows, write_rows, write_json, score


def index(path):
    return {r['sample_id']:r for r in read_rows(path)} if path else {}


def evidence(record, horizon, minimum=1, threshold=.9):
    c=record.get('confidence');times=record.get('evidence_times_s')
    return (type(c) in (int,float) and math.isfinite(c) and threshold<=c<=1
            and isinstance(times,list) and all(type(t) in (int,float) and math.isfinite(t) and 0<=t<=horizon for t in times)
            and len(set(times))>=minimum and isinstance(record.get('reason'),str) and bool(record['reason'].strip()))


def quality_route(pred,job,threshold):
    q=pred.get('quality',{})
    if not isinstance(q,dict):return 'review'
    if pred.get('status')!='ok' or not evidence(q,job['window_s'],threshold=threshold):return 'review'
    if q.get('status')=='measurable' and q.get('failure')=='none' and q.get('target_integrity')=='intact' and q.get('support_integrity')=='intact':return 'pass'
    if q.get('status')=='unmeasurable' and q.get('failure') in ('fusion','identity_loss','severe_corruption') and evidence(q,job['window_s'],2,threshold):return 'auto_rejected'
    return 'review'


def checked_predictions(path,jobs):
    predictions=index(path);known={j['sample_id']:j for j in jobs}
    if set(predictions)-set(known):raise ValueError('unknown or unscheduled prediction IDs')
    for sid,p in predictions.items():
        if p.get('video_sha256')!=known[sid]['video_sha256']:raise ValueError('prediction video hash mismatch')
    return predictions


def invoke(command,manifest,output,log,timeout):
    if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):raise ValueError('judge command must be argv list')
    argv=[x.replace('{manifest}',str(manifest)).replace('{output}',str(output)) for x in command]
    try:
        with log.open('x',encoding='utf-8') as stream:
            code=subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout,check=False).returncode
        return {'returncode':code}
    except (OSError,subprocess.TimeoutExpired) as exc:return {'error':str(exc)}


def run_pipeline(run_dir,protocol_path,out_dir,quality_file=None,event_file=None,reviews_file=None,execute=False):
    root=Path(run_dir).resolve();out=Path(out_dir).resolve()
    protocol=json.loads(Path(protocol_path).read_text(encoding='utf-8'))
    threshold=protocol.get('confidence_threshold',.9)
    if type(threshold) not in (int,float) or not 0<=threshold<=1:raise ValueError('invalid threshold')
    snapshots=json.loads((root/'snapshot_hashes.json').read_text(encoding='utf-8'))
    if any(digest(root/name)!=value for name,value in snapshots.items()):raise ValueError('registration changed')
    keys=index(root/'answers.jsonl');observed=index(root/'observed_rows.jsonl');inputs=index(root/'inputs.jsonl')
    definitions=protocol['samples']
    if set(definitions)!=set(keys):raise ValueError('protocol must cover whole roster')
    reviews=index(reviews_file)
    if set(reviews)-set(keys):raise ValueError('unknown reviewer sample')
    jobs=[]
    for sid,key in keys.items():
        d=definitions[sid];events=d['events']
        if set(events)!=set(key['events']):raise ValueError('protocol events must match registered event names')
        if not d.get('target') or any(not isinstance(v,dict) or not v.get('definition') or type(v.get('minimum_evidence_times',1)) is not int or v.get('minimum_evidence_times',1)<1 for v in events.values()):raise ValueError('event definitions required')
        obs=observed.get(sid,{})
        if obs.get('status')!='ok':continue
        if digest(obs['video'])!=obs['video_sha256']:raise ValueError('media changed')
        # Explicit allowlist: no answers, parameters, thresholds, reference time or boundary side.
        jobs.append(dict(sample_id=sid,video=str(Path(obs['video']).resolve()),video_sha256=obs['video_sha256'],
            target=d['target'],window_s=inputs[sid]['evaluation_duration_s'],
            events={e:{'definition':v['definition'],'minimum_evidence_times':v.get('minimum_evidence_times',1)} for e,v in events.items()}))
        if d.get('generated_track'):
            track=Path(d['generated_track']).resolve()
            if digest(track)!=d.get('generated_track_sha256'):raise ValueError('generated tracking hash mismatch')
            if json.loads(track.read_text(encoding='utf-8')).get('video_sha256')!=obs['video_sha256']:raise ValueError('tracking belongs to another video')
            jobs[-1].update(generated_track=str(track),generated_track_sha256=d['generated_track_sha256'])
        if 'roi' in d:
            roi=d['roi']
            if not isinstance(roi,list) or len(roi)!=4 or any(type(x) is not int or x<0 for x in roi) or roi[0]>=roi[2] or roi[1]>=roi[3]:raise ValueError('invalid ROI')
            jobs[-1]['roi']=roi
        if sid in reviews:
            rev=reviews[sid]
            if rev.get('video_sha256')!=obs['video_sha256'] or not rev.get('reviewer') or not rev.get('evidence'):raise ValueError('human review must bind hash, reviewer, evidence')
    out.mkdir(parents=True,exist_ok=False)
    write_json(out/'protocol.json',protocol)
    quality_jobs=[{k:v for k,v in j.items() if k!='events'} for j in jobs]
    write_rows(out/'quality_jobs.jsonl',quality_jobs)
    calls={}
    if execute and quality_file is None and quality_jobs:
        quality_file=out/'quality_predictions.jsonl'
        calls['quality']=invoke(protocol['quality_command'],out/'quality_jobs.jsonl',quality_file,out/'quality.log',protocol.get('timeout_seconds',3600))
        if not quality_file.exists():quality_file=None
    qp=checked_predictions(quality_file,quality_jobs)
    write_rows(out/'quality_results.jsonl',list(qp.values()))
    states={j['sample_id']:quality_route(qp.get(j['sample_id'],{}),j,threshold) for j in jobs}
    for sid,rev in reviews.items():
        if sid not in states:raise ValueError('cannot adjudicate missing media')
        if 'quality_status' in rev:
            if rev['quality_status'] not in ('pass','confirmed_failure'):raise ValueError('invalid human quality status')
            states[sid]=rev['quality_status']
    event_jobs=[j for j in jobs if states[j['sample_id']]=='pass']
    write_rows(out/'event_jobs.jsonl',event_jobs)
    if execute and event_file is None and event_jobs:
        event_file=out/'event_predictions.jsonl'
        calls['events']=invoke(protocol['event_command'],out/'event_jobs.jsonl',event_file,out/'events.log',protocol.get('timeout_seconds',3600))
        if not event_file.exists():event_file=None
    ep=checked_predictions(event_file,event_jobs)
    write_rows(out/'event_results.jsonl',list(ep.values()))
    write_rows(out/'human_reviews.jsonl',list(reviews.values()))
    screenings=[];annotations=[];pre=[];queue=[];routing=[];inversion_jobs=[]
    by={j['sample_id']:j for j in jobs}
    for sid,key in keys.items():
        job=by.get(sid);rev=reviews.get(sid,{})
        if job is None:
            routing.append(dict(sample_id=sid,quality='media_unavailable',events={e:'media_unavailable' for e in key['events']}));continue
        state=states[sid];q=qp.get(sid,{}).get('quality',{});q=q if isinstance(q,dict) else {}
        status='pass' if state=='pass' else 'confirmed_failure' if state=='confirmed_failure' else 'suspect'
        screen=dict(sample_id=sid,video_sha256=job['video_sha256'],status=status,method='independent_quality_then_human' if 'quality_status' in rev else 'independent_quality',
            evidence=rev.get('evidence') or q.get('reason') or 'quality_missing_or_invalid',blocked_events=list(key['events']) if status=='confirmed_failure' else [],block_inversion=status=='confirmed_failure')
        if status=='confirmed_failure':screen['reviewer']=rev['reviewer']
        screenings.append(screen)
        if state not in ('pass','confirmed_failure'):queue.append(dict(sample_id=sid,kind='quality',video_sha256=job['video_sha256'],machine_route=state,prediction=q,reviewer=None,evidence=None))
        labels={e:None for e in key['events']};times={};routes={}
        payload=ep.get(sid,{}).get('events',{});payload=payload if isinstance(payload,dict) else {}
        human=rev.get('events',{})
        if not isinstance(human,dict) or set(human)-set(labels):raise ValueError('unknown human event')
        for event,definition in job['events'].items():
            p=payload.get(event,{});p=p if isinstance(p,dict) else {};label=p.get('label')
            route='blocked_quality' if state!='pass' else 'review'
            minimum=definition['minimum_evidence_times']
            if state=='pass' and evidence(p,job['window_s'],minimum,threshold) and p.get('contradictions')==[]:
                if label in ('yes','no'):route='preannotated'
                elif label=='not_observed':route='observation_only'
            if event in human:
                h=human[event]
                if state!='pass':raise ValueError('resolve quality before confirming events')
                if not isinstance(h,dict) or type(h.get('label')) is not int or h['label'] not in (0,1) or not h.get('evidence'):raise ValueError('invalid human event')
                labels[event]=h['label'];route='human_confirmed'
                if h.get('time_s') is not None:
                    t=h['time_s']
                    if type(t) not in (int,float) or not math.isfinite(t) or not 0<=t<=job['window_s']:raise ValueError('invalid event time')
                    times[event]=t
            item=dict(sample_id=sid,event=event,route=route,video_sha256=job['video_sha256'],window_s=job['window_s'],prediction=p,human_label=None,reviewer=None)
            if route=='preannotated':pre.append(item)
            elif route=='review':queue.append(dict(item,kind='event'))
            routes[event]=route
        annotations.append(dict(sample_id=sid,video_sha256=job['video_sha256'],events=labels,event_times_s=times,
            method='human_confirmed' if any(v is not None for v in labels.values()) else 'unannotated',evidence=rev.get('evidence',''),reviewer=rev.get('reviewer')))
        routing.append(dict(sample_id=sid,quality=state,events=routes))
        if state=='pass' and key['inversion']['status']=='eligible':inversion_jobs.append(dict(sample_id=sid,video=job['video'],video_sha256=job['video_sha256'],status='pending_inversion_specific_checks'))
    write_rows(out/'screening.jsonl',screenings);write_rows(out/'annotations.jsonl',annotations)
    write_rows(out/'preannotations.jsonl',pre);write_rows(out/'review_queue.jsonl',queue)
    write_rows(out/'routing.jsonl',routing);write_rows(out/'inversion_candidates.jsonl',inversion_jobs)
    result=score(root,out/'annotations.jsonl',screening=out/'screening.jsonl')
    write_json(out/'scores.json',result)
    receipt=dict(registered=len(keys),quality_scheduled=len(quality_jobs),events_scheduled=len(event_jobs),
        preannotated_event_count=len(pre),review_items=len(queue),inversion_completed=0,
        inversion_candidate_count=len(inversion_jobs),calls=calls,score_policy='human_confirmed_only; pending is not confirmed generation failure',
        source_protocol_sha256=digest(protocol_path),quality_predictions_sha256=digest(quality_file) if quality_file else None,
        event_predictions_sha256=digest(event_file) if event_file else None,reviews_sha256=digest(reviews_file) if reviews_file else None)
    write_json(out/'receipt.json',receipt)
    return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run-dir','protocol','out-dir'):p.add_argument('--'+name,required=True)
    for name in ('quality-predictions','event-predictions','reviews'):p.add_argument('--'+name)
    p.add_argument('--execute',action='store_true');a=p.parse_args(argv)
    print(json.dumps(run_pipeline(a.run_dir,a.protocol,a.out_dir,a.quality_predictions,a.event_predictions,a.reviews,a.execute),indent=2))

if __name__=='__main__':main()
