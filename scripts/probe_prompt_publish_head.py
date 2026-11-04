from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.boundary_ssh import remote_text
from scripts.supplement_hf_transport import hf_transport
OUT=ROOT/'review/full_prompt_audit_20261102/publish';OUT.mkdir(exist_ok=True)
code='''import os,json,shutil
from pathlib import Path
os.environ['HTTPS_PROXY']=__TASK_PROXY__;os.environ['HTTP_PROXY']=__TASK_PROXY__
os.environ['https_proxy']=__TASK_PROXY__;os.environ['http_proxy']=__TASK_PROXY__
os.environ['HF_HUB_DISABLE_XET']='1';os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
from huggingface_hub import HfApi,hf_hub_download
root=Path('/data_cached/wangzijun_p25/prompt_numeric_publish_20261102_4a88a7a4');root.mkdir(exist_ok=True)
api=HfApi();repo='phy2/phydataset';head=api.repo_info(repo,repo_type='dataset').sha
trees={}
for directory in ['', 'releases/physedit', 'releases/physedit/catalog','releases/physedit/prompts','prompts/all_videos']:
 try:trees[directory]=[{'path':r.path,'size':getattr(r,'size',None)} for r in api.list_repo_tree(repo,path_in_repo=directory,repo_type='dataset',revision=head)]
 except Exception as exc:trees[directory]={'error':type(exc).__name__}
paths=['README.md','releases/physedit/catalog/videos.jsonl.gz','releases/physedit/catalog/train_final.jsonl.gz']
downloaded={}
for path in paths:
 p=Path(hf_hub_download(repo,path,repo_type='dataset',revision=head,local_dir=root/'current'))
 downloaded[path]=str(p)
result={'head':head,'trees':trees,'downloaded':downloaded,'free_bytes':shutil.disk_usage(root).free}
(root/'HEAD_SNAPSHOT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
'''
with hf_transport(OUT,ports=(18876,18877,18878)) as proxy:
    raw=remote_text('p25',code.replace('__TASK_PROXY__',repr(proxy)),timeout=150,attempts=1,python='/home/wangzijun_p25/miniconda3/bin/python')
result=json.loads(raw);(OUT/'HEAD_SNAPSHOT.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
