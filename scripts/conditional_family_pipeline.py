"""Check source points across families before processing each family's search queue."""
import argparse
import collections
import json
from pathlib import Path
import subprocess


def main():
    p=argparse.ArgumentParser()
    for key in ['plan','root','gpu','python','worker']:p.add_argument('--'+key,required=True)
    a=p.parse_args();root=Path(a.root);root.mkdir(parents=True,exist_ok=True)
    jobs=json.loads(Path(a.plan).read_text());counts=collections.Counter();canaries=[];backgrounds=collections.defaultdict(set)
    for job in jobs:
        key=(job['scene_id'],job['family_id'])
        # A missing background asset must not block an entire parameter family.
        background=job['base_config'].get('experiment',{}).get('background_id')
        if background is None:
            background=next((part for part in job['sample_id'].split('__') if part.startswith('bg')),job['sample_id'])
        counts[key]+=1
        if background not in backgrounds[key]:
            canaries.append(job);backgrounds[key].add(background)
    plan=root/'source_canaries.json';plan.write_text(json.dumps(canaries))
    common=[a.python,a.worker,'--root',str(root),'--gpu',a.gpu,'--python',a.python]
    phase=root/'pipeline_phase.json'
    phase.write_text(json.dumps(dict(status='source_checks',families=len(counts))))
    subprocess.run(common+['--plan',str(plan),'--source-only'],check=True)
    source_status=root/'status.json'
    if source_status.exists():(root/'source_stage_status.json').write_bytes(source_status.read_bytes())
    allowed=set()
    for file in root.glob('*/source_check.json'):
        check=json.loads(file.read_text())
        if check['eligible_events']:allowed.add((check['scene_id'],check['family_id']))
    active=[job for job in jobs if (job['scene_id'],job['family_id']) in allowed]
    blocked=sorted(set(counts)-allowed)
    plan=root/'active_plan.json';plan.write_text(json.dumps(active))
    phase.write_text(json.dumps(dict(status='conditional_searches',active_jobs=len(active),blocked_families=blocked)))
    subprocess.run(common+['--plan',str(plan)],check=True)
    phase.write_text(json.dumps(dict(status='listed_searches_ended',active_jobs=len(active),blocked_families=blocked)))


if __name__=='__main__':main()
