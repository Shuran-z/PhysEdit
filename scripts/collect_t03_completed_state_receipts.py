"""Attach all recovered T03 states and actual solver contracts to parameter rows."""
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    code=r'''
import pathlib,json,hashlib,gzip
r=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t03_current_recovery_20261019');out=[]
for p in r.glob('*.receipt.json'):
 receipt=json.loads(p.read_text())
 if receipt.get('status')!='verified_published_state' or receipt.get('extraction_schema_version')!=2:continue
 path=pathlib.Path(receipt['extracted_path']);prefix=b'';h=None
 # The recovery writer stores the complete metadata header before frames.
 # Read that prefix, rather than decompressing every trajectory a second time.
 with gzip.open(path,'rb') as stream:
  while h is None:
   block=stream.read(65536)
   if not block:raise ValueError('incomplete recovered metadata header')
   prefix+=block
   try:
    text=prefix.decode();start=text.index('"header":')+len('"header":');h=json.JSONDecoder().raw_decode(text,start+len(text[start:])-len(text[start:].lstrip()))[0]
   except (json.JSONDecodeError,UnicodeDecodeError):pass
 scene={k:v for k,v in h['scene_overrides'].items() if not k.startswith('raytracing')}
 timing={k:h['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']}
 contract=hashlib.sha256(json.dumps(dict(scene=scene,timing=timing),sort_keys=True).encode()).hexdigest()
 out.append(dict(sample_id=receipt['sample_id'],revision=receipt['revision'],reference_state_sha256=receipt['published_sha256'],
  solver_contract_sha256=contract,experiment=h['experiment'],actual_scene_physics=scene,actual_timing=timing,
  published_path=receipt['published_path'],extracted_path=receipt['extracted_path'],extracted_sha256_at_recovery=receipt['extracted_sha256'],
  metadata_prefix_sha256=hashlib.sha256(prefix).hexdigest(),verification_scope='metadata header read; full source identity comes from authenticated recovery receipt, not a new full-file rehash'))
if len(out)!=880 or len({x['sample_id'] for x in out})!=880:raise ValueError('selected 880 state recovery incomplete')
print(json.dumps(out))
'''
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True,timeout=240)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    rows=json.loads(p.stdout);(ROOT/'t03_completed_state_contracts_20261020.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(dict(recovered=len(rows),solver_contracts=len({x['solver_contract_sha256'] for x in rows}))))


if __name__=='__main__':main()
