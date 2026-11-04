"""Exercise the unchanged public TXT exporter against the staged prompt pool."""
from pathlib import Path
import gzip,hashlib,json,os,shutil,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/full_prompt_audit_20261102/publish';D=OUT/'stage/releases/physedit';SANDBOX=OUT/'export_consumer_check'
def main():
 assert json.loads((OUT/'PUBLICATION_VERIFICATION.json').read_text())['status']=='PASS'
 SANDBOX.mkdir(exist_ok=True)
 shutil.copyfile(OUT/'export_txt_current.py',SANDBOX/'export_txt.py')
 for name in ['prompt_texts.jsonl.gz','video_prompt_bindings.jsonl.gz']:
  if not (SANDBOX/name).exists():os.link(D/'prompts'/name,SANDBOX/name)
 archive=SANDBOX/'isaac_T14_prompts.zip';assert not archive.exists()
 subprocess.run([sys.executable,str(SANDBOX/'export_txt.py'),'--engine','isaac','--scene','T14','--output',str(archive)],check=True)
 n=0;videos=0
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for r in map(json.loads,gzip.open(D/'prompts/video_prompt_bindings.jsonl.gz','rt',encoding='utf8')):
   if r['engine']!='isaac' or r['scene']!='T14':continue
   videos+=1
   for h,path in zip(r['prompt_sha256'],r['prompt_files']):assert hashlib.sha256(z.read(path)).hexdigest()==h;n+=1
  assert len(z.namelist())==n==2880 and videos==960
 report=dict(status='PASS',unchanged_public_exporter=True,engine='isaac',scene='T14',videos=videos,exported_txt_files=n,all_exported_hashes_match_current_bindings=True)
 (D/'checks/PROMPT_TXT_EXPORT_CHECK_20261102.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
if __name__=='__main__':main()
