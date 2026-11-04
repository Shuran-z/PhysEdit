"""Back up one superseded metadata ZIP locally before freeing its HF storage."""
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.boundary_ssh import remote_text,transport_options
from scripts.supplement_hf_transport import hf_transport
OUT=ROOT/'review/full_prompt_audit_20261102/publish';REMOTE='/data_cached/wangzijun_p25/prompt_numeric_publish_20261102_4a88a7a4';PY='/home/wangzijun_p25/miniconda3/bin/python'
def main():
 candidates=json.loads((OUT/'HISTORICAL_METADATA_CANDIDATES.json').read_text())['candidates']
 x=next(x for x in candidates if x['path']=='releases/physedit/downloads/physedit_metadata.zip')
 with hf_transport(OUT,ports=(20276,20277,20278)) as proxy:
  code=f'''import os,json,hashlib,zipfile
from pathlib import Path
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:os.environ[k]={proxy!r}
from huggingface_hub import HfApi
from huggingface_hub.utils import get_session,hf_raise_for_status
a=HfApi();x={x!r};r=Path({REMOTE!r});p=r/'historical_metadata_backups'/(x['oid']+'.zip');p.parent.mkdir(exist_ok=True)
current=a.get_paths_info('phy2/phydataset',[x['path']],repo_type='dataset',revision='main')[0];assert current.lfs.sha256!=x['oid']
if not p.exists():
 resp=get_session().post('https://huggingface.co/datasets/phy2/phydataset.git/info/lfs/objects/batch',headers=a._build_hf_headers(),json={{'operation':'download','transfers':['basic'],'objects':[{{'oid':x['oid'],'size':x['size']}}]}});hf_raise_for_status(resp)
 obj=resp.json()['objects'][0];assert 'error' not in obj;action=obj['actions']['download']
 with get_session().get(action['href'],headers=action.get('header',{{}}),stream=True) as response:
  hf_raise_for_status(response)
  with p.open('wb') as f:
   for b in response.iter_content(4*1024*1024):f.write(b)
assert p.stat().st_size==x['size'] and hashlib.sha256(p.read_bytes()).hexdigest()==x['oid']
with zipfile.ZipFile(p) as z:assert z.testzip() is None
x['remote_backup']=str(p);(r/'HISTORICAL_METADATA_ONE_BACKUP.json').write_text(json.dumps(x,indent=2));print(json.dumps(x))
'''
  data=json.loads(remote_text('p25',code,timeout=600,attempts=1,python=PY));print(json.dumps({'phase':'historical_zip_remote_verified','bytes':data['size']}),flush=True)
 dest=ROOT.parent/'backups/huggingface/phy2_phydataset/historical_metadata_objects';dest.mkdir(parents=True,exist_ok=True)
 temp=OUT/'local_backup_download'/(x['oid']+'.zip.part')
 subprocess.run(['scp',*transport_options('p25'),'-o','BatchMode=yes',f"p25:{data['remote_backup']}",str(temp.relative_to(ROOT))],cwd=ROOT,check=True)
 assert temp.stat().st_size==x['size'] and hashlib.sha256(temp.read_bytes()).hexdigest()==x['oid']
 with zipfile.ZipFile(temp) as z:assert z.testzip() is None
 target=dest/(x['oid']+'.zip');assert not target.exists();temp.replace(target)
 data.update(local_backup=str(target),local_sha256_verified=True,local_zip_crc_check='PASS',deletion_performed=False)
 (dest/(x['oid']+'.json')).write_text(json.dumps(data,indent=2),encoding='utf8');(OUT/'HISTORICAL_METADATA_LOCAL_BACKUP.json').write_text(json.dumps(data,indent=2),encoding='utf8')
 print(json.dumps(data,ensure_ascii=True),flush=True)
if __name__=='__main__':main()
