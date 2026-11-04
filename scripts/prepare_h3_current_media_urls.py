"""Generate narrowly scoped media read URLs on p25; HF account credentials stay there."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.h3_prompt_sg_transport import run as sg,copy as sgcopy,PY as SGPY
from scripts.boundary_ssh import remote_text,transport_options
from scripts.supplement_hf_transport import hf_transport
OUT=ROOT/'review/h3_prompt_retrain_20261102';SG='/data/yangkaiyuan/h3_prompt_retrain_7af77078_20261102';P25='/data_cached/wangzijun_p25/h3_new_prompt_7af77078_20261102'
def main():
 data=json.loads(sg(f"from pathlib import Path;print(Path({SG+'/CHANGED_MEDIA_REQUESTS.json'!r}).read_text())"));path=OUT/'CHANGED_MEDIA_REQUESTS.json';path.write_text(json.dumps(data),encoding='utf8')
 remote_text('p25',f"from pathlib import Path;Path({P25!r}).mkdir(exist_ok=True)")
 subprocess.run(['scp',*transport_options('p25'),str(path.relative_to(ROOT)),'p25:'+P25+'/requests.json'],cwd=ROOT,check=True)
 with hf_transport(OUT,ports=(21076,21077,21078)) as proxy:
  code=f'''import os,json,concurrent.futures,time,threading,gzip
from pathlib import Path
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:os.environ[k]={proxy!r}
os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import HfApi
from huggingface_hub.utils import get_session,hf_raise_for_status
r=Path({P25!r});requests=json.loads((r/'requests.json').read_text());done=[];api=HfApi();sizes={{}}
source=Path('/data_cached/wangzijun_p25/prompt_numeric_publish_20261102_4a88a7a4/fresh_7af77078d3/releases/physedit/catalog/train_final.jsonl.gz');rows={{x['canonical_video_id']:x for x in map(json.loads,gzip.open(source,'rt'))}}
for offset in range(0,len(requests),200):
 batch=requests[offset:offset+200];infos={{x.path:x for x in api.get_paths_info('phy2/phydataset',[rows[x['id']]['canonical_path'] for x in batch],repo_type='dataset',revision='7af77078d39270a3c6ca7633bd373f357483b5f0')}}
 for x in batch:
  info=infos[rows[x['id']]['canonical_path']];assert info.lfs.sha256==x['sha256'];sizes[x['id']]=info.size
for offset in range(0,len(requests),500):
 batch=requests[offset:offset+500];response=get_session().post('https://huggingface.co/datasets/phy2/phydataset.git/info/lfs/objects/batch',headers=api._build_hf_headers(),json={{'operation':'download','transfers':['basic'],'objects':[{{'oid':x['sha256'],'size':sizes[x['id']]}} for x in batch]}});hf_raise_for_status(response)
 actions={{x['oid']:x for x in response.json()['objects']}}
 for x in batch:
  obj=actions[x['sha256']];assert 'error' not in obj;action=obj['actions']['download'];done.append(dict(id=x['id'],sha256=x['sha256'],url=action['href'],headers=action.get('header',{{}}),size=sizes[x['id']]))
 (r/'URL_PROGRESS.json').write_text(json.dumps(dict(done=len(done),failed=0,total=len(requests),time=time.time(),mode='batched_lfs_reads')))
p=r/'media_read_urls.private.json';p.write_text(json.dumps(dict(items=done,revision='7af77078d39270a3c6ca7633bd373f357483b5f0')));p.chmod(0o600)
print(json.dumps(dict(status='PASS',items=len(done),failed=0)))
'''
  print(remote_text('p25',code,timeout=1050,attempts=1,python='/home/wangzijun_p25/miniconda3/bin/python'),flush=True)
 private=OUT/'media_read_urls.private.json';subprocess.run(['scp',*transport_options('p25'),'p25:'+P25+'/media_read_urls.private.json',str(private.relative_to(ROOT))],cwd=ROOT,check=True)
 sgcopy(private,SG+'/media_read_urls.private.json');sgcopy(ROOT/'scripts/h3_new_prompt_prefetch.py',SG+'/h3_new_prompt_prefetch.py')
 code=f'''from pathlib import Path
import subprocess,json,os
r=Path({SG!r});(r/'media_read_urls.private.json').chmod(0o600)
assert not (r/'MEDIA_PREFETCH_LAUNCHED.json').exists()
with (r/'media_prefetch.log').open('ab') as log:p=subprocess.Popen([{SGPY!r},str(r/'h3_new_prompt_prefetch.py')],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
result=dict(pid=p.pid,items={len(data)},account_token_copied=False);(r/'MEDIA_PREFETCH_LAUNCHED.json').write_text(json.dumps(result));print(json.dumps(result))
'''
 print(sg(code),flush=True)
if __name__=='__main__':main()
