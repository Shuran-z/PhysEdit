"""Attest T04's saved physical inputs/seed; do not require absent config bytes."""
import base64
import hashlib
import json
from pathlib import Path
import zlib

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,gzip,hashlib,json,math
from pathlib import Path
root=Path('/data2/liyuhan/core100_continue_original_20261031/T04_C02')
job=json.loads((root/'jobs.json').read_text())[0]
dep=json.loads((root/'deployment.json').read_text())
for name,digest in dep['sources'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
def read_state(p):
 raw=Path(p).read_bytes();decoded=gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw
 return json.loads(decoded),hashlib.sha256(raw).hexdigest(),hashlib.sha256(decoded).hexdigest()
source,stored,decoded=read_state(TARGET['state_path'])
assert stored==TARGET['stored_state_sha256']and decoded==TARGET['decoded_state_sha256']
cfg=job['base_config'];specs={o['name']:o.get('spec',o)for o in source['dynamic_objects']}
object_match=specs=={o['name']:o for o in cfg['dynamic_objects']}
lighting={'raytracing','raytracing_lights','raytracing_env_map','raytracing_env_map_required','raytracing_env_euler','raytracing_env_encoding'}
solver_differences=[k for k in set(source['scene_overrides'])|set(cfg['scene_overrides'])if k not in lighting and source['scene_overrides'].get(k)!=cfg['scene_overrides'].get(k)]
def stripped(fs):return[{k:v for k,v in f.items()if k!='profile'}for f in fs]
force_match=stripped(source.get('runtime_forces',[]))==stripped(cfg.get('runtime_forces',[]))
seed=source['experiment'].get('seed')
def measure(s):
 frames=s['frames'][4:155];name='t04v3_chain_mug'
 track=[next(o for o in f['objects']if o['name']==name)for f in frames]
 q=track[0]['quaternion_xyzw'];disp=max(math.dist(track[0]['position'],o['position'])for o in track)
 angle=max(math.degrees(2*math.acos(min(1.,abs(sum(x*y for x,y in zip(q,o['quaternion_xyzw'])))/math.sqrt(sum(x*x for x in q)*sum(x*x for x in o['quaternion_xyzw'])))))for o in track)
 hits=[]
 for f in frames:
  contacts=f.get('original_exterior_contacts',f.get('contacts',[]))
  if any({c['entity_a'],c['entity_b']}=={'t04v3_chain_can_2',name}for c in contacts):hits.append(f['frame_index'])
 return dict(label=int(bool(hits)and(disp>=.04 or angle>=18)),mug_maximum_displacement_m=disp,mug_maximum_angle_deg=angle,contact_frames=hits)
rows=[]
for folder in ['0.15','source_repeat']:
 receipt=json.loads((root/'T04_C02/profile_0'/folder/'receipt.json').read_text())
 s,rs,ds=read_state(receipt['state_path']);assert ds==receipt['state_sha256']
 config_path=Path(receipt['state_path']).parent/'config.json';actual=json.loads(config_path.read_text())
 assert hashlib.sha256(config_path.read_bytes()).hexdigest()==receipt['config_sha256']
 errors={}
 for f,g in zip(source['frames'][4:155],s['frames'][4:155]):
  observed={o['name']:o for o in g['objects']}
  for o in f['objects']:errors[o['name']]=max(errors.get(o['name'],0),math.dist(o['position'],observed[o['name']]['position']))
 rows.append(dict(kind=folder,stored_state_sha256=rs,decoded_state_sha256=ds,state_path=receipt['state_path'],
  seed=actual['seed'],backend=receipt['backend'],measurement=measure(s),
  full_window_position_errors_m=errors,config_sha256=receipt['config_sha256']))
print(json.dumps(dict(clip_id='T04_C02',native_stored_sha256=stored,native_decoded_sha256=decoded,
 saved_source_seed=seed,old_random_seed_alias=source['experiment'].get('random_seed'),base_config_seed=cfg.get('seed'),
 physical_objects_match=object_match,solver_differences=solver_differences,runtime_force_match=force_match,
 source_frame_clock={k:source['render'].get(k)for k in['pre_static_frames','physics_steps_per_render_frame','fps']},
 config_frame_clock={k:cfg['render'].get(k)for k in['pre_static_frames','physics_steps_per_render_frame','fps']},
 source_measurement=measure(source),replays=rows,renderer_sources=dep['sources'],job_family=job['family'],
 original_config_byte_identity_claimed=False,source_physical_contract_attested=bool(object_match and not solver_differences and force_match and seed==cfg.get('seed')),
 simulations_started=0,full_trajectory_equivalence_claimed=False)))
'''


def main():
    data,_=load();r=next(c for c in data['cases']if c['clip_id']=='T04_C02')
    payload='TARGET='+repr(r['reference_native_state_binding'])+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    result=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t04_source_contract_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'T04_SOURCE_CONTRACT.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps({k:result[k]for k in ['saved_source_seed','old_random_seed_alias','base_config_seed','physical_objects_match','solver_differences','runtime_force_match','source_physical_contract_attested','source_measurement','replays']}))


if __name__=='__main__':main()
