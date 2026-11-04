from pathlib import Path
import json,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.boundary_ssh import remote_text,transport_options
from scripts.supplement_hf_transport import hf_transport
OUT=ROOT/'review/prompt_semantic_repair_20261102';REMOTE='/data_cached/wangzijun_p25/prompt_semantic_repair_20261102';PY='/home/wangzijun_p25/miniconda3/bin/python'
def main():
 phase=sys.argv[1]
 if phase=='transfer':
  assert json.loads((OUT/'INDEPENDENT_VERIFICATION.json').read_text())['status']=='PASS'
  archive=OUT/'stage.tar'
  with tarfile.open(archive,'w') as z:
   z.add(OUT/'stage',arcname='stage');z.add(ROOT/'scripts/publish_semantic_release_remote.py',arcname='publish_semantic_release_remote.py');z.add(OUT/'LOCAL_BASE_BACKUP_VERIFIED.json',arcname='LOCAL_BASE_BACKUP_VERIFIED.json')
  subprocess.run(['scp',*transport_options('p25'),'-o','BatchMode=yes',str(archive.relative_to(ROOT)),'p25:'+REMOTE+'/stage.tar'],cwd=ROOT,check=True)
  code=f'''from pathlib import Path
import tarfile,sys,runpy
r=Path({REMOTE!r})
with tarfile.open(r/'stage.tar') as z:
 for m in z.getmembers():assert (r/m.name).resolve().is_relative_to(r.resolve()) and not m.issym() and not m.islnk()
 z.extractall(r,filter='data')
sys.argv=['remote','prepare'];runpy.run_path(str(r/'publish_semantic_release_remote.py'),run_name='__main__')
'''
  print(remote_text('p25',code,timeout=600,attempts=1,python=PY),flush=True)
 else:
  port=int(sys.argv[2])
  with hf_transport(OUT,ports=(port,port+1,port+2)) as proxy:
   code=f"import runpy,sys;sys.argv=['remote',{phase!r},{proxy!r}];runpy.run_path({REMOTE+'/publish_semantic_release_remote.py'!r},run_name='__main__')"
   print(remote_text('p25',code,timeout=1100,attempts=1,python=PY),flush=True)
 for name in ['UPLOAD_PLAN.json','PUBLISHED.json','FRESH_VERIFIED.json','SCOPED_METADATA_CLEANUP_RECEIPT.json']:
  value=json.loads(remote_text('p25',f"from pathlib import Path;p=Path({REMOTE+'/'+name!r});print(p.read_text() if p.exists() else 'null')",timeout=45,attempts=1,python=PY))
  if value is not None:(OUT/name).write_text(json.dumps(value,indent=2),encoding='utf8')
if __name__=='__main__':main()
