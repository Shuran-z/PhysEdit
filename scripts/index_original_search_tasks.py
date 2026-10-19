"""Join frozen inventory to original manifest rows; name links are not certification."""
import collections
import json
import re
from pathlib import Path

OUT=Path('review/original_search_tasks_20261018')

def walk(value, pointer=''):
    if isinstance(value,dict):
        yield pointer,value
        for key,item in value.items():yield from walk(item,pointer+'/'+str(key))
    elif isinstance(value,list):
        for i,item in enumerate(value):yield from walk(item,pointer+'/'+str(i))

def main():
    index=collections.defaultdict(list)
    contracts=[]
    for host in ['p25','p26']:
        for source in json.loads((OUT/f'{host}_records.json').read_text()):
            if not source['path'].endswith('.json') or 'text' not in source:continue
            try:data=json.loads(source['text'])
            except ValueError:continue
            evidence={k:source[k] for k in ['path','sha256']}
            evidence['host']=host
            if 'contract' in source['path']:
                contracts.append({**evidence,'contract':data})
            for pointer,row in walk(data):
                sample=row.get('sample_id') or row.get('trajectory_id')
                if not isinstance(sample,str):continue
                # Preserve the original task's parameter/family fields, never
                # synthesize a velocity-only grouping or inherit a threshold.
                fields={k:v for k,v in row.items() if k not in ['frames','objects','camera_states']}
                index[sample].append({**evidence,'json_pointer':pointer,'original_row':fields})
    inventory=Path('../dataset_splits_v2/all_selected_trajectories.jsonl')
    counts=collections.Counter()
    with (OUT/'inventory_task_links.jsonl').open('w',encoding='utf-8') as stream:
        for line in inventory.read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            links=index.get(row['sample_id'],[]) if row['engine']=='genesis' else []
            result={'inventory_source':str(inventory),'inventory_is_historical_snapshot':True,
                    'engine':row['engine'],'scene_id':row['event_id'],'sample_id':row['sample_id'],
                    'release':row.get('release'),'revision':row.get('revision'),'videos':row['videos'],
                    'original_task_candidates':links,'binding_status':'manifest_identity_candidate' if links else 'not_located_in_collected_manifests',
                    'verified_boundary':False}
            counts[(row['engine'],row['event_id'],bool(links))]+=1
            stream.write(json.dumps(result,ensure_ascii=False)+'\n')
    (OUT/'contracts.json').write_text(json.dumps(contracts,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=[dict(engine=e,scene_id=s,manifest_identity_candidate=b,count=n) for (e,s,b),n in sorted(counts.items())]
    (OUT/'inventory_link_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({'contracts':len(contracts),'indexed_sample_ids':len(index),'summary':summary}))

if __name__=='__main__':main()
