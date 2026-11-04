"""Read back the two bounded T16 GPU probes and their original event rule."""
import hashlib
import json
from pathlib import Path
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import hashlib,importlib.util,json,time
from pathlib import Path
source=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t16_gpu_source_20261102')
root=source/'endpoints';dispatch=json.loads((root/'DISPATCH.json').read_text())
old=Path('/data_cached/wangzijun_p25/liyuhan/core100_t16_c04_sealed_window_v2_20261030')
deployment=json.loads((old/'deployment.json').read_text())
for name,digest in deployment['sources'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
spec=importlib.util.spec_from_file_location('original_t16_worker',old/'worker.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
assert hashlib.sha256((old/'jobs.json').read_bytes()).hexdigest()==dispatch['original_job_sha256']
job=json.loads((old/'jobs.json').read_text())[0]
rows=[]
for point in dispatch['points']:
 folder=Path(point['folder']);path=folder/'physics.json'
 if not path.exists():
  rows.append(dict(theta=point['theta'],status='running'if Path('/proc',str(point['pid'])).exists()else'failed_without_state',
   log_tail=(folder/'run.log').read_text()[-300:]));continue
 raw=path.read_bytes();state=json.loads(raw);configraw=(folder/'config.json').read_bytes();config=json.loads(configraw)
 assert hashlib.sha256(configraw).hexdigest()==point['config_sha256']
 expected=worker.intervention(job,point['theta'])
 assert config['dynamic_objects']==expected['dynamic_objects']and config['experiment']==expected['experiment']
 fields=['dt','substeps','constraint_timeconst','box_box_detection','use_gjk_collision']
 assert all(config['scene_overrides'].get(k)==job['base_config']['scene_overrides'].get(k)for k in fields)
 assert config['seed']==job['base_config']['seed']
 assert state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame']==1/state['render']['fps']
 labels,peak=worker.observe(state,job)
 backend=json.loads((folder/'runtime_backend.json').read_text());assert backend['backend']=='gpu32'
 rows.append(dict(theta=point['theta'],status='completed',labels=labels,native_peak_m=peak,
  quality_passed=peak<=.001,state_path=str(path),state_sha256=hashlib.sha256(raw).hexdigest(),
  config_sha256=point['config_sha256'],actual_original_intervention_verified=True,
  original_seed_solver_and_clock_verified=True,backend=backend))
result=dict(clip_id='T16_C04',status='completed'if all(r['status']=='completed'for r in rows)else'pending',
 event='folder_downstream_contact',source_theta=job['theta'],normalization_domain=job['domain'],horizon_s=job['horizon_s'],
 source_state_sha256=job['state_sha256'],source_config_sha256=job['config_sha256'],points=rows,
 elapsed_s=(max(Path(p['state_path']).stat().st_mtime for p in rows)if all(r['status']=='completed'for r in rows)else time.time())-dispatch['started_unix'],new_parameter_searches_started=1,source_files_modified=False,
 scope='Original-renderer GPU32 local interval under unchanged source clock, seed and materials; not a global or numerically converged physical threshold.')
print(json.dumps(result))
'''


def main():
    result=rpc(P21_OPTIONS,'p25',REMOTE)
    if result['status']=='completed':
        raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
        path=WORK/('t16_gpu_endpoints_'+digest[:12]+'.json')
        if not path.exists():path.write_bytes(raw)
        else:assert path.read_bytes()==raw
        (WORK/'T16_GPU_ENDPOINT_RESULT.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':main()
