"""Collect the single T16 source replay without starting further work."""
import hashlib
import json
from pathlib import Path

from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'review/core100_v2_resolution_20261102'
REMOTE = r'''
import hashlib,json,math,time
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t16_gpu_source_20261102')
dispatch=json.loads((root/'DISPATCH.json').read_text())
process=Path('/proc')/str(dispatch['pid'])
state=root/'physics.json'
if not state.exists():
 print(json.dumps(dict(status='running'if process.exists()else'failed_without_state',
  elapsed_s=time.time()-dispatch['started_unix'],pid=dispatch['pid'],
  log_tail=(root/'run.log').read_text()[-1000:])))
 raise SystemExit
raw=state.read_bytes();candidate=json.loads(raw)
original_path=Path('/data_cached/wangzijun_p25/liyuhan/core100_t16_t17_window_exact_20261030/state.json')
original_raw=original_path.read_bytes();original=json.loads(original_raw)
assert hashlib.sha256(original_raw).hexdigest()==dispatch['source_state_sha256']
assert len(candidate['frames'])==len(original['frames'])==210
clock=['dt','substeps','constraint_timeconst','box_box_detection','use_gjk_collision']
differences={k:[original['scene_overrides'].get(k),candidate['scene_overrides'].get(k)]for k in clock
 if original['scene_overrides'].get(k)!=candidate['scene_overrides'].get(k)}
errors=[]
for left,right in zip(original['frames'][4:155],candidate['frames'][4:155]):
 a={o['name']:o for o in left['objects']};b={o['name']:o for o in right['objects']}
 assert set(a)==set(b)and left['frame_index']==right['frame_index']
 for name in a:
  errors.append((math.dist(a[name]['position'],b[name]['position']),left['frame_index'],name))
def contact_frames(data):
 return sorted({f['frame_index']for f in data['frames'][5:155]for c in f.get('original_exterior_contacts',f.get('contacts',[]))
  if {c.get('entity_a'),c.get('entity_b')}=={'t16_folder','t16_downstream_box'}})
hit=contact_frames(candidate);original_hit=contact_frames(original)
peak=max(errors)
out=dict(status='completed',clip_id='T16_C04',backend=json.loads((root/'runtime_backend.json').read_text()),
 source_state_path=str(original_path),source_state_sha256=dispatch['source_state_sha256'],
 state_path=str(state),state_sha256=hashlib.sha256(raw).hexdigest(),
 config_sha256=hashlib.sha256((root/'config.json').read_bytes()).hexdigest(),
 source_theta=dispatch['source_theta'],horizon_s=5.0,start_frame=4,end_frame=154,
 source_solver_differences=differences,actual_published_trajectory_comparison=True,
 max_position_error_m=peak[0],max_error_frame=peak[1],max_error_object=peak[2],
 exact_published_positions_reproduced=peak[0]==0,
 event='folder_downstream_contact',reference_label=int(bool(original_hit)),replay_label=int(bool(hit)),
 original_contact_frames=original_hit,replay_contact_frames=hit,
 original_exterior_contact_rule_used=True,
 native_peak_penetration_m=max([0.]+[c['penetration_m']for f in candidate['frames'][5:155]for c in f.get('contacts',[])]),
 process_exists=process.exists(),new_parameter_searches_started=0,
 source_replays_started=1,source_files_modified=False,
 scope='Original GPU32 source replay only; no boundary or whole-video physics certification inferred.')
print(json.dumps(out))
'''


def main():
    result = rpc(P21_OPTIONS, 'p25', REMOTE)
    if result['status'] == 'completed':
        raw = json.dumps(result, indent=2).encode()
        digest = hashlib.sha256(raw).hexdigest()
        path = WORK / ('t16_gpu_source_' + digest[:12] + '.json')
        if path.exists():
            assert path.read_bytes() == raw
        else:
            path.write_bytes(raw)
        (WORK / 'T16_GPU_SOURCE_RESULT.json').write_text(json.dumps(
            dict(path=path.relative_to(ROOT).as_posix(), sha256=digest), indent=2), encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
