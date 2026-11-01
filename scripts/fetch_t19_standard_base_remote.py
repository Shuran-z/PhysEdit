"""Fetch the current publication base without modifying it."""
import os, json, time, shutil, gzip, collections, logging
from pathlib import Path
logging.disable(logging.CRITICAL)
os.environ['NO_PROXY']='.amazonaws.com'
os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import HfApi, hf_hub_download, get_token
ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029/current_standard_base')
ROOT.mkdir(exist_ok=True)
api=HfApi(token=get_token()); repo='phy2/phydataset'
def retry(fn):
    for i in range(8):
        try:return fn()
        except Exception:
            if i==7:raise
            time.sleep(2)
head=retry(lambda:api.repo_info(repo,repo_type='dataset',expand=['sha']).sha)
def fetch(path):
    src=retry(lambda:hf_hub_download(repo,path,repo_type='dataset',revision=head,token=get_token()))
    dst=ROOT/path;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    return dst
pointer=json.loads(fetch('catalog/active_72000.json').read_text())
manifest=fetch(pointer['manifest_path'])
for path in ['README.md','data/T19/INDEX.json','data/T19/README.md','releases/physedit/README.md']:
    fetch(path)
tree=retry(lambda:list(api.list_repo_tree(repo,'releases/physedit/catalog',repo_type='dataset',revision=head)))
for x in tree:
    if x.path.endswith('.json') or x.path.endswith('.md'):fetch(x.path)
with gzip.open(manifest,'rt') as f:rows=list(map(json.loads,f))
result={'head':head,'pointer':pointer,'tree':[x.path for x in tree],
 'counts':dict(collections.Counter(r['quality_admission_status'] for r in rows)),
 'target':[r for r in rows if r['video_id'].startswith('phy_isaac_t19_67a7c1d07f0f0048')]}
(ROOT/'BASE.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'head':head,'counts':result['counts'],'tree':result['tree'],'target_count':len(result['target'])}),flush=True)
