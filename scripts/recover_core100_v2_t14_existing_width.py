"""Read the completed T14-C03 original-setting width slice, without simulation."""
import gzip
import base64
import hashlib
import json
import zlib
from pathlib import Path
from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import gzip,hashlib,json,math
from pathlib import Path
root=Path(PLAN['root']);job=json.loads((root/'jobs.json').read_text())[0]
assert job['clip_id']=='T14_C03'and job['family']=='channel_throat_width_m'and job['theta']==.0325
assert job['base_config']['dynamic_objects']==SOURCE_SPECS
for k,v in SOURCE_PHYSICS.items():assert job['base_config']['scene_overrides'].get(k)==v,(k,v,job['base_config']['scene_overrides'].get(k))
source=PLAN['result']['probes'][0]
assert source['theta']==job['theta']
points=[]
selected=[source]
for b in PLAN['result']['intervals']:
 if b['event']!='passed_channel':continue
 for t in b['bracket']:
  selected.append(next(p for p in PLAN['result']['probes']if p['theta']==t))
for p in selected:
 path=Path(p['state_path']);raw=gzip.decompress(path.read_bytes());assert hashlib.sha256(raw).hexdigest()==p['state_sha256']
 configraw=(path.parent/'config.json').read_bytes();assert hashlib.sha256(configraw).hexdigest()==p['config_sha256']
 config=json.loads(configraw);state=json.loads(raw)
 for k,v in SOURCE_PHYSICS.items():assert config['scene_overrides'].get(k)==v
 assert config.get('seed')==job['base_config'].get('seed')
 assert abs(state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame']*150-5)<1e-12
 objects={o['name']:o for o in config['dynamic_objects']};base={o['name']:o for o in job['base_config']['dynamic_objects']}
 expected=json.loads(json.dumps(base));delta=p['theta']-job['theta']
 for name in['t14v2_corridor_book_left','t14v2_corridor_book_right']:
  expected[name]['pose']['position'][1]+=(1 if base[name]['pose']['position'][1]>0 else-1)*delta/2
 # Compare floating-point translations within the original JSON precision.
 def equal(a,b):
  if isinstance(a,(int,float))and isinstance(b,(int,float)):return abs(a-b)<1e-12
  if isinstance(a,dict)and isinstance(b,dict):return set(a)==set(b)and all(equal(a[k],b[k])for k in a)
  if isinstance(a,list)and isinstance(b,list):return len(a)==len(b)and all(equal(x,y)for x,y in zip(a,b))
  return a==b
 assert equal(objects,expected)
 marker=CLASSIFICATION['marker_name'];exit_x=CLASSIFICATION['channel_exit_center_x_m']
 first=next((f['frame_index']for f in state['frames'][5:155]if next(o['position'][0]for o in f['objects']if o['name']==marker)>=exit_x),None)
 assert int(first is not None)==p['labels']['passed_channel']
 assert p['quality_passed']and p['backend']=='gpu32'
 points.append(dict(theta=p['theta'],label=int(first is not None),first_exit_frame=first,
  state_sha256=p['state_sha256'],config_sha256=p['config_sha256'],state_path=str(path),native_peak_m=p['native_peak_m'],
  original_physics_and_axis_verified=True))
print(json.dumps(dict(clip_id='T14_C03',points=points,intervals=[b for b in PLAN['result']['intervals']if b['event']=='passed_channel'],
 source_config_sha256=job['config_sha256'],source_repeat_diagnostic=PLAN['audit'],new_simulations=0,original_files_modified=False)))
'''


def main():
    registry,_=load();ref=next(r for r in registry['cases']if r['clip_id']=='T14_C03')
    archive=ROOT/'review/core100_continue_20261031/verified_probes_20261101T054328357637Z.json'
    plan=next(r for r in json.loads(archive.read_text(encoding='utf8'))if r['root'].endswith('/T14_C03_A'))
    bindings=json.loads((ROOT/'review/core100_binding_20261028/t14_original_source_binding_20261031.json').read_text(encoding='utf8'))
    binding=next(r for r in bindings if r['clip_id']=='T14_C03');statepath=ROOT/binding['source_state_path']
    original=json.loads(gzip.decompress(statepath.read_bytes()))
    assert hashlib.sha256(gzip.decompress(statepath.read_bytes())).hexdigest()==ref['source_state_sha256']
    fields=['dt','substeps','constraint_timeconst','box_box_detection','use_gjk_collision','gravity']
    physics={k:original['scene_overrides'].get(k)for k in fields}
    specs=[o.get('spec',o)for o in original['dynamic_objects']]
    code='PLAN='+repr(plan)+'\nSOURCE_SPECS='+repr(specs)+'\nSOURCE_PHYSICS='+repr(physics)+'\nCLASSIFICATION='+repr(original['experiment']['classification_contract'])+'\n'+REMOTE
    packed=base64.b64encode(zlib.compress(code.encode())).decode()
    result=rpc(P21_OPTIONS,'p25',"import base64,zlib;exec(zlib.decompress(base64.b64decode("+repr(packed)+")).decode())")
    result.update(reference_video_sha256=ref['reference_video_sha256'],source_state_sha256=ref['source_state_sha256'],
        original_reference_first_exit_frame=binding['first_exit_frame'],archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        horizon_s=5.0,axis='channel_throat_width_m',theta=ref['theta'])
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t14_existing_width_'+digest[:12]+'.json')
    if not path.exists():path.write_bytes(raw)
    else:assert path.read_bytes()==raw
    (WORK/'T14_EXISTING_WIDTH.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(dict(source_exit_frame=result['points'][0]['first_exit_frame'],original_exit_frame=result['original_reference_first_exit_frame'],intervals=result['intervals'])))


if __name__=='__main__':main()
