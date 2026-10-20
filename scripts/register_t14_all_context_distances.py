"""Bind completed old-T14 original-family searches, keeping both sides.

Numerical replay and reference-video event admission remain separate. T14S is
not imported. No inversion eligibility filter is applied.
"""
import collections
import hashlib
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT,distances


def main():
    launch=json.loads((ROOT/'t14_formal_search_launch_20261019.json').read_text())
    plan_path=ROOT/'t14_formal_search_plan_20261019.json';plan=json.loads(plan_path.read_text());jobs={j['job_id']:j for j in plan['jobs']}
    release=json.loads(Path('docs/critical_boundary/RELEASE_SELECTION.json').read_text())['scenes']['T14']
    if any(a['config']['dataset_version']!=release['required_dataset_version'] for j in jobs.values() for a in j['anchors']):raise ValueError('T14S or another release cannot enter old-T14 results')
    code=r'''
import pathlib,json,hashlib
root=pathlib.Path(ROOT_DIRECTORY);rows=[]
for r in json.loads((root/'status.json').read_text()) if (root/'status.json').exists() else []:
 if r['status']!='scanned_original_triplet':rows.append(dict(result=r));continue
 probes=[]
 for p in (root/r['job_id']).glob('*/receipt.json'):
  v=json.loads(p.read_text())
  for key,name in [('state_sha256','physics.json'),('config_sha256','config.json')]:
   if hashlib.sha256((p.parent/name).read_bytes()).hexdigest()!=v[key]:raise ValueError('T14 numeric source changed')
  probes.append(v)
 rows.append(dict(result=r,probes=probes))
print(json.dumps(rows))
'''.replace('ROOT_DIRECTORY',repr(launch['root']))
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True,timeout=240)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    evidence=json.loads(p.stdout);(ROOT/'t14_all_context_search_evidence_20261020.json').write_text(json.dumps(evidence,indent=2))
    rows=[];candidates=[];no_flip=0;completed=0
    for entry in evidence:
        result=entry['result'];job=jobs[result['job_id']]
        if result['status']!='scanned_original_triplet':candidates.append(result);continue
        completed+=1;probes={r['theta']:r for r in entry['probes']}
        if result['renderer_sha256']!=plan['renderer']['sha256'] or result['analyzer_sha256']!=plan['analyzer']['sha256']:raise ValueError('original T14 sources changed')
        for probe in probes.values():
            if probe['renderer_sha256']!=result['renderer_sha256'] or probe['analyzer_sha256']!=result['analyzer_sha256']:raise ValueError('probe source mismatch')
        anchors={r['sample_id']:r for r in job['anchors']};domain=[min(r['theta'] for r in job['anchors']),max(r['theta'] for r in job['anchors'])];span=domain[1]-domain[0]
        if span<=0:raise ValueError('empty original T14 parameter range')
        if not result['intervals']:no_flip+=1
        for observed in result['anchors']:
            original=anchors[observed['sample_id']]
            if original['sha256']!=observed['original_config_sha256'] or original['theta']!=observed['theta']:raise ValueError('T14 reference identity mismatch')
            if probes[observed['theta']]['events']!=observed['events']:raise ValueError('T14 source-point event mismatch')
            base=dict(scene_id='T14',engine='genesis',repo_id=release['selected_repo'],revision=release['selected_revision'],sample_id=observed['sample_id'],family_id=job['family'],theta=observed['theta'],
                reference_config_sha256=original['sha256'],reference_state_sha256=probes[observed['theta']]['state_sha256'],
                reference_origin='original_backend_replay_at_selected_published_config',published_video_event_confirmed=False,
                normalization_domain=domain,normalization_span=span,normalization_source='original counterfactual family triplet span',
                inversion_eligibility='independent',formal_nearacc_eligible=False,job_id=job['job_id'])
            candidates.append(dict(base,events=observed['events'],boundary_intervals=result['intervals']))
            for interval in result['intervals']:
                a,b=interval['bracket'];event=interval['target_event']
                if a not in probes or b not in probes or [probes[a]['events'][event],probes[b]['events'][event]]!=interval['endpoint_labels']:raise ValueError('missing T14 opposite solver endpoints')
                d=distances(observed['theta'],bracket=[a,b])
                rows.append(dict(base,target_event=event,reference_label=observed['events'][event],original_boundary_interval=[a,b],**d,
                    normalized_distance_lower=d['distance_lower']/span,normalized_distance_upper=d['distance_upper']/span,
                    original_reference_kind='selected_old_T14_original_backend_refined_local_interval',
                    numerical_evidence_sha256=hashlib.sha256(json.dumps(entry,sort_keys=True).encode()).hexdigest()))
    (ROOT/'original_value_distance_ledger/t14_all_context_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    (ROOT/'t14_all_context_reference_candidates_20261020.json').write_text(json.dumps(candidates,indent=2))
    summary=dict(planned_contexts=len(jobs),completed_contexts=completed,failed_contexts=sum(e['result']['status']=='failed' for e in evidence),contexts_without_observed_flip=no_flip,
        bound_distinct_samples=len({r['sample_id'] for r in rows}),sample_event_interval_records=len(rows),events=dict(collections.Counter(r['target_event'] for r in rows)),formal_new_admissions=0)
    (ROOT/'t14_all_context_distance_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
