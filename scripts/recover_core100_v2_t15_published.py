"""Read original V11 trajectories and synchronized-view bindings; never simulate."""
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'review/core100_v2_resolution_20261102'
REMOTE = r'''
import copy,hashlib,json,math
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/liyuhan/ebb_new_outputs/t15/v11_20260914')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def normalized(x):
 if isinstance(x,float):return round(x,10)
 if isinstance(x,list):return[normalized(v)for v in x]
 if isinstance(x,dict):return{k:normalized(v)for k,v in x.items()}
 return x
def read(p,axis):
 raw=p.read_bytes();s=json.loads(raw);h=hashlib.sha256(raw).hexdigest()
 bp=p.with_name('media_binding.json');b=json.loads(bp.read_text());cp=Path(b['render_config']);c=json.loads(cp.read_text())
 assert b['physics_sha256']==b['media']['source_sha256']==c['trajectory_replay_sha256']==h
 assert b['render_config_sha256']==sha(cp)
 assert b['media']['source_render_poses_match']and b['media']['media_valid']and b['media']['frames']==len(s['frames'])==210
 assert b['camera_contract']=='one audited physics trajectory, three fixed synchronized views'
 ap=Path(b['actual_pose_audit']);assert json.loads(ap.read_text())['pass']
 d=s['time_diagnostic'];assert d['render_fps']==30 and abs(d['sim_dt']*d['physics_steps_per_render_frame']*150-5)<1e-12
 assert c['scene_overrides']['dt']==d['sim_dt']and c['render']['physics_steps_per_render_frame']==d['physics_steps_per_render_frame']
 assert s['physical_provenance']['precision_bits']==64
 objects={o['name']:copy.deepcopy(o.get('spec',o))for o in s['dynamic_objects']}
 driver=objects['t15v4_driver_book'];lap=objects['t15v4_closed_laptop'];table=objects['t15v4_tabletop_collision']
 margin=table['pose']['position'][0]+table['size'][0]/2-lap['pose']['position'][0]
 speed=math.dist(driver['motion']['initial_velocity'],[0,0,0])
 meta=c['sample_metadata'];assert abs(meta['laptop_edge_margin_m']-margin)<1e-10
 assert abs(meta['initial_velocity_mps']-speed)<1e-10
 assert abs(meta['impulse_ns']-driver['mass']*speed)<1e-10
 if axis=='driver_book_initial_speed_mps':
  theta=speed
  driver['motion']['initial_velocity']=[x/speed for x in driver['motion']['initial_velocity']]
 else:
  theta=margin
  for name in['t15v4_driver_book','t15v4_closed_laptop']:objects[name]['pose']['position'][0]+=theta
 profile=copy.deepcopy(s['physical_provenance']);profile.pop('config_sha256')
 camera=copy.deepcopy(b['cameras'][0]);assert camera['camera_id']=='cam01';camera.pop('filename')
 context=normalized(dict(objects=objects,solver=c['scene_overrides'],profile=profile,
  camera=camera,background=c['experiment']['background_id'],background_anchor=c['background_anchor'],
  runtime_forces=c.get('runtime_forces'),runtime_impulses=c.get('runtime_impulses'),clock=d))
 digest=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
 fs=s['frames'][5:155];assert [f['frame_index']for f in fs]==list(range(5,155))
 hits=[f['frame_index']for f in fs for contact in f.get('contacts',[])if{contact.get('entity_a'),contact.get('entity_b')}=={'t15v4_closed_laptop','t15v4_floor_phone'}]
 minimum=min(next(o['position'][2]for o in f['objects']if o['name']=='t15v4_closed_laptop')for f in fs)
 assert all('contacts'in f for f in fs)and 'all solver steps sampled'in profile['contact_aggregation']
 label=int(minimum<-.15)if axis=='driver_book_initial_speed_mps'else int(bool(hits))
 r=dict(sample_id=s['sample_id'],state_path=str(p),state_sha256=h,theta=theta,label=label,
  fixed_context_sha256=digest,media_binding_sha256=sha(bp),render_config_sha256=sha(cp),
  original_physics_config_sha256=profile.get('config_sha256',s['physical_provenance']['config_sha256']),
  actual_pose_audit_sha256=sha(ap),first_laptop_phone_contact_frame=min(hits,default=None),minimum_laptop_world_z_m=minimum,
  horizon_s=5.,camera='cam01',calibrated_source_id=meta.get('calibrated_source_id'))
 return r,context,b
cases=[]
for target in TARGETS:
 source,context,b=read(Path(target['state_path']),target['parameter'])
 assert source['sample_id']==target['sample_id']and source['state_sha256']==target['source_state_sha256']
 assert abs(source['theta']-target['theta'])<1e-10 and source['label']==target['label']
 assert sha(Path(target['video_path']))==target['reference_video_sha256']
 native_video=Path(b['media']['video_output'])/b['cameras'][0]['filename']
 assert sha(native_video)==target['reference_video_sha256']
 prefix=target['sample_id'].split('__formal')[0]
 paths=list((root/'formal').glob(prefix+'__formal_*/metadata/physics.json'))
 paths+=list((root/'deliverymoon').glob(prefix+'__formal_*/metadata/physics.json'))
 matches=[];other=[];errors=[]
 for p in sorted(set(paths)):
  try:
   candidate,ctx,_=read(p,target['parameter'])
   if candidate['fixed_context_sha256']==source['fixed_context_sha256']:matches.append(candidate)
   else:other.append(dict(sample_id=candidate['sample_id'],theta=candidate['theta'],context_sha256=candidate['fixed_context_sha256'],
    context_differing_keys=[k for k in context if context[k]!=ctx[k]]))
  except Exception as e:errors.append(dict(path=str(p),error_type=type(e).__name__,error=str(e)))
 bytheta={}
 for p in matches:bytheta.setdefault(p['theta'],[]).append(p)
 conflicting={str(t):ps for t,ps in bytheta.items()if len({p['label']for p in ps})>1}
 values=sorted((t,ps)for t,ps in bytheta.items()if str(t)not in conflicting)
 intervals=[dict(event=target['event'],bracket=[a,b],endpoint_labels=[pa[0]['label'],pb[0]['label']],
  endpoints=[pa,pb])for(a,pa),(b,pb)in zip(values,values[1:])if pa[0]['label']!=pb[0]['label']]
 cases.append(dict(target,source=source,matched_original_records=matches,other_contexts=other,read_errors=errors,
  conflicting_theta_labels=conflicting,intervals=intervals,
  scope='Original V11 published observations, exact simulator/profile and 5s target; no unique or fine physical root claim.'))
print(json.dumps(dict(cases=cases,new_simulations=0,source_files_modified=False)))
'''


