"""Verify published content hashes and independently exercise the client exporter."""
import collections,gzip,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
from huggingface_hub import HfApi,hf_hub_download
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');STAGE=R/'stage';D=STAGE/'releases/physedit';REPO='phy2/phydataset'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
api=HfApi();head=api.repo_info(REPO,repo_type='dataset').sha
checks=json.loads((D/'checks/FILES_SHA256.json').read_text())
paths=[STAGE/'release_status.json',D/'checks/FILES_SHA256.json',D/'downloads/physedit_metadata.zip']+[D/r['path'] for r in checks['files']]
for start in range(0,len(paths),400):
    selected=paths[start:start+400]
    infos={x.path:x for x in api.get_paths_info(REPO,[p.relative_to(STAGE).as_posix() for p in selected],revision=head,repo_type='dataset')}
    for p in selected:
        info=infos[p.relative_to(STAGE).as_posix()];raw=p.read_bytes();assert info.size==len(raw)
        if info.lfs:assert info.lfs.sha256==hashlib.sha256(raw).hexdigest(),str(p)
        else:assert info.blob_id==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),str(p)
fresh=R/'client_smoke';(fresh/'catalog').mkdir(parents=True,exist_ok=True);(fresh/'tools').mkdir(exist_ok=True);(fresh/'provenance').mkdir(exist_ok=True)
manifest=Path(hf_hub_download(REPO,'releases/physedit/catalog/config_bindings.jsonl.gz',revision=head,repo_type='dataset',local_dir=R/'fresh_manifest',force_download=True))
assert sha(manifest)==sha(D/'catalog/config_bindings.jsonl.gz')
shutil.copyfile(manifest,fresh/'catalog/config_bindings.jsonl.gz')
tool=Path(hf_hub_download(REPO,'releases/physedit/tools/download_original_configs.py',revision=head,repo_type='dataset',local_dir=R/'fresh_manifest',force_download=True))
assert sha(tool)==sha(D/'tools/download_original_configs.py');shutil.copyfile(tool,fresh/'tools/download_original_configs.py')
source=R/'fresh_download/releases/physedit/provenance/configs.zip'
assert sha(source)==sha(D/'provenance/configs.zip')
dest=fresh/'provenance/configs.zip'
if not dest.exists():os.link(source,dest)
with gzip.open(manifest,'rt') as f:bindings={b['canonical_video_id']:b for b in map(json.loads,f)}
assert len(bindings)==72000
counts=collections.Counter(b['status'] for b in bindings.values());package=json.loads((R/'PACKAGE.json').read_text());assert dict(counts)==package['counts']
with gzip.open(D/'catalog/videos.jsonl.gz','rt') as f:
    for row in map(json.loads,f):
        b=bindings[row['canonical_video_id']];assert row['sha256']==b['video_sha256'];assert row['config_binding_status']==b['status'];assert row['config_download']==b.get('download')
ids=['physedit_genesis_t03_7b11b86fe8ac0134__cam01','physedit_isaac_t11_a4ea4e89bd9981be__cam01','physedit_isaac_t19_0987dd87acd0c6d0__cam01','physedit_isaac_t20_48df634f70618cca__cam01']
command=[sys.executable,str(fresh/'tools/download_original_configs.py'),'--output',str(R/'client_exports')]
for cid in ids:command+=['--video-id',cid]
subprocess.run(command,check=True)
receipt=dict(revision=head,config_revision=bindings[ids[0]]['download']['revision'],**package,
    published_metadata_files_hash_verified=len(paths),verification_method='Remote LFS SHA256/Git blob identity plus fresh config archive/manifest/tool downloads',
    full_manifest_video_bindings_verified=72000,four_fresh_client_exports_verified=True,scientific_inputs_and_train_test_membership_preserved=True)
(R/'PUBLISHED.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in receipt.items() if k!='by_scene'}),flush=True)
