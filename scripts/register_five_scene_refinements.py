"""Bind verified conditional refinements while preserving every published row."""
import collections
import hashlib
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT, distances

BASES = ['t01_published_event_sample_distances', 't04_t05_supplemental_sample_distances',
         't08_supplemental_sample_distances', 't11_supplemental_sample_distances']
LAUNCHES = [('five_scene_boundary_launch_20261020.json', 'five_scene_prepared_plan_20261020.json'),
            ('five_scene_alternate_seed_launch_20261020.json', 'five_scene_alternate_seed_plan_20261020.json'),
            ('t11_original_p29_boundary_launch_20261020.json', 't11_original_p29_boundary_plan_20261020.json'),
            ('t11_verified_p26_producer_launch_20261020.json', 't11_verified_p26_producer_plan_20261020.json')]


def identity(row):
    return (row['scene_id'], row['family_id'], row['target_event'],
            tuple(row['endpoint_sample_ids']), tuple(row['original_boundary_interval']))


def bind(rows, matches):
    output=[]; count=0
    for source in rows:
        row=dict(source); pair=matches.get(identity(row))
        if pair:
            job, result=pair
            span=job['normalization_domain'][1]-job['normalization_domain'][0]
            if span <= 0: raise ValueError('invalid original normalization domain')
            d=distances(row['theta'],bracket=result['bracket'])
            row.update(published_scan_interval=row['original_boundary_interval'],
                       original_boundary_interval=result['bracket'], **d,
                       normalization_domain=job['normalization_domain'], normalization_span=span,
                       normalized_distance_lower=d['distance_lower']/span,
                       normalized_distance_upper=d['distance_upper']/span,
                       refinement_job_id=job['job_id'], refinement_status='original_backend_conditional_interval',
                       backend_sources=result['backend_sources'], execution_sources=result['execution_sources'],
                       refinement_source_seed=job['endpoints'][job.get('seed_endpoint',0)]['config'].get('random_seed'),
                       refinement_seed_endpoint=job.get('seed_endpoint',0),
                       refinement_execution_host=job.get('refinement_execution_host'),
                       verified_production_host=job.get('production_host'),
                       production_completion_receipts=job.get('production_completion_receipts'),
                       refinement_scope='source endpoint seed held fixed; published labels and states retained',
                       formal_nearacc_eligible=False)
            count+=1
        output.append(row)
    return output,count


def collect(launch):
    code=r'''
import pathlib,json,hashlib,gzip
launch=LAUNCH
root=pathlib.Path(launch['root']); p=root/'status.json'
rows=json.loads(p.read_text()) if p.exists() else []
sha=lambda b:hashlib.sha256(b).hexdigest()
for row in rows:
 if row['status']!='refined_local_interval':continue
 if json.loads((root/row['job_id']/'result.json').read_text())!=row:raise ValueError('canonical result mismatch')
 for key in ['backend_sources','execution_sources']:
  for path,digest in row[key].items():
   if sha(pathlib.Path(path).read_bytes())!=digest:raise ValueError('source changed: '+path)
 for probe in row['probes']:
  sp=pathlib.Path(probe['state_path'])
  if root.resolve() not in sp.resolve().parents:raise ValueError('state outside run')
  stored=sp.read_bytes()
  if sha(stored)!=probe['stored_state_sha256'] or sha(gzip.decompress(stored))!=probe['state_sha256']:raise ValueError('numeric state changed')
  if sha((sp.parent/'config.json').read_bytes())!=probe['config_sha256']:raise ValueError('numeric config changed')
  if probe['backend_sources']!=row['backend_sources'] or probe['execution_sources']!=row['execution_sources']:raise ValueError('probe provenance mismatch')
canary=pathlib.Path(launch.get('canary_root',launch['root']))/'status.json'
resource=root/'resource_status.json'
print(json.dumps(dict(rows=rows,canary=json.loads(canary.read_text()) if canary.exists() and 'canary_root' in launch else [],resource=json.loads(resource.read_text()) if resource.exists() else {})))
'''.replace('LAUNCH',repr(launch))
    p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',launch['host'],'python3 -'],input=code.encode(),capture_output=True,timeout=240)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    return json.loads(p.stdout)


