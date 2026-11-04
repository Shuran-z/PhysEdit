"""Recover original published G-family outcomes; no new simulation or old labels."""
import base64
import hashlib
import json
from pathlib import Path
import zlib

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'benchmarks/t11_observable_events_candidate_v1_20261103'
REMOTE=r'''
import copy,gzip,hashlib,json,math
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/phyediting_t11_r011/formal_880_720p')
job=json.loads(Path('/data2/liyuhan/core100_continue_families_20261031/T11_C03__G_global_original/jobs.json').read_text())[0]
assert job['reference_video_sha256']==REFERENCE_VIDEO_SHA
assert job['state_sha256']==REFERENCE_STORED_SHA
assert hashlib.sha256(CONTRACT['helper_source'].encode()).hexdigest()==CONTRACT['helper_sha256']
exec(CONTRACT['helper_source'])
info=next(c for c in CONTRACT['cases']if c['clip_id']=='T11_C03')
assert info['source_no_op_exact']and info['all_eight_released_controlled_physics_match']
assert info['source_config_sha256']==job['config_sha256']
assert info['source_vector']==job['joint_source_nominal_parameters']
keys=['shape','collision_proxy','collision_proxy_size','size','mass','friction','restitution','pose','motion','fixed','kinematic']
def physics(spec):return{k:spec[k]for k in keys if k in spec}
def same(a,b):
 if isinstance(a,(int,float))and isinstance(b,(int,float)):return math.isclose(a,b,abs_tol=1e-9,rel_tol=1e-9)
 if type(a)!=type(b):return False
 if isinstance(a,dict):return set(a)==set(b)and all(same(a[k],b[k])for k in a)
 if isinstance(a,list):return len(a)==len(b)and all(same(x,y)for x,y in zip(a,b))
 return a==b
rows=[]
for n,(theta,vector)in enumerate(zip(info['joint_path']['coordinates'],info['joint_path']['nodes']),1):
 sid='T11R011__bg01_home_ase__g03_earth__G_global_'+str(n).zfill(2)
 folder=root/sid;p=folder/'annotations'/(sid+'__cam01.json.gz');video=folder/'videos'/(sid+'__cam01.mp4')
 raw=p.read_bytes();decoded=gzip.decompress(raw);state=json.loads(decoded);actual=state['experiment']['parameter']
 expected=t11_joint_intervention(job['base_config'],info['source_vector'],vector)
 assert actual['parameter_value']==vector
 actual_objects={o['name']:physics(o.get('spec',o))for o in state['dynamic_objects']}
 expected_objects={o['name']:physics(o)for o in expected['dynamic_objects']}
 mismatches=[k for k in set(actual_objects)|set(expected_objects)if not same(actual_objects.get(k),expected_objects.get(k))]
 parameter_mismatches=[k for k in expected['experiment']['parameter']if k not in actual or not same(actual[k],expected['experiment']['parameter'][k])]
 numerical_fields=['gravity','dt','substeps','use_gjk_collision','box_box_detection','enable_multi_contact','static_scene_collision','layout_collision','add_ground_plane']
 solver_matches=all(same(state['scene_overrides'].get(k),expected['scene_overrides'].get(k))for k in numerical_fields)
 assert state['render']['physics_steps_per_render_frame']==expected['render']['physics_steps_per_render_frame']
 assert len(state['frames'])==210
 video_sha=hashlib.sha256(video.read_bytes()).hexdigest()
 if n==6:
  assert video_sha==REFERENCE_VIDEO_SHA and hashlib.sha256(decoded).hexdigest()==REFERENCE_DECODED_SHA
 rows.append(dict(sample_id=sid,theta=theta,vector=vector,state_path=str(p),video_path=str(video),
  stored_state_sha256=hashlib.sha256(raw).hexdigest(),decoded_state_sha256=hashlib.sha256(decoded).hexdigest(),video_sha256=video_sha,
  physical_object_mismatches=mismatches,parameter_mismatches=parameter_mismatches,solver_matches=solver_matches,
  measurement=reference_events(state,condition_frame=4,end_frame=154)))
 del state
print(json.dumps(dict(rows=rows,original_family='original_G_global_path',source_coordinate=info['source_coordinate'],
 normalization_domain=[0.,1.],new_simulations=0,frozen_inputs_modified=False,
 scope='Original published trajectories, read under the new observable event; no replay source drift or CPU64 label transfer.')))
'''


def main():
    data,_=load();c=next(c for c in data['cases']if c['clip_id']=='T11_C03');native=c['reference_native_state_binding']
    contract=ROOT/'review/core100_continue_20261031/t11_original_global_path_contract_20261101.json'
    module=ROOT/'physedit/t11_visual_events.py'
    payload=module.read_text(encoding='utf8')+'\nCONTRACT='+repr(json.loads(contract.read_text()))+'\nREFERENCE_VIDEO_SHA='+repr(c['reference_video_sha256'])+'\nREFERENCE_STORED_SHA='+repr(native['stored_state_sha256'])+'\nREFERENCE_DECODED_SHA='+repr(native['decoded_state_sha256'])+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    r=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    r['event_definition_sha256']=hashlib.sha256(module.read_bytes()).hexdigest()
    r['original_path_contract_sha256']=hashlib.sha256(contract.read_bytes()).hexdigest()
    raw=json.dumps(r,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=OUT/('published_G_contrast_'+digest[:12]+'.json');path.write_bytes(raw)
    (OUT/'PUBLISHED_G_CONTRAST.json').write_text(json.dumps(dict(path=path.name,sha256=digest),indent=2))
    print(json.dumps([dict(theta=p['theta'],objects=p['physical_object_mismatches'],parameters=p['parameter_mismatches'],solver=p['solver_matches'],
      label=p['measurement']['events']['t11_driver_eraser_edge_fall_begins']['label'])for p in r['rows']]))


if __name__=='__main__':main()
