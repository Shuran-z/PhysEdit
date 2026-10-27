"""Compare source and replay event histories without redefining the event."""
import argparse, collections, gzip, hashlib, json, math
from pathlib import Path
try:
    from scripts.t18_table_contact_boundary_worker import table_event
except ModuleNotFoundError:
    from t18_table_contact_boundary_worker import table_event

def read_state(path, digest, raw_digest=False):
    path=Path(path);data=path.read_bytes();raw=gzip.decompress(data) if path.suffix=='.gz' else data
    if hashlib.sha256(raw if raw_digest else data).hexdigest()!=digest:raise ValueError('state digest mismatch')
    return json.loads(raw)

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--plan',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    base=Path(a.base);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    roots=[base/n for n in ['run','legacy_run','asset_retry_run']]+sorted(base.glob('resource_parallel_20261022_*'))+sorted(base.glob('source_retry_20261025_*'))+[base/'original_render_retry_20261027']
    rows=[]
    for job in json.loads(Path(a.plan).read_text()):
        key=job['job_id'];c=job['base_config'];theta=c['experiment']['parameter']['parameter_value']
        receipts=[r/key/format(theta,'.12g')/'receipt.json' for r in roots];receipts=[r for r in receipts if r.exists()]
        row=dict(job_id=key,sample_id=job['sample_id'],reference_label=job['reference_label'])
        try:
            rp=receipts[-1];v=json.loads(rp.read_text());source=read_state(job['source_event']['source_state_path'],job['reference_state_sha256']);replay=read_state(v['state_path'],v['state_sha256'],True)
            histories=[]
            for state in [source,replay]:
                labels=[table_event(c,f)['label'] for f in state['frames']]
                histories.append(dict(ever=int(any(labels)),terminal=labels[-1],first_contact=next((i for i,x in enumerate(labels) if x),None),last10=labels[-10:]))
            names={o['name'] for o in c['dynamic_objects']};errors=[]
            frame_index=int(c.get('render',{}).get('pre_static_frames',0))
            static=[]
            for state in [source,replay]:
                hits=[x for x in state['frames'][frame_index].get('contacts',[]) if any(str(x.get(k,'')).startswith('static_geom_') and x.get(k)!='static_geom_0' for k in ['entity_a','entity_b'])]
                static.append(dict(count=len(hits),max_penetration_m=max((x.get('penetration_m',0) for x in hits),default=0)))
            row['source_initial_extra_static_contacts']=static[0]
            row['replay_initial_extra_static_contacts']=static[1]
            for x,y in zip(source['frames'],replay['frames']):
                aa={o['name']:o['position'] for o in x['objects'] if o['name'] in names};bb={o['name']:o['position'] for o in y['objects'] if o['name'] in names}
                errors.append(max(math.dist(aa[n],bb[n]) for n in names))
            source_history,replay_history=histories
            category='event_reproduced' if source_history['terminal']==replay_history['terminal'] else 'terminal_only_disagreement' if source_history['ever']==replay_history['ever'] else 'contact_history_disagreement'
            row.update(category=category,source_history=source_history,replay_history=replay_history,initial_error_m=errors[0],first_error_over_1mm_frame=next((i for i,x in enumerate(errors) if x>.001),None),max_position_error_m=max(errors),replay_receipt=str(rp),source_state_sha256=job['reference_state_sha256'],replay_state_sha256=v['state_sha256'],original_render_retry='original_render_retry_20261027' in str(rp))
        except Exception as e:row.update(category='audit_error',error=repr(e))
        rows.append(row);(out/(key+'.json')).write_text(json.dumps(row,indent=2))
        (out/'summary.json').write_text(json.dumps(dict(examined=len(rows),categories=dict(collections.Counter(x['category'] for x in rows)),cases=rows),indent=2))
    print(json.dumps(dict(examined=len(rows),categories=dict(collections.Counter(x['category'] for x in rows)))))
if __name__=='__main__':main()
