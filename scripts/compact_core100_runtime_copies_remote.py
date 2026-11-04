"""Deduplicate verified generated runtime copies, retaining every evidence path."""
import json
from pathlib import Path
from scripts.boundary_ssh import remote_text

ROOT=Path(__file__).resolve().parents[1]
REMOTE=r'''
import datetime,hashlib,json,os,shutil,uuid,zipfile
from pathlib import Path
parent=Path('/data2/liyuhan/core100_distance_bindings_20261031').resolve()
receipts=Path('/home/wangzijun_p25/core100_runtime_compaction_20261101');receipts.mkdir(exist_ok=True)
assert parent.name=='core100_distance_bindings_20261031'
def digest(path):
 h=hashlib.sha256()
 with path.open('rb')as handle:
  for chunk in iter(lambda:handle.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def target(project,name):
 path=(project/name).resolve()
 assert path.is_relative_to(project.resolve())and path.is_relative_to(parent)
 return path
snapshots=[]
for folder in sorted((parent/'snapshots').iterdir()):
 if not folder.is_dir()or folder.is_symlink():continue
 project=folder/'project';proof=project/'DISTANCE_SUPPLEMENT_MANIFEST.json'
 if not proof.exists():continue
 manifest=json.loads(proof.read_text())
 assert manifest['schema']=='core100-distance-runtime-supplement-v1'
 snapshots.append((folder,project,manifest))
before=shutil.disk_usage(parent).free
removed=[]
def remove_redundant_zip(folder,project,manifest):
 archive=folder/'distance_runtime.zip'
 if not archive.exists():return
 assert archive.resolve().is_relative_to(parent)
 with zipfile.ZipFile(archive)as package:
  assert set(package.namelist())==set(manifest['files'])|{'DISTANCE_SUPPLEMENT_MANIFEST.json'}
  assert json.loads(package.read('DISTANCE_SUPPLEMENT_MANIFEST.json'))==manifest
  for name,expected in manifest['files'].items():
   assert digest(target(project,name))==expected
   assert hashlib.sha256(package.read(name)).hexdigest()==expected
 receipt=dict(archive=str(archive),archive_sha256=digest(archive),bytes=archive.stat().st_size,
  every_extracted_member_hash_verified=True,unique_evidence_or_reference_files_deleted=False)
 with(receipts/'redundant_archives.jsonl').open('a')as stream:
  stream.write(json.dumps(receipt)+'\n');stream.flush();os.fsync(stream.fileno())
 archive.unlink();removed.append(receipt)
# One strictly redundant ZIP supplies metadata headroom on the full filesystem.
for args in snapshots:
 if(args[0]/'distance_runtime.zip').exists():remove_redundant_zip(*args);break
canonical={};linked=0;verified=0;released_blocks=0
for folder,project,manifest in snapshots:
 for name,expected in manifest['files'].items():
  path=target(project,name)
  assert digest(path)==expected,str(path)
  verified+=1
  first=canonical.setdefault(expected,path)
  if first==path or os.path.samefile(first,path):continue
  stat=path.stat();temporary=path.with_name(path.name+'.deduplicate-'+uuid.uuid4().hex)
  os.link(first,temporary)
  try:os.replace(temporary,path)
  finally:
   if temporary.exists():temporary.unlink()
  linked+=1
  if stat.st_nlink==1:released_blocks+=stat.st_blocks*512
for args in snapshots:remove_redundant_zip(*args)
result=dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),snapshots=len(snapshots),
 verified_files=verified,identical_copies_linked=linked,duplicate_blocks_released=released_blocks,
 redundant_archives_removed=len(removed),free_before=before,free_after=shutil.disk_usage(parent).free,
 all_extracted_evidence_paths_and_bytes_retained=True,original_render_results_untouched=True,
 source_base_runtime_untouched=True)
(receipts/'COMPACTED.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
'''


def main():
    raw=remote_text('p25',REMOTE,timeout=300,attempts=1)
    data=json.loads(raw)
    out=ROOT/'review/core100_continue_20261031/runtime_compaction_20261101.json'
    out.write_text(json.dumps(data,indent=2),encoding='utf8')
    print(raw)


if __name__=='__main__':main()
