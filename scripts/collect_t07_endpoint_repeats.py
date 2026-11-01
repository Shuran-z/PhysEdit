"""Collect completed endpoint repetitions without replacing published labels."""
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT

CODE=r'''
import json,hashlib
from pathlib import Path
b=Path('/data_cached/wangzijun_p25/liyuhan/t07_B_endpoint_repeats_20261030')
job=json.loads((b/'plan.json').read_text())[0];out=[]
for i in range(2):
 root=b/('repeat_'+str(i));folder=root/job['sample_id']/format(job['source_theta'],'.12g');p=folder/'receipt.json'
 if not p.exists():continue
 r=json.loads(p.read_text());assert hashlib.sha256((folder/'physics.json').read_bytes()).hexdigest()==r['state_sha256'];assert hashlib.sha256((folder/'config.json').read_bytes()).hexdigest()==r['config_sha256']
 out.append(dict(repeat=i,observed_label=r['label'],published_reference_label=job['source_label'],reference_reproduced=r['label']==job['source_label'],contact_evidence=r.get('contact_evidence'),state_sha256=r['state_sha256'],config_sha256=r['config_sha256'],consumed_experiment_random_seed=r['config']['experiment'].get('random_seed'),preserve_render_settings=True))
print(json.dumps(dict(planned_repeats=2,completed_repeats=len(out),remaining_repeats=2-len(out),results=out,published_truth_overwritten=False,source_endpoint_resolved=bool(out) and all(r['reference_reproduced'] for r in out) and len(out)==2)))
'''
if __name__=='__main__':
    text=remote_text('p25',CODE,timeout=40,attempts=1)
    (ROOT/'t07_endpoint_repeats_summary_20261030.json').write_text(text,encoding='utf8');print(text)
