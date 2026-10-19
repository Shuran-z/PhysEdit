"""Recover T20 original successful groups outside the historical release inventory."""
import json,subprocess
from pathlib import Path
from physedit.boundary import digest,distance
OUT=Path('review/scene_family_completion_20261018')
def main():
 source=Path('review/all_scene_boundary_audit_20261018/isaac_boundary_status.json')
 data=json.loads(source.read_text());rows=[]
 for cell,c in data['cells'].items():
  if not cell.startswith('T20__'):continue
  for family,g in c.get('groups',{}).items():
   if g['status']!='BOUNDARY_PASS_VISUAL_REVIEW_PENDING':continue
   for o in g['outputs']:rows.append(dict(cell=cell,family=family,original=o))
 code=r'''
import pathlib,json,hashlib
result=[]
for row in ROWS:
 try:
  root=pathlib.Path(row['original']['output']);p=root/'input.json';b=p.read_bytes();c=json.loads(b)
  result.append({**row,'config':{k:c[k] for k in ['parameter','production'] if k in c},'config_sha256':hashlib.sha256(b).hexdigest(),'source_hash_match':hashlib.sha256(b).hexdigest()==row['original']['input_sha256']})
 except Exception as e:result.append({**row,'error':type(e).__name__})
print(json.dumps(result))
'''
 import base64,gzip
 packed=base64.b64encode(gzip.compress(json.dumps(rows).encode())).decode()
 code='import base64,gzip,json\nROWS=json.loads(gzip.decompress(base64.b64decode('+repr(packed)+')))\n'+code
 p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','p25','python3 -'],input=code.encode(),capture_output=True,timeout=90);p.check_returncode()
 data=json.loads(p.stdout);(OUT/'t20_original_source_configs.json').write_bytes(p.stdout)
 registry=[]
 for r in data:
  if not r.get('source_hash_match'):continue
  c=r['config'];param=c['parameter'];prod=c['production'];bracket=prod.get('measured_bracket')
  if not bracket:continue
  row=dict(scene_id='T20',engine='isaac',source_output=r['original']['output'],cell=r['cell'],family_id='d'+r['family'],theta=param['value'],parameter=param,target_event='propagation_depth_ge_'+r['family'],reference_label=int(r['original']['depth']>=int(r['family'])),config_sha256=r['config_sha256'],boundary=dict(status='observed',source=str(source.resolve()),source_sha256=digest(source),intervals=[dict(bracket=bracket)]),blocking_reasons=['current_release_identity_pending','original_visual_admission_pending','normalization_not_registered'])
  row['distance']=distance(row);registry.append(row)
 (OUT/'t20_original_source_distances.json').write_text(json.dumps(registry,indent=2),encoding='utf-8')
 print(json.dumps(dict(source_outputs=len(rows),source_hash_matches=sum(r.get('source_hash_match',False) for r in data),source_distances=len(registry),not_added_to_historical_inventory=True)))
if __name__=='__main__':main()
