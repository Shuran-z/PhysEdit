import gzip,json
from pathlib import Path
from huggingface_hub import hf_hub_download
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031')
sources=set()
with gzip.open(R/'TASKS.jsonl.gz','rt') as f:
    for t in map(json.loads,f):
        e=t['evidence'].get('config_evidence') or {}
        if e.get('archive_path') and e.get('member'):sources.add((e.get('repo_id','phy2/phydataset'),e['revision'],e['archive_path']))
for repo,rev,path in sorted(sources):
    local=hf_hub_download(repo,path,repo_type='dataset',revision=rev)
    print(json.dumps({'archive_ready':path,'bytes':Path(local).stat().st_size}),flush=True)
