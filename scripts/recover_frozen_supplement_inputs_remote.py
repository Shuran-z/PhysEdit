"""Restore only exact-hash input bytes attested by the frozen video/input registry."""
import gzip,hashlib,json
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'followup';A=Path('/data_cached/wangzijun_p25/author_release_20261029/metadata')
def load(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
prior=load(O/'NEW_RECOVERIES.jsonl.gz');done={x['canonical_video_id'] for x in prior}
tasks={x['canonical_video_id']:x for x in load(R/'TASKS.jsonl.gz')}
pending={x['canonical_video_id']:x for x in load(R/'unresolved_configs.jsonl.gz') if x['canonical_video_id'] not in done}
bindings={x['video_sha256']:x for x in load(A/'supplement_prompt_input_bindings.jsonl.gz')}
inline={x['source_sha256']:x for x in load(A/'supplement_source_configs.jsonl.gz')}
rawdir=O/'frozen_supplement_bytes';rawdir.mkdir(exist_ok=True);cache={};added=[];requests=[]
for cid,row in pending.items():
    t=tasks[cid];b=bindings.get(t['video_sha256'])
    if not b or b.get('sample_id')!=t['native_sample_id'] or b.get('camera')!=t['camera']:continue
    declared=next((x for x in b.get('runtime_config_binding',[]) if x.get('camera')==t['camera']),None)
    if not declared:continue
    expected=declared['source_sha256'];found=None
    if expected in cache:found=cache[expected]
    elif expected in inline:
        c=inline[expected]['config']
        for indent in [2,4,None]:
            for ensure in [False,True]:
                for newline in ['\n','\r\n']:
                    text=json.dumps(c,ensure_ascii=ensure,indent=indent).replace('\n',newline)
                    for end in ['',newline]:
                        raw=(text+end).encode()
                        if hashlib.sha256(raw).hexdigest()==expected:found=raw;break
                    if found:break
                if found:break
            if found:break
        cache[expected]=found
    if found:
        p=rawdir/(expected+'.json');p.write_bytes(found)
        added.append(dict(canonical_video_id=cid,status='RECOVERED',local_path=str(p),sha256=expected,method='frozen_video_input_registry_and_exact_original_config_sha256',evidence=dict(video_sha256=t['video_sha256'],config_byte_sha256=expected,registry='supplement_prompt_input_bindings.jsonl.gz',source_path=declared['source'])))
    else:
        requests.append(dict(canonical_video_id=cid,expected_sha256=expected,local_paths=[declared['source']],runtime_path=declared['path'],runtime_sha256=declared['sha256'],storage_host=b.get('storage_host')))
with gzip.open(O/'NEW_RECOVERIES.jsonl.gz','wt') as f:
    for x in prior+added:f.write(json.dumps(x)+'\n')
addedids={x['canonical_video_id'] for x in added};remaining=load(O/'REMAINING.jsonl.gz')
with gzip.open(O/'REMAINING.jsonl.gz','wt') as f:
    for x in remaining:
        if x['canonical_video_id'] not in addedids:f.write(json.dumps(x)+'\n')
(O/'SUPPLEMENT_REQUESTS.json').write_text(json.dumps(requests,indent=2));summary=dict(added=len(added),all_new_recovered=len(prior)+len(added),unresolved_attested_sources=len(requests))
(O/'SUPPLEMENT_RECOVERY.json').write_text(json.dumps(summary));print(json.dumps(summary),flush=True)
