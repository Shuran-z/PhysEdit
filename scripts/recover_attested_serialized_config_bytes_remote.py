"""Accept a serialized source config only if its bytes match a recorded input SHA256."""
import collections,gzip,hashlib,io,json,copy
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'followup';B=Path('/data2/wangzijun_p25/phy2_standardization_20261027');ART=B/'phy2_release_v1.0.0_rc1'
def load(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
tasks={x['canonical_video_id']:x for x in load(R/'TASKS.jsonl.gz')};remaining=load(O/'REMAINING.jsonl.gz');oldmissing={x['canonical_video_id']:x for x in load(R/'unresolved_configs.jsonl.gz')}
selected=[x for x in remaining if x['scene']=='T02'];sources={};metadata=collections.defaultdict(list)
for line in (B/'processed.jsonl').open():
    a=json.loads(line)
    if a['kind']=='video':sources[a['repo'],a['revision'],a['source_path']]=a
    elif '/metadata/' in a['logical_path'] and a['logical_path'].endswith('.json.gz'):metadata[a['release_id']].append(a)
from recover_local_config_sources_remote import input_prefix
cache={};added=[];rawdir=O/'attested_bytes';rawdir.mkdir(exist_ok=True)
for item in selected:
    cid=item['canonical_video_id'];t=tasks[cid];source=sources.get((t['source_repo'],t['source_revision'],t['source_path']))
    if not source or source['source_sha256']!=t['video_sha256']:continue
    ms=[a for a in metadata[source['release_id']] if source['native_sample_id'] in a['logical_path'] and '__'+t['camera']+'.json.gz' in a['logical_path']]
    if len(ms)!=1:continue
    a=ms[0];packed=(ART/a['path']).read_bytes();assert hashlib.sha256(packed).hexdigest()==a['sha256'];m=input_prefix(packed)
    target=(m.get('experiment',{}).get('config_input_sha256') or '').lower()
    if len(target)!=64:continue
    found=None
    for path in oldmissing[cid].get('candidate_summary',{}).get('example_paths',[]):
        p=Path(path)
        if not p.is_file() or p.stat().st_size>1024*1024:continue
        k=(path,target)
        if k in cache:
            if cache[k]:found=cache[k];break
            continue
        original=json.loads(p.read_bytes());unstamped=copy.deepcopy(original);unstamped.get('experiment',{}).pop('config_input_sha256',None)
        for cfg in [original,unstamped]:
            for indent in [None,2,4]:
                for sort in [False,True]:
                    for ensure in [False,True]:
                        text=json.dumps(cfg,indent=indent,sort_keys=sort,ensure_ascii=ensure)
                        for newline in ['\n','\r\n']:
                            version=text.replace('\n',newline)
                            for end in ['',newline]:
                                for bom in [b'',b'\xef\xbb\xbf']:
                                    raw=bom+(version+end).encode()
                                    if hashlib.sha256(raw).hexdigest()==target:found=raw;break
                                if found:break
                            if found:break
                        if found:break
                    if found:break
                if found:break
            if found:break
        cache[k]=found
        if found:break
    if found:
        p=rawdir/(target+'.json');p.write_bytes(found)
        added.append(dict(canonical_video_id=cid,status='RECOVERED',local_path=str(p),sha256=target,method='original_recorded_input_sha256_exact_serialized_bytes',evidence=dict(video_sha256=t['video_sha256'],metadata_source_key=a['source_key'],metadata_source_sha256=a['source_sha256'],metadata_artifact_sha256=a['sha256'],config_byte_sha256=target)))
prior=load(O/'NEW_RECOVERIES.jsonl.gz');ids={x['canonical_video_id'] for x in added}
with gzip.open(O/'NEW_RECOVERIES.jsonl.gz','wt') as f:
    for x in prior+added:f.write(json.dumps(x)+'\n')
with gzip.open(O/'REMAINING.jsonl.gz','wt') as f:
    for x in remaining:
        if x['canonical_video_id'] not in ids:f.write(json.dumps(x)+'\n')
summary=dict(t02_checked=len(selected),added=len(added),all_new_recovered=len(prior)+len(added),remaining_targeted=len(remaining)-len(added))
(O/'ATTESTED_SERIALIZATION.json').write_text(json.dumps(summary));print(json.dumps(summary),flush=True)
