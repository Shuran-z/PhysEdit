"""Run the actual public exporter and hash every one of the 216000 exported files."""
from pathlib import Path
import gzip,hashlib,json,os,re,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'review/prompt_semantic_repair_20261102';D=OUT/'stage/releases/physedit';SANDBOX=OUT/'export_validation'
def main():
 audit=json.loads((OUT/'INDEPENDENT_VERIFICATION.json').read_text(encoding='utf8'));assert audit['status']=='PASS'
 backup=json.loads((OUT/'LOCAL_BASE_BACKUP_VERIFIED.json').read_text(encoding='utf8'));base=Path(backup['local_directory'])
 SANDBOX.mkdir(exist_ok=True)
 with zipfile.ZipFile(base/'releases/physedit/downloads/physedit_metadata.zip') as z:code=z.read('physedit/prompts/export_txt.py')
 (SANDBOX/'export_txt.py').write_bytes(code)
 for name in ['prompt_texts.jsonl.gz','video_prompt_bindings.jsonl.gz']:
  p=SANDBOX/name
  if not p.exists():os.link(D/'prompts'/name,p)
 clock_texts=0
 for item in map(json.loads,gzip.open(D/'prompts/prompt_texts.jsonl.gz','rt',encoding='utf8')):
  text=item['prompt']
  if re.search(r'\bframes?\s+\d',text,re.I):
   assert re.search(r'\b(?:fps|Hz)\b|\b(?:Frame|Controller) step\s+[-+0-9.eE/]+\s*s\b',text,re.I),('frame-index prompt missing controller clock',text)
   clock_texts+=1
 archive=SANDBOX/'all_216000_prompt_txt.zip';assert not archive.exists()
 subprocess.run([sys.executable,str(SANDBOX/'export_txt.py'),'--output',str(archive)],check=True)
 n=0;videos=0;seen=set()
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for row in map(json.loads,gzip.open(D/'prompts/video_prompt_bindings.jsonl.gz','rt',encoding='utf8')):
   videos+=1
   for h,path in zip(row['prompt_sha256'],row['prompt_files']):
    assert path not in seen;seen.add(path);assert hashlib.sha256(z.read(path)).hexdigest()==h;n+=1
  assert len(z.namelist())==n==216000 and videos==72000
 report=dict(status='PASS',unchanged_public_exporter_sha256=hashlib.sha256(code).hexdigest(),videos=videos,exported_prompt_files=n,all_exported_sha256_match=True,frame_index_texts_with_explicit_clock=clock_texts,missing_controller_clocks=0,export_zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
 target=D/'checks/TXT_ALL_VARIANTS_EXPORT_VERIFIED.json';target.write_text(json.dumps(report,indent=2),encoding='utf8');(OUT/target.name).write_text(json.dumps(report,indent=2),encoding='utf8')
 audit.update(txt_export_files_checked=n,txt_export_hash_check='PASS')
 for p in [OUT/'INDEPENDENT_VERIFICATION.json',D/'checks/PROMPT_SEMANTIC_AUDIT_20261102.json']:p.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
 check=json.loads((D/'checks/CHECK_REPORT.json').read_text(encoding='utf8'));check['all216000_txt_export_hashes_verified']=True
 check['previous_numeric_audit']=check.get('numeric_audit');check['numeric_audit']='PROMPT_SEMANTIC_AUDIT_20261102.json'
 (D/'checks/CHECK_REPORT.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf8')
 regression=json.loads((OUT/'REGRESSION_TESTS.json').read_text(encoding='utf8'));assert regression['status']=='PASS'
 (D/'checks/REGRESSION_TESTS.json').write_text(json.dumps(regression,indent=2),encoding='utf8')
 (D/'prompts/VIEW.html').write_text('''<!doctype html><meta charset="utf-8"><title>PhysEdit current prompts</title>
<h1>Current PhysEdit prompts</h1><p>Policy: semantic-units-display-dedup-v2-20261102. 72,000 videos and 216,000 English prompt bindings.</p>
<p>Units are dimensionally checked. Text uses at most 8 significant digits or shorter exact fractions, with relative display error at most 5e-8. Full precision parameters remain in metadata. Repeated facts are removed only with source evidence.</p>
<p><a href="../checks/PROMPT_SEMANTIC_AUDIT_20261102.json">Full semantic audit</a> / <a href="../checks/UNIT_DIMENSION_REGISTRY.json">Physical unit registry</a> / <a href="../checks/TXT_ALL_VARIANTS_EXPORT_VERIFIED.json">All TXT export hash checks</a></p>
<p><a href="prompt_texts.jsonl.gz">Current prompt text pool</a> / <a href="video_prompt_bindings.jsonl.gz">Current video bindings</a> / <a href="export_txt.py">TXT exporter</a></p>
<p>Current video bytes, simulation configurations, splits and frozen Core100 submitted inputs are preserved.</p>''',encoding='utf8')
 print(json.dumps(report),flush=True)
if __name__=='__main__':main()