def main():
    data, _ = load()
    p = ROOT / 'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json'
    points = {r['clip_id']: r['points'][0] for r in json.loads(p.read_text(encoding='utf8'))}
    targets = []
    for r in data['cases']:
        if r['scene_id'] != 'T15':
            continue
        cid = r['clip_id']
        identity = json.loads((ROOT / 'review/core100_remaining74_admission_20261101/reference_review' / cid / 'IDENTITY.json').read_text(encoding='utf8'))
        assert identity['video_sha256'] == r['reference_video_sha256']
        event = next(iter(r['reference_events']))
        targets.append(dict(clip_id=cid, sample_id=r['sample_id'], parameter=r['parameter'], theta=r['theta'],
            label=r['reference_events'][event], event=event, source_state_sha256=r['source_state_sha256'],
            reference_video_sha256=r['reference_video_sha256'], state_path=points[cid]['state_path'], video_path=identity['video_path']))
    result = rpc(P21_OPTIONS, 'p25', 'TARGETS=' + repr(targets) + '\n' + REMOTE)
    result['source_readback_sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    raw = json.dumps(result, indent=2).encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = WORK / ('t15_original_published_' + digest[:12] + '.json')
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    (WORK / 'T15_ORIGINAL_PUBLISHED.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(), sha256=digest), indent=2), encoding='utf8')
    print(json.dumps([dict(clip_id=c['clip_id'], matched=len(c['matched_original_records']),
        intervals=[b['bracket']for b in c['intervals']], errors=c['read_errors'], conflicts=list(c['conflicting_theta_labels']))for c in result['cases']]))


if __name__ == '__main__':
    main()
