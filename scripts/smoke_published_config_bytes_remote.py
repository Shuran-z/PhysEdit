"""Fresh-download the published config object and verify the four original gaps."""
import gzip,hashlib,json,zipfile,os
from pathlib import Path
from huggingface_hub import hf_hub_download
R=Path(os.environ.get('CONFIG_BINDING_WORKDIR','/data_cached/wangzijun_p25/config_bindings_20261031'))
D=R/'stage/releases/physedit'
ids={'physedit_genesis_t03_7b11b86fe8ac0134__cam01','physedit_isaac_t11_a4ea4e89bd9981be__cam01','physedit_isaac_t19_0987dd87acd0c6d0__cam01','physedit_isaac_t20_48df634f70618cca__cam01'}
if (R/'SMOKE_IDS.json').exists():ids.update(json.loads((R/'SMOKE_IDS.json').read_text()))
with gzip.open(D/'catalog/config_bindings.jsonl.gz','rt') as f:
    selected=[r for r in map(json.loads,f) if r['canonical_video_id'] in ids]
assert len(selected)==len(ids) and all(r['status']=='VERIFIED' for r in selected)
b=selected[0]['download']
archive=Path(hf_hub_download(b['repo_id'],b['path'],repo_type='dataset',revision=b['revision'],local_dir=R/'fresh_download',force_download=True))
assert hashlib.sha256(archive.read_bytes()).hexdigest()==b['archive_sha256']
results=[]
with zipfile.ZipFile(archive) as z:
    for r in selected:
        raw=z.read(r['archive_member']);h=hashlib.sha256(raw).hexdigest();assert h==r['config_sha256'];json.loads(raw)
        results.append(dict(canonical_video_id=r['canonical_video_id'],video_sha256=r['video_sha256'],config_sha256=h,original_config_downloaded_and_verified=True))
(R/'FOUR_FRESH_DOWNLOADS.json').write_text(json.dumps({'revision':b['revision'],'samples':results,'archive_sha256_verified':True},indent=2))
print(json.dumps({'fresh_config_downloads':len(results),'all_original_hashes_match':True}),flush=True)
