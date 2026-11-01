"""Inventory exact original config bindings for all current video rows."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
from huggingface_hub import HfApi,hf_hub_download

ROOT=Path('/data_cached/wangzijun_p25/config_bindings_20261031')
REPO='phy2/phydataset'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def rows(p):
    with gzip.open(p,'rt') as f:yield from map(json.loads,f)

def main():
    ROOT.mkdir(exist_ok=True)
    api=HfApi();revision=api.repo_info(REPO,repo_type='dataset').sha
    p=hf_hub_download(REPO,'releases/physedit/catalog/videos.jsonl.gz',repo_type='dataset',revision=revision)
    tasks=[];counts=collections.Counter();keys=collections.Counter();examples={};local_cache={}
    for r in rows(p):
        evidence=r.get('prompt_binding_evidence') or {}
        config_evidence=evidence.get('config_evidence') or {}
        current=r.get('current_render') or {}
        expected=current.get('source_config_sha256') or r.get('prompt_source_config_sha256') or evidence.get('source_config_sha256') or evidence.get('config_sha256') or config_evidence.get('expected_sha256') or evidence.get('source_config_sha256')
        paths=[r.get('prompt_source_config'),config_evidence.get('path'),evidence.get('source_config')]
        paths=list(dict.fromkeys(p for p in paths if p and p.startswith('/')))
        found=[];mismatch=[]
        for path in paths:
            if path not in local_cache:
                q=Path(path)
                if q.is_file():
                    raw=q.read_bytes()
                    if path.endswith('.gz'):
                        try:raw=gzip.decompress(raw)
                        except Exception:pass
                    try:json.loads(raw);local_cache[path]=sha(raw)
                    except Exception:local_cache[path]='NOT_JSON'
                else:local_cache[path]=None
            h=local_cache[path]
            if h and h==expected:found.append(path)
            elif h:mismatch.append({'path':path,'actual_sha256':h})
        if current.get('source_bundle') and current.get('config_member'):kind='current_bundle'
        elif r['engine']=='genesis' and r['quota_scene']=='T19':kind='t19_metadata_zip'
        elif found:kind='exact_local_config'
        else:kind='needs_recovery'
        counts[kind]+=1
        if not expected:counts['missing_expected_sha256']+=1
        keys[r['engine'],r['quota_scene'],kind]+=1
        task=dict(canonical_video_id=r['canonical_video_id'],engine=r['engine'],scene=r['quota_scene'],
            video_sha256=r['sha256'],native_sample_id=r['native_sample_id'],camera=r['camera'],
            expected_sha256=expected,local_paths=paths,verified_local_paths=found,mismatches=mismatch,
            kind=kind,declared_config=r.get('prompt_source_config'),current_render=current,
            evidence=evidence,source_repo=r.get('source_repo'),source_revision=r.get('source_revision'),source_path=r.get('source_path'))
        tasks.append(task)
        examples.setdefault((r['engine'],r['quota_scene'],kind),task)
    with gzip.open(ROOT/'TASKS.jsonl.gz','wt') as f:
        for t in tasks:f.write(json.dumps(t)+'\n')
    summary=dict(revision=revision,total=len(tasks),counts=dict(counts),distinct_expected_hashes=len({t['expected_sha256'] for t in tasks if t['expected_sha256']}),
        by_scene=[dict(engine=e,scene=s,kind=k,videos=n) for (e,s,k),n in sorted(keys.items())],
        examples=list(examples.values()))
    (ROOT/'INVENTORY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('examples','by_scene')}),flush=True)
    for t in tasks:
        if t['canonical_video_id'] in ['physedit_genesis_t03_7b11b86fe8ac0134__cam01','physedit_isaac_t11_a4ea4e89bd9981be__cam01','physedit_isaac_t19_0987dd87acd0c6d0__cam01','physedit_isaac_t20_48df634f70618cca__cam01']:print(json.dumps(t),flush=True)

if __name__=='__main__':main()
