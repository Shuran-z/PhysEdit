from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.boundary_ssh import remote_text
from scripts.supplement_hf_transport import hf_transport
OUT=ROOT/'review/full_prompt_audit_20261102/publish'
code='''import os,json,hashlib
from pathlib import Path
for key in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:os.environ[key]=__TASK_PROXY__
os.environ['HF_HUB_DISABLE_XET']='1';os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
from huggingface_hub import hf_hub_download,HfApi
root=Path('/data_cached/wangzijun_p25/prompt_numeric_publish_20261102_4a88a7a4');head=json.loads((root/'HEAD_SNAPSHOT.json').read_text())['head']
paths=['releases/physedit/downloads/physedit_metadata.zip','releases/physedit/catalog/config_bindings.jsonl.gz','releases/physedit/checks/CHECK_REPORT.json','releases/physedit/docs/QUICKSTART_ZH.md','releases/physedit/prompts/VIEW.html','releases/physedit/prompts/export_txt.py']
result={}
for path in paths:
 p=Path(hf_hub_download('phy2/phydataset',path,repo_type='dataset',revision=head,local_dir=root/'current'))
 result[path]={'local':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
status=json.loads((root/'current/release_status.json').read_text());assert result[paths[0]]['sha256']==status['offline_metadata_sha256']
import zipfile
with zipfile.ZipFile(result[paths[0]]['local']) as z:result['offline_member_sample']=z.namelist()[:18]
import gzip
with gzip.open(result[paths[1]]['local'],'rt') as f:result['config_binding_example']=json.loads(next(f))
(root/'EXTRA_METADATA_DOWNLOADS.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
'''
with hf_transport(OUT,ports=(19176,19177,19178)) as proxy:
    data=json.loads(remote_text('p25',code.replace('__TASK_PROXY__',repr(proxy)),timeout=500,attempts=1,python='/home/wangzijun_p25/miniconda3/bin/python'))
(OUT/'EXTRA_METADATA_DOWNLOADS.json').write_text(json.dumps(data,indent=2),encoding='utf8');print(json.dumps(data))
