"""Recover the actual T03 cf-A released contact contrast; no simulation."""
import hashlib
import json
from pathlib import Path
from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,gzip,hashlib,json,math
from pathlib import Path
def norm(v):
 if isinstance(v,float):return round(v,9)
 if isinstance(v,list):return[norm(x)for x in v]
 if isinstance(v,dict):return{k:norm(x)for k,x in v.items()}
 return v
cases=[]
for target in TARGETS:
 raw=Path(target['state_path']).read_bytes();decoded=gzip.decompress(raw);state=json.loads(decoded)
 assert target['source_state_sha256']in[hashlib.sha256(raw).hexdigest(),hashlib.sha256(decoded).hexdigest()]
 video=Path(target['video_path']);assert hashlib.sha256(video.read_bytes()).hexdigest()==target['reference_video_sha256']
 theta=state['experiment']['parameter']['book_initial_speed_mps']
 assert theta==target['theta']and len(state['frames'])==210
 assert abs(state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame']*150-5)<1e-12
 pair={'t03v5_impulsed_book','t03v5_upper_edge_can'}
 hits=[f['frame_index']for f in state['frames'][5:155]for c in f.get('contacts',[])if{c.get('entity_a'),c.get('entity_b')}==pair]
 assert int(bool(hits))==target['label']
 objects={o['name']:copy.deepcopy(o.get('spec',o))for o in state['dynamic_objects']}
 velocity=objects['t03v5_impulsed_book']['motion']['initial_velocity'];assert abs(math.dist(velocity,[0,0,0])-theta)<1e-12
 objects['t03v5_impulsed_book']['motion']['initial_velocity']=[x/theta for x in velocity]
 p=copy.deepcopy(state['experiment']['parameter']);mass=p['book_mass_kg']
 assert abs(p['declared_one_shot_impulse_magnitude_Ns']-mass*theta)<1e-12
 assert all(abs(x-mass*v)<1e-12 for x,v in zip(p['declared_one_shot_impulse_vector_Ns'],velocity))
 for k in['parameter_value','book_initial_speed_mps','declared_one_shot_impulse_vector_Ns','declared_one_shot_impulse_magnitude_Ns']:p.pop(k)
 context=norm(dict(objects=objects,physics=state['scene_overrides'],parameters=p,
  camera1=state['render']['fixed_view'],pre_static_frames=state['render']['pre_static_frames'],
  physical_steps=state['render']['physics_steps_per_render_frame'],fps=state['render']['fps']))
 ctx=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
 cases.append(dict(clip_id=target['clip_id'],sample_id=target['sample_id'],theta=theta,event='book_contacts_upper_can',label=int(bool(hits)),
  fixed_context_sha256=ctx,reference_video_sha256=target['reference_video_sha256'],source_state_sha256=target['source_state_sha256'],
  decoded_state_sha256=hashlib.sha256(decoded).hexdigest(),first_contact_frame=min(hits,default=None),horizon_s=5.0,
  native_camera='cam03',condition_sha256=target['condition_sha256'],
  intervention='Original cf-A speed with the declared equivalent impulse J=m*v; all remaining recorded physical inputs fixed.',
  scope='Original released observed contact contrast; no unique root or fine-grid precision is claimed.'))
assert len({r['fixed_context_sha256']for r in cases})==1
assert[c['label']for c in cases]==[0,1]
print(json.dumps(dict(cases=cases,bracket=[c['theta']for c in cases],new_simulations=0,source_files_modified=False,
 reference_admission='Existing per-video book-contact admission is retained, not expanded to the full chain.',
 condition_images_byte_identical=cases[0]['condition_sha256']==cases[1]['condition_sha256'],
 condition_visual_review='Assistant checked both original condition images; same camera and actor layout, not independent human gold.')))
'''


def main():
    data,_=load();readback_path=ROOT/'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json'
    readback={r['clip_id']:r['points'][0]for r in json.loads(readback_path.read_text(encoding='utf8'))}
    targets=[]
    for cid in['T03_C04','T03_C05']:
        ref=next(r for r in data['cases']if r['clip_id']==cid);c=next(r for r in data['input_bindings']if r['clip_id']==cid)
        identity=json.loads((ROOT/'review/core100_remaining74_admission_20261101/reference_review'/cid/'IDENTITY.json').read_text(encoding='utf8'))
        assert identity['video_sha256']==ref['reference_video_sha256']
        targets.append(dict(clip_id=cid,sample_id=ref['sample_id'],theta=ref['theta'],label=ref['reference_events']['book_contacts_upper_can'],
            reference_video_sha256=ref['reference_video_sha256'],source_state_sha256=ref['source_state_sha256'],
            state_path=readback[cid]['state_path'],video_path=identity['video_path'],condition_sha256=c['condition_sha256']))
    result=rpc(P21_OPTIONS,'p25','TARGETS='+repr(targets)+'\n'+REMOTE)
    result['source_readback_sha256']=hashlib.sha256(readback_path.read_bytes()).hexdigest()
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t03_original_a_'+digest[:12]+'.json')
    if not path.exists():path.write_bytes(raw)
    else:assert path.read_bytes()==raw
    (WORK/'T03_ORIGINAL_A.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(dict(bracket=result['bracket'],cases=[(c['clip_id'],c['label'])for c in result['cases']])))


if __name__=='__main__':main()
