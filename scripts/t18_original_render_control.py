"""Test original rendering on two divergent sources; never amend reference labels."""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
try:
    from scripts.audit_t18_source_failures import compare
except ModuleNotFoundError:
    from audit_t18_source_failures import compare


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--root',required=True);p.add_argument('--gpu',required=True);a=p.parse_args()
    base,root=Path(a.base),Path(a.root);root.mkdir(exist_ok=True,parents=True)
    jobs={j['job_id']:j for j in json.loads((base/'inputs/plan_all567.json').read_text())}
    candidates=[json.loads(f.read_text()) for f in (base/'failure_audit_20261023/results').glob('*.json') if f.name not in ['summary.json','progress.json']]
    selected=[r for r in candidates if r.get('category')=='different_contact_history' and r.get('first_error_over_1mm_frame')==24][:2]
    renderer='/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T16_T20_v1/scripts/render_sample.py'
    results=[]
    for case in selected:
        j=jobs[case['job_id']]
        for repeat in [0,1]:
            dest=root/(j['job_id']+'_'+str(repeat));dest.mkdir(exist_ok=True);final=dest/'comparison.json'
            if final.exists():results.append(json.loads(final.read_text()));continue
            try:
                while float(subprocess.check_output(['nvidia-smi','-i',a.gpu,'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())<12288:time.sleep(20)
                c=copy.deepcopy(j['base_config'])
                for k in ['save_video','save_first_rgb','save_last_rgb','save_rgb_frames_dir']:
                    if c['render'].get(k):c['render'][k]=str(dest/Path(c['render'][k]).name)
                c['annotations']['save_path']=str(dest/'physics.json');cp=dest/'config.json';cp.write_text(json.dumps(c))
                env=dict(os.environ,CUDA_VISIBLE_DEVICES=a.gpu,OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
                with (dest/'run.log').open('w') as log:r=subprocess.run(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',renderer,'--config',str(cp)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=3600)
                if r.returncode:raise RuntimeError('original full-render execution failed')
                raw=(dest/'physics.json').read_bytes();state=json.loads(raw);sp=Path(j['source_event']['source_state_path']);stored=sp.read_bytes()
                if hashlib.sha256(stored).hexdigest()!=j['reference_state_sha256']:raise ValueError('source identity changed')
                source=json.loads(gzip.decompress(stored) if sp.suffix=='.gz' else stored)
                result=dict(job_id=j['job_id'],repeat=repeat,status='original_render_control_completed',reference_labels_changed=0,
                    seed=c['seed'],render_config=c['render'],original_numeric_comparison=case,
                    control_state_sha256=hashlib.sha256(raw).hexdigest(),**compare(c,source,state))
                (dest/'physics.json.gz').write_bytes(gzip.compress(raw,mtime=0));(dest/'physics.json').unlink()
            except Exception as exc:result=dict(job_id=j['job_id'],repeat=repeat,status='failed',error=str(exc),reference_labels_changed=0)
            final.write_text(json.dumps(result,indent=2));results.append(result);(root/'status.json').write_text(json.dumps(results))
    print(json.dumps(dict(planned=len(selected)*2,completed=sum(r['status']=='original_render_control_completed' for r in results),failed=sum(r['status']=='failed' for r in results))))


if __name__=='__main__':main()
