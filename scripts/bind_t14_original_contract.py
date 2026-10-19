"""Recover T14's three original families and verify release video byte identity."""
import json,subprocess,collections,sys
from pathlib import Path
OUT=Path('review/original_search_tasks_20261018')
REMOTE=r'''
import pathlib,json,hashlib
root=pathlib.Path('/data2/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T14_v2_pose_gate')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
matrix=json.loads((root/'manifests/formal_r006/matrix.json').read_text())
results=[]
for r in matrix['rows']:
 p=root/'configs/formal_r006'/r['sample_id']/'cam01.json'
 row=dict(sample_id=r['sample_id'],manifest_row=r)
 try:
  c=json.loads(p.read_text());row['config_sha256']=sha(p)
  row['experiment']=c['experiment'];row['scene_overrides']=c.get('scene_overrides')
  row['videos']={}
  for cam in ['cam01','cam02','cam03']:
   video=root/'formal_r006'/r['sample_id']/'videos'/(r['sample_id']+'__'+cam+'.mp4')
   row['videos'][cam]={'path':str(video),'sha256':sha(video)} if video.exists() else {'missing':str(video)}
 except Exception as e:row['error']=str(e)
 results.append(row)
print(json.dumps(results))
'''

def main():
 if '--cached' in sys.argv:
  rows=json.loads((OUT/'t14_source_identity.json').read_text(encoding='utf-8'))
 else:
  p=subprocess.run(['ssh','-o','BatchMode=yes','p26','python3 -'],input=REMOTE.encode(),capture_output=True,timeout=300)
  (OUT/'t14_remote_stderr.txt').write_bytes(p.stderr);p.check_returncode()
  rows=json.loads(p.stdout);(OUT/'t14_source_identity.json').write_bytes(p.stdout)
 sources=json.loads((OUT/'p26_records.json').read_text())
 source=next(x for x in sources if x['path'].endswith('manifests/t14_independent_event_contract_v2.json'))
 contract=json.loads(source['text']);cal=contract['calibration_results_r006']
 inventory={r['sample_id']:r for r in map(json.loads,Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text().splitlines()) if r['event_id']=='T14' and r['engine']=='genesis'}
 out=[]
 for r in rows:
  m=r['manifest_row'];published=inventory.get(r['sample_id']);family=m['design_id'][0]
  bound=None;unit=None;theta=None;kind=None
  if family=='A':
   b=cal['A_gap_boundary_m_all_gravities'];bound=[b['jam_or_wedge_edge'],b['pass_and_hit_edge']];unit='m';theta=m['channel_gap_m'];kind='measured_bracket'
  elif family=='B':
   b=cal['B_yaw_boundaries'][m['gravity_id']];bound=[b['theta_minus_deg'],b['theta_plus_deg']];unit='deg';theta=m['marker_yaw_deg'];kind='calibrated_triplet_envelope'
  elif family=='C':
   b=cal['C_speed_boundaries_mps'][m['gravity_id']]
   param=r.get('experiment',{}).get('parameter',{});mass=param.get('marker_mass_kg')
   if isinstance(mass,(int,float)) and abs(param['trigger_impulse_magnitude_Ns']-mass*m['marker_speed_mps'])<1e-10:
    bound=[mass*b['stalled_edge'],mass*b['pass_and_hit_edge']];unit='N*s';theta=param['trigger_impulse_magnitude_Ns'];kind='measured_speed_bracket_converted_to_original_impulse_coordinate'
  matches=bool(published) and all(r.get('videos',{}).get(cam,{}).get('sha256')==v['sha256'] for cam,v in published['videos'].items())
  out.append(dict(sample_id=r['sample_id'],family=family,changed_variable=m.get('changed_variable'),
      background_id=m['background_id'],gravity_id=m['gravity_id'],release=published.get('release') if published else None,
      release_video_hashes_match=matches,contract_path=source['path'],contract_sha256=source['sha256'],
      config_sha256=r.get('config_sha256'),theta=theta,unit=unit,original_search_interval=bound,interval_kind=kind,
      distance_to_original_interval=([max(bound[0]-theta,theta-bound[1],0),max(abs(theta-bound[0]),abs(theta-bound[1]))] if bound else None),
      exact_threshold=None,near_bin=None,status='source_contract_linked_pending_event_and_context_validation' if matches and bound else 'requires_review',
      note='C uses the recorded mass to convert J=m*v, preserving the original impulse family. B triplet envelope is not an exact solved threshold.'))
 (OUT/'t14_original_family_bindings.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'total':len(out),'release_video_hash_matches':sum(r['release_video_hashes_match'] for r in out),'by_family':dict(collections.Counter(r['family'] for r in out))}))
if __name__=='__main__':main()
