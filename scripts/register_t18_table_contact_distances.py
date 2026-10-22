"""Collect T18 searches and bind only each matching published source context.

All source candidates remain present, including failed/pending/no-flip searches.
This does not admit reference videos automatically or filter generated failures.
"""
import collections
import json
from pathlib import Path
import subprocess
import inspect
from scripts.probe_verification_cache import verify_probe_files
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT, distances


def nearest_distance(theta,intervals,span):
    values=[distances(theta,bracket=w['bracket']) for w in intervals]
    low=min(v['distance_lower'] for v in values)/span;high=min(v['distance_upper'] for v in values)/span
    label=('near' if high<=.05 else 'mid' if .05<low<=high<=.15 else 'far' if low>.15 else None)
    return dict(status='resolved' if label else 'ambiguous',bin=label,normalized_absolute_interval=[low,high],
                scope='nearest of the observed left/right local intervals, not a globally unique critical root')


REMOTE='''import json,gzip,hashlib,os
from pathlib import Path
VERIFY_FUNCTION
base=Path(BASE);allplans=json.loads((base/'inputs/plan_all567.json').read_text());plans=[];results=[];resource_recovery_ids=set();probe_progress={}
cache_path=base/'collector_probe_digest_cache.json';cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
for j in allplans:
 c=j['base_config'];plans.append(dict(job_id=j['job_id'],sample_id=j['sample_id'],revision=j['revision'],theta=c['experiment']['parameter']['parameter_value'],parameter_unit=c['experiment']['parameter']['parameter_unit'],
  family_id=c['experiment']['parameter']['parameter_name'],seed=c['seed'],normalization_domain=j['normalization_domain'],reference_label=j['reference_label'],reference_state_sha256=j['reference_state_sha256']))
for rootname in ['run','legacy_run','asset_retry_run']+sorted(p.name for p in base.glob('resource_parallel_20261022_*') if p.is_dir()):
 root=base/rootname;p=root/'status.json';status=json.loads(p.read_text()) if p.exists() else []
 history=root/'status_before_resource_recovery_20261021.json'
 if history.exists():
  cohort={r['job_id'] for r in json.loads(history.read_text()) if r['status']=='failed' and 'GPU free-memory' in r.get('error','')}
  resource_recovery_ids.update(cohort)
  for job_id in cohort:probe_progress[job_id]=max(probe_progress.get(job_id,0),len(list((root/job_id).glob('*/receipt.json'))))
 status_by_id={r['job_id']:r for r in status}
 # A resumed worker may currently be before an already completed job in its
 # sequential plan. Canonical results remain valid during that partial status.
 for canonical in root.glob('*/result.json'):
  r=json.loads(canonical.read_text())
  if r['job_id'] not in status_by_id or status_by_id[r['job_id']]['status']!='conditional_event_search_completed':status_by_id[r['job_id']]=r
 status=list(status_by_id.values())
 for r in status:
  if r['status']=='source_event_reproduced':continue
  if r['status']!='conditional_event_search_completed':results.append(dict(r,source_root=str(root)));continue
  canonical=root/r['job_id']/'result.json'
  if not canonical.exists():raise ValueError('completed job has no final receipt')
  r=json.loads(canonical.read_text());receipts=[]
  for path in (root/r['job_id']).glob('*/receipt.json'):
   v=json.loads(path.read_text());sp=Path(v['state_path'])
   if not sp.exists() and sp.suffix=='.json' and sp.with_suffix('.json.gz').exists():sp=sp.with_suffix('.json.gz');v['state_path']=str(sp)
   v['state_path']=verify_probe_files(v,path.parent,cache)
   # Full per-frame contact evidence remains in the immutable remote receipt.
   # Transfer its hash and measurement fields once, not again inside r.probes.
   v.pop('contact_evidence',None)
   v['receipt_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
   v['receipt_path']=str(path)
   receipts.append(v)
  r.pop('probes',None)
  results.append(dict(r,verified_probe_receipts=receipts,source_root=str(root),canonical_result_sha256=hashlib.sha256(canonical.read_bytes()).hexdigest()))
temp=cache_path.with_name(cache_path.name+'.'+str(os.getpid())+'.tmp');temp.write_text(json.dumps(cache));temp.replace(cache_path)
print(json.dumps(dict(plans=plans,results=results,resource_recovery_ids=sorted(resource_recovery_ids),resource_recovery_probe_progress=probe_progress)))
'''


