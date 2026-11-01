"""Recover byte-exact config artifacts using historical source ledgers."""
import collections
import gzip
import hashlib
import json
from pathlib import Path

R=Path('/data_cached/wangzijun_p25/config_bindings_20261031')
B=Path('/data2/wangzijun_p25/phy2_standardization_20261027')
ART=B/'phy2_release_v1.0.0_rc1'

def digest(raw):return hashlib.sha256(raw).hexdigest()
def main():
    with gzip.open(R/'TASKS.jsonl.gz','rt') as f:tasks=list(map(json.loads,f))
    artifacts=[];byhash=collections.defaultdict(list);videos=collections.defaultdict(list)
    for line in (B/'processed.jsonl').open():
        a=json.loads(line)
        if a['kind']=='video':videos[a['source_sha256']].append(a)
        elif a['logical_path'].endswith('.json'):
            artifacts.append(a);byhash[a['source_sha256']].append(a)
    byrelease=collections.defaultdict(list)
    for a in artifacts:byrelease[a['release_id']].append(a)
    natives=collections.defaultdict(set)
    for values in videos.values():
        for v in values:natives[v['release_id']].add(v['native_sample_id'])
    bycase=collections.defaultdict(list)
    for a in artifacts:
        parts=Path(a['logical_path']).parts;name=parts[-1]
        if not (name in ('config.json','input.json') or 'configs' in parts or 'inputs' in parts):continue
        known=natives[a['release_id']]
        matches=set(parts)&known
        stem=name[:-5]
        if stem in known:matches.add(stem)
        for camera in ['cam01','cam02','cam03']:
            prefix=stem.split('__'+camera)[0]
            if prefix in known:matches.add(prefix)
        for native in matches:bycase[a['release_id'],native].append(a)
    cache={};result=[];examples=[];counts=collections.Counter()
    def read(a):
        p=ART/a['path']
        if not p.is_file():return None
        raw=p.read_bytes()
        assert digest(raw)==a['sha256'],str(p)
        if a['storage_transform']=='gzip_lossless':raw=gzip.decompress(raw)
        assert digest(raw)==a['source_sha256']
        json.loads(raw)
        return raw
    for t in tasks:
        out=dict(canonical_video_id=t['canonical_video_id'],expected_sha256=t['expected_sha256'])
        if t['verified_local_paths']:
            out.update(status='RECOVERED',local_path=t['verified_local_paths'][0],sha256=t['expected_sha256'],method='previously_registered_raw_config_hash')
        elif t['kind'] in ('current_bundle','t19_metadata_zip'):
            out.update(status=t['kind'].upper())
        else:
            matches=byhash.get(t['expected_sha256'],[]) if t['expected_sha256'] else []
            available=next((a for a in matches if (ART/a['path']).is_file()),None)
            if available:
                raw=read(available)
                out.update(status='RECOVERED',artifact=available,sha256=digest(raw),method='registered_raw_config_hash_from_lossless_source_ledger')
            else:
                h=t['evidence'].get('derived_from_video_sha256') or t['video_sha256']
                candidates=[]
                source_vids=videos.get(h,[])
                for v in source_vids:
                    native=v['native_sample_id']
                    for a in bycase[v['release_id'],native]:
                        parts=Path(a['logical_path']).parts;name=parts[-1]
                        belongs=native in parts or name==native+'.json' or name.startswith(native+'__'+t['camera'])
                        role=name in ('config.json','input.json') or 'configs' in parts or 'inputs' in parts
                        if belongs and role and (ART/a['path']).is_file():candidates.append(a)
                unique={a['source_sha256']:a for a in candidates}
                if len(unique)==1:
                    a=next(iter(unique.values()));raw=read(a)
                    if t['expected_sha256'] and digest(raw)!=t['expected_sha256']:
                        out.update(status='HASH_MISMATCH',candidate=a)
                    else:
                        out.update(status='RECOVERED',artifact=a,sha256=digest(raw),method='original_video_sha_matched_source_ledger_same_case_config',video_source_records=source_vids)
                else:
                    out.update(status='UNRESOLVED',source_video_matches=len(source_vids),config_candidates=len(unique),
                        candidates=list(unique.values())[:3])
                    if len(examples)<60:examples.append(dict(task=t,recovery=out,source_video_records=source_vids,
                        nearby_artifacts=[]))
        counts[out['status']]+=1;result.append(out)
    with gzip.open(R/'RECOVERED.jsonl.gz','wt') as f:
        for x in result:f.write(json.dumps(x)+'\n')
    (R/'RECOVERY_EXAMPLES.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2))
    print(json.dumps(dict(counts=counts,artifacts=len(artifacts),videos=len(videos))),flush=True)
    (R/'RECOVERY_COUNTS.json').write_text(json.dumps(counts,indent=2))

if __name__=='__main__':main()
