import collections,gzip,json
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');B=Path('/data2/wangzijun_p25/phy2_standardization_20261027')
with gzip.open(R/'TASKS.jsonl.gz','rt') as f:tasks={x['canonical_video_id']:x for x in map(json.loads,f)}
selected={}
with gzip.open(R/'followup/REMAINING.jsonl.gz','rt') as f:
    for x in map(json.loads,f):
        if x['source_metadata_objects']==0 and x['source_video_records']>0:selected.setdefault(x['scene'],tasks[x['canonical_video_id']])
hashes={x['video_sha256']:x for x in selected.values()};sources=[];artifacts=[]
for line in (B/'processed.jsonl').open():
    a=json.loads(line)
    if a['kind']=='video' and a['source_sha256'] in hashes:sources.append(a)
    elif a['kind']=='artifact':artifacts.append(a)
for a in sources:
    row=hashes[a['source_sha256']]
    related=[x for x in artifacts if x['release_id']==a['release_id'] and a['native_sample_id'] in x['logical_path']]
    print(json.dumps({'target':row['canonical_video_id'],'video_source':a,'related_artifacts':related[:12]},ensure_ascii=False),flush=True)
