"""Inspect original T20 speed sweeps without combining different contexts."""
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,gzip,hashlib,json,math
from pathlib import Path
production=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T16_T20_v1/production')
def norm(x):
 if isinstance(x,float):return round(x,10)
 if isinstance(x,list):return[norm(v)for v in x]
 if isinstance(x,dict):return{k:norm(v)for k,v in x.items()}
 return x
def read(p):
 raw=p.read_bytes();decoded=gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw;s=json.loads(decoded)
 objects={o['name']:copy.deepcopy(o.get('spec',o))for o in s['dynamic_objects']}
 v=objects['t20_book']['motion']['initial_velocity'];theta=math.dist(v,[0,0,0])
 assert abs(theta-s['experiment']['parameter']['parameter_value'])<1e-10
 objects['t20_book']['motion']['initial_velocity']=[x/theta for x in v]
 period=s['scene_overrides']['dt']*s['render']['physics_steps_per_render_frame'];assert abs(period*150-5)<1e-12
 context=norm(dict(objects=objects,solver=s['scene_overrides'],hold=s['render']['pre_static_frames'],steps=s['render']['physics_steps_per_render_frame'],
  runtime_forces=s.get('runtime_forces'),runtime_impulses=s.get('runtime_impulses')))
 def pos(f,n):return next(o['position']for o in f['objects']if o['name']==n)
 hits=[]
 for a,b in zip(['t20_book','t20_can','t20_box'],['t20_can','t20_box','t20_cup']):
  first=min(((f['frame_index'],c.get('physics_step_index',0))for f in s['frames'][5:155]for c in f.get('contacts',[])if{c.get('entity_a'),c.get('entity_b')}=={a,b}),default=None)
  hits.append(first)
 displacement=math.dist(pos(s['frames'][4],'t20_cup'),pos(s['frames'][154],'t20_cup'))
 label=0 if displacement<=.015 else int(hits==sorted(hits))if all(hits)else None
 return dict(sample_id=s.get('sample_id')or s['experiment'].get('sample_id')or(p.parent.parent.name if p.parent.parent.name.startswith('T20__')else None),theta=theta,label=label,
  state_path=str(p),stored_state_sha256=hashlib.sha256(raw).hexdigest(),decoded_state_sha256=hashlib.sha256(decoded).hexdigest(),
  fixed_context_sha256=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest(),
  cup_final_displacement_m=displacement,ordered_first_contacts=hits,horizon_s=5.)
cases=[]
for t in TARGETS:
 source=read(Path(t['state_path']))
 if t['source_state_sha256']not in[source['stored_state_sha256'],source['decoded_state_sha256']]:
  cases.append(dict(t,source=source,status='frozen_reference_and_old_numerical_source_digest_differ',points_read=0,same_context_points=0,read_errors=[],observed_values=[],intervals=[],
   scope='Do not transfer an original production sweep to a differently configured frozen canonical reference. Resolve both states before adopting a boundary.'))
  continue
 assert abs(source['theta']-t['theta'])<1e-10 and source['label']==t['label']
 prefix=t['sample_id'].rsplit('__p',1)[0]+'__p';points=[];errors=[]
 for p in sorted(production.glob(prefix+'*/metadata/*__cam01.json.gz')):
  try:points.append(read(p))
  except Exception as e:errors.append(dict(path=str(p),error_type=type(e).__name__,error=str(e)))
 own=[p for p in points if p['fixed_context_sha256']==source['fixed_context_sha256']]
 if not any(p['decoded_state_sha256']==source['decoded_state_sha256']for p in own):own.append(source)
 grouped={}
 for p in own:grouped.setdefault(p['theta'],[]).append(p)
 values=[]
 for theta,ps in sorted(grouped.items()):
  labels={p['label']for p in ps};values.append(dict(theta=theta,label=next(iter(labels))if len(labels)==1 else None,points=ps))
 intervals=[dict(event='complete_propagation_original',bracket=[a['theta'],b['theta']],endpoint_labels=[a['label'],b['label']],endpoints=[a['points'],b['points']])
  for a,b in zip(values,values[1:])if a['label']in[0,1]and b['label']in[0,1]and a['label']!=b['label']]
 cases.append(dict(t,source=source,points_read=len(points),same_context_points=len(own),read_errors=errors,
  observed_values=values,intervals=intervals,
  scope='Same original object specifications except book speed, solver and clock. No-flip observations are not proof of nonexistence.'))
print(json.dumps(dict(cases=cases,new_simulations=0,original_sources_modified=False)))
'''


def main():
    registry,_=load();readback_path=ROOT/'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json'
    points={r['clip_id']:r['points'][0]for r in json.loads(readback_path.read_text(encoding='utf8'))}
    targets=[dict(clip_id=r['clip_id'],sample_id=r['sample_id'],theta=r['theta'],label=r['reference_events']['complete_propagation_original'],
        reference_video_sha256=r['reference_video_sha256'],source_state_sha256=r['source_state_sha256'],state_path=points[r['clip_id']]['state_path'])
        for r in registry['cases']if r['scene_id']=='T20'and r['parameter']=='book_drive_speed']
    result=rpc(P21_OPTIONS,'p25','TARGETS='+repr(targets)+'\n'+REMOTE)
    result['source_readback_sha256']=hashlib.sha256(readback_path.read_bytes()).hexdigest()
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t20_saved_speed_'+digest[:12]+'.json')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    (WORK/'T20_SAVED_SPEED.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps([dict(clip_id=c['clip_id'],points_read=c['points_read'],same_context=c['same_context_points'],
        errors=c['read_errors'],intervals=[b['bracket']for b in c['intervals']],labels=[p['label']for p in c['observed_values']])for c in result['cases']]))


if __name__=='__main__':main()
