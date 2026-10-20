"""Recover current T18 configs and source events before conditional searches."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import re

try:
    from scripts.t18_table_contact_boundary_worker import PROJECT,EVENT,table_event,change,builder
except ModuleNotFoundError:
    from t18_table_contact_boundary_worker import PROJECT,EVENT,table_event,change,builder


def main():
    p=argparse.ArgumentParser();p.add_argument('--records',required=True);p.add_argument('--out',required=True);args=p.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);build,bgs=builder();jobs=[];pending=[];events=[]
    for path in Path(args.records).glob('T18*.json'):
        row=json.loads(path.read_text());sid=row['sample_id']
        if row.get('status')!='published_metadata_extracted':continue
        cp=PROJECT/'configs/production'/sid/'cam01.json'
        try:
            raw=cp.read_bytes();c=json.loads(raw);e=c['experiment'];axis=e['parameter']['parameter_name']
            if 'supported_book_names' not in e:continue  # old two-book event contract retained separately
            if {o['name']:o for o in c['dynamic_objects']}!={o['name']:o['spec'] for o in row['actors']}:raise ValueError('live original config differs from published objects')
            if e!=row['experiment'] or c['scene_overrides']!=row['scene_overrides']:raise ValueError('live original conditions differ from release')
            mp=Path(row['metadata_source_path']);data=mp.read_bytes()
            if hashlib.sha256(data).hexdigest()!=row['metadata_sha256']:raise ValueError('published state bytes changed')
            text=gzip.decompress(data).decode() if mp.suffix=='.gz' else data.decode()
            marker=re.search(r'"manifest"\s*:\s*',text)
            if not marker or json.JSONDecoder().raw_decode(text,marker.end())[0]!=c['manifest']:raise ValueError('static manifest differs from release')
            index=text.rfind('"frame_index": 209')
            if index<0:raise ValueError('last frame missing')
            frame=json.JSONDecoder().raw_decode(text,text.rfind('{',0,index))[0]
            measured=table_event(c,frame)
            log=PROJECT/'production'/sid/'logs'/(sid+'__cam01.log')
            logged_seed=None
            if log.exists():
                with log.open(errors='replace') as stream:head=stream.read(20000)
                match=re.search(r'deterministic seed:\s*(\d+)',head)
                if match:logged_seed=int(match[1])
            if logged_seed is not None and logged_seed!=int(c['seed'])%(2**31-1):raise ValueError('original logged seed differs from config')
            event=dict(sample_id=sid,scene_id='T18',engine='genesis',revision=row['revision'],target_event=EVENT,
                theta=e['parameter']['parameter_value'],family_id=axis,reference_label=measured['label'],**{k:v for k,v in measured.items() if k!='label'},
                reference_state_sha256=row['metadata_sha256'],reference_config_sha256=hashlib.sha256(raw).hexdigest(),
                source_config_path=str(cp),source_state_path=str(mp),seed=c['seed'],logged_applied_seed=logged_seed,
                event_variant_version=e['event_variant_version'],event_variant_id=e['event_variant_id'])
            events.append(event)
            try:
                reconstructed=change(c,event['theta'],build,bgs)
                if reconstructed['dynamic_objects']!=c['dynamic_objects']:raise ValueError('recipe does not reconstruct published geometry')
            except ValueError as exc:
                pending.append(dict(sample_id=sid,status='original_overlap_recipe_pending',reason=str(exc),version=e['event_variant_version']));continue
            original_build=build
            if 'v3_' in e['event_variant_version']:original_build,_=builder('v3')
            elif 'v4_' in e['event_variant_version']:original_build,_=builder('v4')
            grid=next(values for name,unit,values in original_build.SWEEPS['T18'] if name==axis)
            identity=dict(config_sha256=event['reference_config_sha256'],state_sha256=event['reference_state_sha256'],event=EVENT,axis=axis)
            jobs.append(dict(job_id=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24],
                sample_id=sid,scene_id='T18',revision=row['revision'],reference_label=event['reference_label'],
                reference_state_sha256=event['reference_state_sha256'],source_config_sha256=event['reference_config_sha256'],
                target_event=EVENT,base_config=c,original_grid=grid,normalization_domain=[min(grid),max(grid)],source_event=event))
        except Exception as exc:pending.append(dict(sample_id=sid,status='source_recovery_pending',reason=str(exc)))
    jobs.sort(key=lambda j:(-len(j['source_event']['upper_books_on_table']),j['sample_id']))
    (out/'plan.json').write_text(json.dumps(jobs));(out/'source_events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    (out/'pending.json').write_text(json.dumps(pending,indent=2))
    summary=dict(multi_book_reference_events=len(events),positive=sum(e['reference_label'] for e in events),ready_search_jobs=len(jobs),
        pending=collections.Counter(p['status'] for p in pending),versions=collections.Counter(e['event_variant_version'] for e in events),
        target_event=EVENT,original_grid_and_fixed_sample_topology=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
