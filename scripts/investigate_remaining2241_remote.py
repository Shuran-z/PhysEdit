import json,gzip,hashlib,collections,os
from pathlib import Path
from huggingface_hub import HfApi
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'remaining2241';O.mkdir(exist_ok=True)
api=HfApi();repo='phyeditingvideo/Phyediting'
commits=api.list_repo_commits(repo,repo_type='dataset');out=[dict(commit_id=x.commit_id,title=x.title,created_at=str(x.created_at)) for x in commits];(O/'UPSTREAM_HISTORY.json').write_text(json.dumps(out,indent=2));print('commits',len(out));print(json.dumps(out[:35],indent=2))
B=Path('/data2/wangzijun_p25/phy2_standardization_20261027');
for l in (B/'processed.jsonl').open():
 x=json.loads(l)
 if x['engine']=='genesis' and '/T04/' in x['logical_path'] and '/metadata/' in x['logical_path']:
  raw=(B/'phy2_release_v1.0.0_rc1'/x['path']).read_bytes();m=json.loads(gzip.decompress(raw));print('T04_META_KEYS',list(m));break
