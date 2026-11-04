from pathlib import Path
import hashlib,json,subprocess,sys,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.boundary_ssh import remote_text,transport_options
from scripts.supplement_hf_transport import hf_transport
OUT=ROOT/'review/prompt_semantic_repair_20261102';BASE='7af77078d39270a3c6ca7633bd373f357483b5f0';REMOTE='/data_cached/wangzijun_p25/prompt_semantic_repair_20261102'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 with hf_transport(OUT,ports=(21376,21377,21378)) as proxy:
  code=f'''from pathlib import Path
import os,json,hashlib,tarfile
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:os.environ[k]={proxy!r}
from huggingface_hub import HfApi
root=Path({REMOTE!r});root.mkdir(exist_ok=True);old=Path('/data_cached/wangzijun_p25/prompt_numeric_publish_20261102_4a88a7a4');source=old/'fresh_7af77078d3'
plan=json.loads((old/'UPLOAD_PLAN.json').read_text());api=HfApi();head=api.repo_info('phy2/phydataset',repo_type='dataset').sha;assert head=={BASE!r},('HEAD_CHANGED',head)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
infos={{x.path:x for x in api.get_paths_info('phy2/phydataset',[x['path'] for x in plan['files']],repo_type='dataset',revision=head)}}
for x in plan['files']:
 p=source/x['path'];assert p.stat().st_size==x['size'] and sha(p)==x['sha256']
 info=infos[x['path']];assert info.size==x['size']
 if info.lfs:assert info.lfs.sha256==x['sha256']
manifest=dict(revision=head,files=plan['files'],source=str(source),current_media_configs_splits_and_core100_not_selected=True)
(root/'BASE_BACKUP_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
archive=root/'base_7af_metadata.tar'
with tarfile.open(archive,'w') as z:
 for x in plan['files']:z.add(source/x['path'],arcname=x['path'],recursive=False)
 z.add(root/'BASE_BACKUP_MANIFEST.json',arcname='BASE_BACKUP_MANIFEST.json')
receipt=dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,files=len(plan['files']),revision=head);(root/'BASE_BACKUP_RECEIPT.json').write_text(json.dumps(receipt));print(json.dumps(receipt))
'''
  receipt=json.loads(remote_text('p25',code,timeout=300,attempts=1,python='/home/wangzijun_p25/miniconda3/bin/python'))
 print(json.dumps({'phase':'remote_backup_pass',**receipt}),flush=True)
 part=OUT/'base_7af_metadata.tar.part';subprocess.run(['scp',*transport_options('p25'),'-o','BatchMode=yes','p25:'+receipt['archive'],str(part.relative_to(ROOT))],cwd=ROOT,check=True)
 assert sha(part)==receipt['sha256'];dest=ROOT.parent/'backups/huggingface/phy2_phydataset'/BASE;dest.mkdir(parents=True,exist_ok=True)
 with tarfile.open(part) as z:
  for m in z.getmembers():assert (dest/m.name).resolve().is_relative_to(dest.resolve()) and m.isfile()
  z.extractall(dest,filter='data')
 manifest=json.loads((dest/'BASE_BACKUP_MANIFEST.json').read_text())
 for x in manifest['files']:assert sha(dest/x['path'])==x['sha256']
 with zipfile.ZipFile(dest/'releases/physedit/downloads/physedit_metadata.zip') as z:assert z.testzip() is None
 target=dest/'metadata_backup.tar';assert not target.exists();part.replace(target)
 receipt.update(status='PASS',local_directory=str(dest),archive=str(target),all_file_hashes_match=True,offline_zip_crc='PASS')
 for p in [OUT/'LOCAL_BASE_BACKUP_VERIFIED.json',dest/'LOCAL_BACKUP_VERIFIED.json']:p.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(receipt,ensure_ascii=True),flush=True)
if __name__=='__main__':main()
