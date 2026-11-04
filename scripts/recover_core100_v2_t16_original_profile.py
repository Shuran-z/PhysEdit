"""Recover completed native-profile T16-C04 points before repaired profiles.

Reads existing files only; no GPU/model or simulation is initialized.
"""
import hashlib
import json
from pathlib import Path
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import gzip,hashlib,json,math
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_t16_c04_sealed_window_v2_20261030')
job=json.loads((root/'jobs.json').read_text())[0];base=job['base_config']
raw=Path(job['original_state_path']).read_bytes();original=json.loads(gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw)
digests=[hashlib.sha256(raw).hexdigest(),hashlib.sha256(gzip.decompress(raw)).hexdigest()if raw[:2]==bytes([31,139])else hashlib.sha256(raw).hexdigest()]
assert job['state_sha256']in digests
source_specs={o['name']:o.get('spec',o)for o in original['dynamic_objects']}
base_specs={o['name']:o for o in base['dynamic_objects']}
source_specs_match=source_specs==base_specs
clock_fields=['dt','substeps','constraint_timeconst','box_box_detection','use_gjk_collision']
source_solver_differences={k:[original['scene_overrides'].get(k),base['scene_overrides'].get(k)]for k in clock_fields if original['scene_overrides'].get(k)!=base['scene_overrides'].get(k)}
out=[]
for rp in sorted((root/'T16_C04/profile_0').glob('*/receipt.json')):
 if rp.parent.name=='source_repeat':continue
 receipt=json.loads(rp.read_text());packed=Path(receipt['state_path']).read_bytes();decoded=gzip.decompress(packed)
 assert hashlib.sha256(decoded).hexdigest()==receipt['state_sha256']
 cp=rp.parent/'config.json';config_raw=cp.read_bytes();assert hashlib.sha256(config_raw).hexdigest()==receipt['config_sha256']
 state=json.loads(decoded);config=json.loads(config_raw)
 differences={k:[base['scene_overrides'].get(k),config['scene_overrides'].get(k)]for k in clock_fields if base['scene_overrides'].get(k)!=config['scene_overrides'].get(k)}
 assert config.get('seed')==base.get('seed')and config.get('random_seed')==base.get('random_seed')
 assert len(state['frames'])==210
 a,b=4,154
 hits=[f['frame_index']for f in state['frames'][a+1:b+1]for c in f.get('contacts',[])if {c.get('entity_a'),c.get('entity_b')}=={'t16_folder','t16_downstream_box'}]
 labels=dict(folder_downstream_contact=int(bool(hits)))
 assert labels['folder_downstream_contact']==receipt['labels']['folder_downstream_contact']
 out.append(dict(theta=receipt['theta'],labels=labels,first_contact_frame=min(hits,default=None),
  state_sha256=receipt['state_sha256'],config_sha256=receipt['config_sha256'],
  receipt_path=str(rp),state_path=receipt['state_path'],native_peak_m=receipt['native_peak_m'],
  quality_passed=receipt['quality_passed'],backend=receipt['backend'],
  original_solver_differences=differences,
  clock_s=(b-a)*state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame']))
print(json.dumps(dict(clip_id='T16_C04',sample_id=job['sample_id'],source_state_sha256=job['state_sha256'],
 source_config_sha256=job['config_sha256'],source_specs_match=source_specs_match,
 source_solver_differences=source_solver_differences,source_theta=job['theta'],points=out,
 new_simulations=0,source_files_modified=False)))
'''

def main():
    result=rpc(P21_OPTIONS,'p25',REMOTE);raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('t16_original_profile_'+digest[:12]+'.json')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    (WORK/'T16_ORIGINAL_PROFILE.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(dict(source_specs_match=result['source_specs_match'],source_solver_differences=result['source_solver_differences'],
        points=len(result['points']),valid=sum(p['quality_passed']and not p['original_solver_differences']for p in result['points']))))

if __name__=='__main__':main()
