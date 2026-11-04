import gzip,json,hashlib,subprocess,sys,zipfile
from pathlib import Path
O=Path('/data_cached/wangzijun_p25/config_bindings_20261031/remaining2241');D=O/'stage/releases/physedit';rows={x['canonical_video_id']:x for x in map(json.loads,gzip.open(D/'catalog/config_bindings.jsonl.gz','rt'))};cases=[('physedit_genesis_t04_3b2518652781d673__cam01',False),('physedit_genesis_t04_d04d6543c1b79c1a__cam01',True),('physedit_genesis_t01_3822bbc39d5b077a__cam01',False)];out=[]
for cid,valid in cases:
 p=subprocess.run([sys.executable,str(D/'tools/download_original_configs.py'),'--video-id',cid,'--output',str(O/'export_gate_test')],capture_output=True,text=True);assert (p.returncode==0)==valid
 out.append(dict(canonical_video_id=cid,expected_original_available=valid,exit_code=p.returncode,behavior_correct=True))
b=rows[cases[0][0]];assert b['status']=='UNRESOLVED';a=b['auxiliary_config'];assert a['document_type']=='metadata_derived_config'
with zipfile.ZipFile(D/'provenance/configs.zip') as z:assert hashlib.sha256(z.read(a['archive_member'])).hexdigest()==a['config_sha256']
r={'checks':out,'derived_copy_preserved_with_explicit_auxiliary_type':True,'no_derived_copy_exported_as_original':True};(O/'EXPORT_GATES_VERIFIED.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
