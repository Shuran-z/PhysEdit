from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.boundary_ssh import remote_text
from scripts.supplement_hf_transport import hf_transport
OUT=ROOT/'review/full_prompt_audit_20261102/publish'
code='''import os,json,hashlib
from pathlib import Path
os.environ['HTTPS_PROXY']=__TASK_PROXY__;os.environ['HTTP_PROXY']=__TASK_PROXY__;os.environ['https_proxy']=__TASK_PROXY__;os.environ['http_proxy']=__TASK_PROXY__
os.environ['HF_HUB_DISABLE_XET']='1';os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
from huggingface_hub import HfApi,hf_hub_download
root=Path('/data_cached/wangzijun_p25/prompt_numeric_publish_20261102_4a88a7a4');snap=json.loads((root/'HEAD_SNAPSHOT.json').read_text());head=snap['head'];api=HfApi();repo='phy2/phydataset'
paths=['release_status.json','releases/physedit/prompts/PROMPT_MANIFEST.json','releases/physedit/README.md','releases/physedit/catalog/scene_index.json','releases/physedit/catalog/train_unique_declared_triplets.jsonl.gz','releases/physedit/catalog/parquet/videos_train.parquet','releases/physedit/provenance/configs.zip','releases/t14_original_isaac_20261101/provenance.zip']
rootcat=[r.path for r in api.list_repo_tree(repo,path_in_repo='catalog',repo_type='dataset',revision=head) if hasattr(r,'size')]
paths+=rootcat
result={}
for path in paths:
 p=Path(hf_hub_download(repo,path,repo_type='dataset',revision=head,local_dir=root/'current'))
 result[path]={'local':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
(root/'CURRENT_SOURCE_DOWNLOADS.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
'''
with hf_transport(OUT,ports=(19076,19077,19078)) as proxy:
    raw=remote_text('p25',code.replace('__TASK_PROXY__',repr(proxy)),timeout=500,attempts=1,python='/home/wangzijun_p25/miniconda3/bin/python')
result=json.loads(raw);(OUT/'CURRENT_SOURCE_DOWNLOADS.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