def main():
    matches={}; by_scene=collections.defaultdict(collections.Counter); evidence=[]
    planned=collections.defaultdict(set);outcomes={}
    for filename,planfile in LAUNCHES:
        if not (ROOT/filename).exists():continue
        launch=json.loads((ROOT/filename).read_text(encoding='utf-8-sig'))
        jobs=json.loads((ROOT/planfile).read_text(encoding='utf-8')); plan={j['job_id']:dict(j,refinement_execution_host=launch['host']) for j in jobs}
        data=collect(launch); evidence.append(dict(launch=launch,**data))
        for job in jobs:
            planned[job['scene_id']].add(job['job_id'])
            if job.get('seed_endpoint',0):by_scene[job['scene_id']]['alternate_seed_attempts']+=1
        for row in data['canary']:by_scene[row['scene_id']]['canary_'+row['status']]+=1
        for row in data['rows']:
            job=plan[row['job_id']]
            prior=outcomes.get(row['job_id'])
            if prior is None or prior['status']!='refined_local_interval':outcomes[row['job_id']]=row
            if row['status']!='refined_local_interval':continue
            if row['backend_sources']!=job['backend_sources']:raise ValueError('wrong original backend')
            if row.get('conditional_seed_endpoint',0)!=job.get('seed_endpoint',0):raise ValueError('conditional seed origin mismatch')
            if row['source_state_sha256']!=[e['state_sha256'] for e in job['endpoints']]:raise ValueError('wrong published states')
            if row['endpoint_labels']!=[e['label'] for e in job['endpoints']] or len(set(row['endpoint_labels']))!=2:raise ValueError('wrong source outcomes')
            a,b=row['bracket'];lo,hi=job['bracket']
            if not lo<=a<b<=hi or b-a>job['tolerance']*1.000001:raise ValueError('invalid refined bracket')
            labels={p['theta']:p['label'] for p in row['probes']}
            if labels.get(a)!=row['endpoint_labels'][0] or labels.get(b)!=row['endpoint_labels'][1]:raise ValueError('final endpoints lack opposite evidence')
            source=job['source_window'];key=identity(dict(scene_id=job['scene_id'],family_id=job['family_id'],target_event=job['target_event'],endpoint_sample_ids=source['endpoint_sample_ids'],original_boundary_interval=job['bracket']))
            if key in matches and not (job.get('production_host')==launch['host'] and matches[key][0].get('production_host')!=launch['host']):continue
            matches[key]=(job,row)
    out=ROOT/'original_value_distance_ledger';summaries={}
    for stem in BASES:
        base=out/(stem+'.jsonl')
        if not base.exists():continue
        rows=[json.loads(l) for l in base.read_text(encoding='utf-8').splitlines() if l.strip()]
        bound,count=bind(rows,matches)
        overlay=out/(stem+'_refined.jsonl');overlay.write_text(''.join(json.dumps(r)+'\n' for r in bound),encoding='utf-8')
        summaries[stem]=dict(base_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),overlay_sha256=hashlib.sha256(overlay.read_bytes()).hexdigest(),records=len(rows),refined_records=count)
    for row in outcomes.values():by_scene[row['scene_id']][row['status']]+=1
    for scene,ids in planned.items():
        values=by_scene[scene];values['planned']=len(ids)
        values['pending']=values['planned']-values['refined_local_interval']-values['failed']
    summary=dict(all20_completed=False,scenes=dict(by_scene),sources=summaries,
                 refined_intervals=len(matches),formal_admission_granted=False)
    (ROOT/'five_scene_refinement_evidence_20261020.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    (ROOT/'five_scene_refinement_summary_20261020.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))


if __name__=='__main__':main()