def main():
    launch=json.loads((ROOT/'t18_table_contact_search_launch_20261020.json').read_text())
    base=str(Path(launch['root']).parent).replace('\\','/')
    query=REMOTE.replace('BASE',repr(base)).replace('VERIFY_FUNCTION',inspect.getsource(verify_probe_files))
    evidence=json.loads(remote_text(launch['host'],query,timeout=600));(ROOT/'t18_search_evidence_20261020.json').write_text(json.dumps(evidence,indent=2))
    plans={r['job_id']:r for r in evidence['plans']};results={}
    for r in evidence['results']:
        previous=results.get(r['job_id'])
        if previous is None or previous['status']!='conditional_event_search_completed':results[r['job_id']]=r
    originals={r['sample_id']:r for r in map(json.loads,(ROOT/'t18_table_contact_source_events_20261020.jsonl').read_text().splitlines())}
    candidates=[];bindings=[]
    for key,plan in plans.items():
        original=originals[plan['sample_id']];r=results.get(key)
        row=dict(original,job_id=key,normalization_domain=plan['normalization_domain'],parameter_unit=plan['parameter_unit'],
                 target_event='upper_nonpulled_book_on_table_at_end',reference_admission='pending_visual_event_contract',
                 inversion_eligibility='independent',search_status=r['status'] if r else 'pending')
        if r and r['status']=='conditional_event_search_completed':
            if r['reference_state_sha256']!=plan['reference_state_sha256'] or r['source_seed']!=plan['seed']:raise ValueError('result belongs to another source context')
            probes={v['theta']:v for v in r['verified_probe_receipts']}
            if probes[plan['theta']]['label']!=plan['reference_label']:raise ValueError('source event not reproduced')
            for w in r['local_intervals']:
                a,b=w['bracket']
                if a not in probes or b not in probes or probes[a]['label']==probes[b]['label']:raise ValueError('interval endpoints not actual opposite outcomes')
            row['boundary_intervals']=r['local_intervals'];span=plan['normalization_domain'][1]-plan['normalization_domain'][0]
            if not r['local_intervals']:row['boundary_status']='no_observed_flip_on_original_grid'
            else:
                row['boundary_status']='conditional_local_intervals';row['distance']=nearest_distance(plan['theta'],r['local_intervals'],span)
                for w in r['local_intervals']:
                    d=distances(plan['theta'],bracket=w['bracket'])
                    bindings.append(dict(row,original_boundary_interval=w['bracket'],**d,normalization_span=span,
                        normalized_distance_lower=d['distance_lower']/span,normalized_distance_upper=d['distance_upper']/span,
                        family_id=plan['family_id'],refinement_job_id=key,refinement_source_seed=plan['seed'],
                        original_reference_kind='conditional_original_backend_event_interval_for_exact_source_video',
                        numerical_evidence=str((ROOT/'t18_search_evidence_20261020.json').resolve())))
        candidates.append(row)
    out=ROOT/'original_value_distance_ledger'
    (out/'t18_table_contact_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bindings))
    (ROOT/'t18_event_reference_candidates_20261020.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in candidates))
    summary=dict(source_candidates=len(candidates),completed_contexts=sum(r['search_status']=='conditional_event_search_completed' for r in candidates),
        contexts_with_intervals=sum(r.get('boundary_status')=='conditional_local_intervals' for r in candidates),
        contexts_without_observed_flip=sum(r.get('boundary_status')=='no_observed_flip_on_original_grid' for r in candidates),
        failed_contexts=sum(r['search_status']=='failed' for r in candidates),pending_contexts=sum(r['search_status']=='pending' for r in candidates),
        unique_bound_samples=len({r['sample_id'] for r in bindings}),distance_bins=dict(collections.Counter(r.get('distance',{}).get('bin') for r in candidates if r.get('distance'))),
        original_source_candidates_retained=True,formal_nearacc_admissions=0)
    cohort=set(evidence.get('resource_recovery_ids',[]))
    if cohort-set(plans):raise ValueError('resource recovery cohort outside original T18 plan')
    recovered=[dict(job_id=r['job_id'],sample_id=r['sample_id'],status=r['search_status'],boundary_status=r.get('boundary_status'),distance=r.get('distance'),completed_probe_files=evidence.get('resource_recovery_probe_progress',{}).get(r['job_id'],0)) for r in candidates if r['job_id'] in cohort]
    recovery=dict(total=len(cohort),completed=sum(r['status']=='conditional_event_search_completed' for r in recovered),failed=sum(r['status']=='failed' for r in recovered),pending=sum(r['status']=='pending' for r in recovered),with_distances=sum(r['distance'] is not None for r in recovered),started_jobs=sum(r['completed_probe_files']>0 for r in recovered),completed_probe_files=sum(r['completed_probe_files'] for r in recovered),probe_count_scope='progress only; complete jobs retain full state and config digest verification')
    summary['resource_recovery_cohort']=recovery
    (ROOT/'t18_resource_recovery_cohort_progress_20261021.json').write_text(json.dumps(dict(summary=recovery,jobs=recovered),indent=2))
    (ROOT/'t18_event_distance_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
