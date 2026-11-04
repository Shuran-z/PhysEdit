"""Read completed original gap probes; do not substitute the speed axis."""
import gzip
import hashlib
import json
from pathlib import Path

from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,SG_OPTIONS,SG
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import gzip,hashlib,importlib.util,inspect,json,math
from pathlib import Path
root=Path('/data/yangkaiyuan/core100_continue_original_20261031/T20_C01')
job=json.loads((root/'jobs.json').read_text())[0]
spec=importlib.util.spec_from_file_location('t20_gap_observer',root/'worker.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
wanted=[job['theta'],.3,.4318359375,.43212890625,.45]
out=[]
for theta in wanted:
 p=root/'T20_C01/profile_0'/format(theta,'.12g');receipt=json.loads((p/'receipt.json').read_text())
 raw=gzip.decompress(Path(receipt['state_path']).read_bytes());assert hashlib.sha256(raw).hexdigest()==receipt['state_sha256']
 cp=p/'config.json';packed=cp.read_bytes();assert hashlib.sha256(packed).hexdigest()==receipt['config_sha256']
 state=json.loads(raw);config=json.loads(packed);expected=module.intervention(job,theta)
 assert config['dynamic_objects']==expected['dynamic_objects']
 for key in ['dt','substeps','constraint_timeconst']:
  assert config['scene_overrides'].get(key)==job['base_config']['scene_overrides'].get(key)
 assert config.get('seed')==job['base_config'].get('seed')and config.get('random_seed')==job['base_config'].get('random_seed')
 labels,peak=module.observe(state,job)if len(inspect.signature(module.observe).parameters)==2 else module.observe(state)
 assert labels==receipt['labels']
 contacts=[c for f in state['frames'][5:155]for c in f.get('contacts',[])]
 pairs={}
 for c in contacts:
  pair=' / '.join(sorted([str(c.get('entity_a')),str(c.get('entity_b'))]))
  pairs[pair]=max(pairs.get(pair,0),c.get('penetration_m',0))
 named={o['name']for o in config['dynamic_objects']}
 dynamic_peak=max([c.get('penetration_m',0)for c in contacts if c.get('entity_a')in named and c.get('entity_b')in named],default=0)
 out.append(dict(theta=theta,labels=labels,receipt_path=str(p/'receipt.json'),state_path=receipt['state_path'],
  state_sha256=receipt['state_sha256'],config_sha256=receipt['config_sha256'],
  original_seed_solver_and_intervention_verified=True,physics_frame_period_s=state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame'],
  original_quality_passed=receipt['quality_passed'],all_contact_peak_m=peak,named_object_contact_peak_m=dynamic_peak,
  top_contact_pairs=sorted(pairs.items(),key=lambda x:-x[1])[:6]))
print(json.dumps(dict(clip_id='T20_C01',family=job['family'],source_theta=job['theta'],sample_id=job['sample_id'],
 normalization_domain_in_job=job.get('normalization_domain'),observed=out,source_config_sha256=job['config_sha256'],
 original_intervention_source_sha256=hashlib.sha256((root/'worker.py').read_bytes()).hexdigest(),
 new_simulations=0,source_files_modified=False)))
'''

def main():
    result=rpc(SG_OPTIONS,SG,REMOTE);raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    WORK.mkdir(exist_ok=True);path=WORK/('t20_original_gap_'+digest[:12]+'.json')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    (WORK/'T20_ORIGINAL_GAP.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(dict(family=result['family'],points=[dict(theta=r['theta'],labels=r['labels'],peak=r['all_contact_peak_m'],named_peak=r['named_object_contact_peak_m'])for r in result['observed']])))

if __name__=='__main__':main()
