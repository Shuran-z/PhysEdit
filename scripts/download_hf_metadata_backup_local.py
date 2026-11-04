"""Copy the exact reviewed old metadata to the user's Windows disk; no HF writes."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.boundary_ssh import remote_text,transport_options
OUT=ROOT/'review/full_prompt_audit_20261102/publish'
PLAN=json.loads((OUT/'QUOTA_REPLACEMENT_PLAN.json').read_text(encoding='utf8'))
BASE=PLAN['head_unchanged'];REMOTE='/data_cached/wangzijun_p25/prompt_numeric_publish_20261102_4a88a7a4'
DEST=ROOT.parent/'backups/huggingface/phy2_phydataset'/BASE
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 code=f'''from pathlib import Path
import hashlib,json,tarfile
r=Path({REMOTE!r});plan=json.loads((r/'QUOTA_REPLACEMENT_PLAN.json').read_text());base=plan['head_unchanged']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
records=plan['backed_up_files']
for item in records:
 p=Path(item['backup']);assert p.stat().st_size==item['size'] and sha(p)==item['sha256'],item['path']
manifest=dict(repo_id='phy2/phydataset',repo_type='dataset',revision=base,files=records,remote_backups_preserved=True,history_deleted=False)
m=r/'LOCAL_BACKUP_MANIFEST.json';m.write_text(json.dumps(manifest,indent=2))
archive=r/'metadata_backup_for_windows.tar'
with tarfile.open(archive,'w') as z:
 for item in records:z.add(item['backup'],arcname=item['path'],recursive=False)
 z.add(m,arcname='BACKUP_MANIFEST.json',recursive=False)
receipt=dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,files=len(records),revision=base)
(r/'LOCAL_BACKUP_ARCHIVE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''
 receipt=json.loads(remote_text('p25',code,timeout=180,attempts=1))
 print(json.dumps({'phase':'remote_archive_verified',**receipt}),flush=True)
 download=OUT/'local_backup_download';download.mkdir(exist_ok=True);part=download/'metadata_backup.tar.part'
 subprocess.run(['scp',*transport_options('p25'),'-o','BatchMode=yes','-o','ConnectTimeout=10',f"p25:{receipt['archive']}",str(part.relative_to(ROOT))],cwd=ROOT,check=True)
 assert part.stat().st_size==receipt['bytes'] and sha(part)==receipt['sha256'],'archive transfer hash mismatch'
 print(json.dumps({'phase':'download_sha256_verified','bytes':receipt['bytes']}),flush=True)
 DEST.mkdir(parents=True,exist_ok=True)
 expected={x['path']:x for x in PLAN['backed_up_files']}
 with tarfile.open(part,'r') as z:
  assert set(z.getnames())==set(expected)|{'BACKUP_MANIFEST.json'}
  for member in z.getmembers():
   target=(DEST/member.name).resolve()
   assert target.is_relative_to(DEST.resolve()) and member.isfile() and not member.issym() and not member.islnk()
   if target.exists():
    if member.name in expected:assert sha(target)==expected[member.name]['sha256']
    else:assert target.read_bytes()==z.extractfile(member).read()
   else:z.extract(member,DEST,filter='data')
 for name,item in expected.items():
  p=DEST/name;assert p.stat().st_size==item['size'] and sha(p)==item['sha256'],name
 with zipfile.ZipFile(DEST/'releases/physedit/downloads/physedit_metadata.zip') as z:assert z.testzip() is None
 archive=DEST/'metadata_backup.tar'
 if archive.exists():assert sha(archive)==receipt['sha256']
 else:shutil.move(str(part),archive)
 result=dict(status='PASS',repo='phy2/phydataset',revision=BASE,local_directory=str(DEST),archive=str(archive),archive_sha256=receipt['sha256'],archive_bytes=receipt['bytes'],files_verified=len(expected),metadata_bytes=sum(x['size'] for x in expected.values()),all_sha256_match=True,offline_zip_crc_check='PASS',remote_backups_preserved=True,huggingface_history_deleted=False,huggingface_release_changed=False)
 for p in [DEST/'LOCAL_BACKUP_VERIFIED.json',OUT/'LOCAL_BACKUP_VERIFIED.json']:p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(result,ensure_ascii=True),flush=True)
if __name__=='__main__':main()
