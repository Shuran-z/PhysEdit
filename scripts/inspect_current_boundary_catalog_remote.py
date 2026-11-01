"""Read the live standard catalog identity without changing the release."""
import os,json,logging,time,shutil
from pathlib import Path
logging.disable(logging.CRITICAL);os.environ['NO_PROXY']='.amazonaws.com';os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import HfApi,hf_hub_download,get_token
def retry(fn):
    for i in range(8):
        try:return fn()
        except Exception:
            if i==7:raise
            time.sleep(2)
repo='phy2/phydataset';api=HfApi(token=get_token())
head=retry(lambda:api.repo_info(repo,repo_type='dataset',expand=['sha']).sha)
p=retry(lambda:hf_hub_download(repo,'catalog/active_72000.json',repo_type='dataset',revision=head,token=get_token()))
pointer=json.loads(Path(p).read_text());path=pointer['manifest_path']
item=retry(lambda:api.get_paths_info(repo,[path],repo_type='dataset',revision=head))[0]
result={'repo':repo,'revision':head,'pointer':pointer,'manifest_sha256':item.lfs.sha256,'manifest_bytes':item.size}
out=Path('/data_cached/wangzijun_p25/t19_review_20261029/boundary_catalog_live_20261030');out.mkdir(exist_ok=True)
manifest=retry(lambda:hf_hub_download(repo,path,repo_type='dataset',revision=head,token=get_token()))
shutil.copy2(manifest,out/'videos.jsonl.gz');(out/'CATALOG.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
