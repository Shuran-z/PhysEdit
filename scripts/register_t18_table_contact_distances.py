"""Collect T18 searches and bind only each matching published source context.

All source candidates remain present, including failed/pending/no-flip searches.
This does not admit reference videos automatically or filter generated failures.
"""
import collections
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT, distances


def nearest_distance(theta,intervals,span):
    values=[distances(theta,bracket=w['bracket']) for w in intervals]
    low=min(v['distance_lower'] for v in values)/span;high=min(v['distance_upper'] for v in values)/span
    label=('near' if high<=.05 else 'mid' if .05<low<=high<=.15 else 'far' if low>.15 else None)
    return dict(status='resolved' if label else 'ambiguous',bin=label,normalized_absolute_interval=[low,high],
                scope='nearest of the observed left/right local intervals, not a globally unique critical root')


REMOTE='''import json,gzip,hashlib
from pathlib import Path
base=Path(BASE);allplans=json.loads((base/'inputs/plan_all567.json').read_text());plans=[];results=[]
for j in allplans:
 c=j['base_config'];plans.append(dict(job_id=j['job_id'],sample_id=j['sample_id'],revision=j['revision'],theta=c['experiment']['parameter']['parameter_value'],parameter_unit=c['experiment']['parameter']['parameter_unit'],
  family_id=c['experiment']['parameter']['parameter_name'],seed=c['seed'],normalization_domain=j['normalization_domain'],reference_label=j['reference_label'],reference_state_sha256=j['reference_state_sha256']))
for rootname in ['run','legacy_run','asset_retry_run']:
 root=base/rootname;p=root/'status.json';status=json.loads(p.read_text()) if p.exists() else []
 for r in status:
  if r['status']=='source_event_reproduced':continue
  if r['status']!='conditional_event_search_completed':results.append(dict(r,source_root=str(root)));continue
  canonical=root/r['job_id']/'result.json'
  if not canonical.exists():raise ValueError('completed job has no final receipt')
  r=json.loads(canonical.read_text());receipts=[]
  for path in (root/r['job_id']).glob('*/receipt.json'):
   v=json.loads(path.read_text());sp=Path(v['state_path'])
   if not sp.exists() and sp.suffix=='.json' and sp.with_suffix('.json.gz').exists():sp=sp.with_suffix('.json.gz');v['state_path']=str(sp)
   raw=sp.read_bytes()
   if v.get('stored_state_sha256') and hashlib.sha256(raw).hexdigest()!=v['stored_state_sha256']:raise ValueError('stored state changed')
   if sp.suffix=='.gz':raw=gzip.decompress(raw)
   if hashlib.sha256(raw).hexdigest()!=v['state_sha256']:raise ValueError('numeric state changed')
   if hashlib.sha256((path.parent/'config.json').read_bytes()).hexdigest()!=v['config_sha256']:raise ValueError('probe config changed')
   receipts.append(v)
  results.append(dict(r,verified_probe_receipts=receipts,source_root=str(root),canonical_result_sha256=hashlib.sha256(canonical.read_bytes()).hexdigest()))
print(json.dumps(dict(plans=plans,results=results)))
'''


def main():
    launch=json.loads((ROOT/'t18_table_contact_search_launch_20261020.json').read_text())
    base=str(Path(launch['root']).parent).replace('\\','/')
    p=subprocess.run(['ssh','-o','BatchMode=yes',launch['host'],'python3 -'],input=REMOTE.replace('BASE',repr(base)).encode(),capture_output=True,timeout=180);p.check_returncode()
    evidence=json.loads(p.stdout);(ROOT/'t18_search_evidence_20261020.json').write_text(json.dumps(evidence,indent=2))
    plans={r['job_id']:r for r in evidence['plans']};results={r['job_id']:r for r in evidence['results']}
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
    (ROOT/'t18_event_distance_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
