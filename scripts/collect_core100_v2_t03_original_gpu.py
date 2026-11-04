"""Read the original shared T03 GPU source without admitting a boundary."""
import hashlib
import json
from pathlib import Path
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import gzip,hashlib,json,math
from pathlib import Path
folder=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t03_original_gpu_20261102/T03_C01_source')
item=json.loads((folder/'DISPATCH.json').read_text());proc=Path('/proc',str(item['pid']),'cmdline')
if proc.exists()and str(folder/'config.json').encode()in proc.read_bytes():
 print(json.dumps(dict(status='running',pid=item['pid'],folder=str(folder))));raise SystemExit
def state(p):
 raw=Path(p).read_bytes();return json.loads(gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw),hashlib.sha256(raw).hexdigest()
def observe(s,native=False):
 names=dict(book_can={'t03v5_impulsed_book','t03v5_upper_edge_can'},
  can_shelf={'t03v5_upper_edge_can','t03v5_lower_transfer_ramp'},
  can_phone={'t03v5_upper_edge_can','t03v5_lower_edge_phone'},
  phone_floor={'t03v5_lower_edge_phone','t03v5_terminal_floor'})
 first={k:None for k in names};pre=s['render']['pre_static_frames']
 for f in s['frames'][4:155]:
  contacts=f['original_exterior_contacts']if native and f['frame_index']>=pre else f.get('contacts',[])
  for c in contacts:
   pair={c['entity_a'],c['entity_b']}
   for k,required in names.items():
    if pair==required and first[k]is None:first[k]=[f['frame_index'],c.get('physics_step_index',-1)]
 baseline=next(o['position'][2]for o in s['frames'][pre]['objects']if o['name']=='t03v5_lower_edge_phone')
 minimum=min(o['position'][2]for f in s['frames'][4:155]for o in f['objects']if o['name']=='t03v5_lower_edge_phone')
 drop=baseline-minimum
 return dict(first_contacts=first,phone_center_drop_from_original_pre_static_frame_m=drop,
  label=int(all(v is not None for v in first.values())and drop>.20),baseline_frame=pre,window=[4,154])
path=folder/'physics.json';assert path.exists(),'Source ended without complete state; inspect run.log'
source,digest=state(item['source_state_path']);assert digest==item['source_state_sha256']
replay,replay_digest=state(path);cfg=json.loads((folder/'config.json').read_text())
assert len(source['frames'])==len(replay['frames'])==210
backend=json.loads((folder/'runtime_backend.json').read_text());assert backend['backend']=='gpu32'
assert backend['actual_init_seed']==item['expected_actual_init_seed']
specs=lambda s:{o['name']:o.get('spec',o)for o in s['dynamic_objects']}
objects_match=specs(source)==specs(replay)=={o['name']:o for o in cfg['dynamic_objects']}
visual={'raytracing_env_encoding','raytracing_env_euler','raytracing_env_map','raytracing_lights','raytracing_env_map_required'}
physical_diff={k:[source['scene_overrides'].get(k),replay['scene_overrides'].get(k)]for k in set(source['scene_overrides'])|set(replay['scene_overrides'])if k not in visual and source['scene_overrides'].get(k)!=replay['scene_overrides'].get(k)}
by_actor={};first_above_1mm=None
for a,b in zip(source['frames'][4:155],replay['frames'][4:155]):
 old={o['name']:o for o in a['objects']}
 for o in b['objects']:
  error=math.dist(old[o['name']]['position'],o['position']);by_actor[o['name']]=max(by_actor.get(o['name'],0),error)
  if error>.001 and first_above_1mm is None:first_above_1mm=b['frame_index']
before=observe(source);after=observe(replay,True)
peak=max((dict(c,frame=f['frame_index'])for f in replay['frames'][5:155]for c in f.get('contacts',[])),key=lambda c:c.get('penetration_m',0),default={})
print(json.dumps(dict(status='completed',clip_id='T03_C01',source_state_sha256=digest,
 state_path=str(path),state_sha256=replay_digest,config_sha256=hashlib.sha256((folder/'config.json').read_bytes()).hexdigest(),
 reference_video_sha256=item['reference_video_sha256'],original_source=before,measurement=after,
 source_event_match=before['label']==after['label'],objects_match=objects_match,physical_solver_differences=physical_diff,
 backend=backend,source_maximum_position_error_by_actor_m=by_actor,first_position_error_above_1mm_frame=first_above_1mm,
 native_peak_penetration_m=peak.get('penetration_m',0),peak_native_contact=peak,formal_admission=False,
 source_hashes=item['source_hashes'],frozen_inputs_modified=False)))
'''


def main():
    result=rpc(P21_OPTIONS,'p25',REMOTE)
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t03_original_gpu_source_collect_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'T03_ORIGINAL_GPU_SOURCE_RESULT.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps(result))


if __name__=='__main__':main()
