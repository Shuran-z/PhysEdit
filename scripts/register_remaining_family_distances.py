"""Join new family scans and verified fixed-source intervals into the existing ledger."""
import base64
import collections
import gzip
import inspect
import json
import hashlib
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT,distances
from scripts.probe_verification_cache import verify_probe_files


def bind(job,result):
    if any(result[k]!=job[k] for k in ['job_id','scene_id','family_id','sample_id']):raise ValueError('conditional job identity mismatch')
    if result['source_state_sha256']!=job['source_state_sha256'] or result['source_config_sha256']!=job['source_config_sha256']:
        raise ValueError('conditional search belongs to another source')
    if result['backend_sources']!=job['backend_sources']:raise ValueError('conditional backend changed')
    if result['source_seed']!=job['base_config'].get('seed',job['base_config'].get('random_seed')):raise ValueError('conditional seed changed')
    probes={p['theta']:p for p in result['probes']}
    for event in result['eligible_events']:
        if probes[job['theta']]['labels'][event]!=job['expected'][event]:raise ValueError('source event not reproduced')
    if any(theta not in probes for theta in job['grid']):raise ValueError('released intervention grid incomplete')
    span=job['normalization_domain'][1]-job['normalization_domain'][0]
    out=[]
    for interval in result['intervals']:
        event=interval['target_event'];a,b=interval['bracket']
        if event not in result['eligible_events'] or span<=0 or b-a>job['tolerance']*1.000001 or not job['normalization_domain'][0]<=a<b<=job['normalization_domain'][1]:
            raise ValueError('invalid conditional interval')
        if [probes[t]['labels'][event] for t in [a,b]]!=interval['labels'] or len(set(interval['labels']))!=2:
            raise ValueError('missing opposite endpoint evidence')
        # Retain an unseeded run as diagnostic evidence without promoting it
        # to a fixed-seed boundary. Its grid and endpoints are still checked.
        if result['source_seed'] is None:continue
        distance=distances(job['theta'],bracket=[a,b])
        out.append(dict(scene_id=job['scene_id'],engine='genesis',revision=job['revision'],sample_id=job['sample_id'],
            family_id=job['family_id'],theta=job['theta'],parameter_unit=job['parameter_unit'],target_event=event,
            reference_label=job['expected'][event],reference_state_sha256=job['source_state_sha256'],
            source_config_sha256=job['source_config_sha256'],fixed_context_sha256=job['fixed_context_sha256'],
            original_boundary_interval=[a,b],normalization_domain=job['normalization_domain'],normalization_span=span,
            normalized_distance_lower=distance['distance_lower']/span,normalized_distance_upper=distance['distance_upper']/span,
            refinement_job_id=job['job_id'],refinement_source_seed=result['source_seed'],**distance,
            backend_sources=result['backend_sources'],grid_scope=job.get('grid_scope','same_released_context_grid'),
            config_reconstruction=job.get('config_reconstruction'),
            visual_manifest_restoration=job.get('visual_manifest_restoration'),
            original_reference_kind='conditional_original_backend_interval_for_exact_source_configuration',
            scope='Only this source video is bound; no distances propagated to other seeds or topology variants.',
            formal_nearacc_eligible=False))
    return out


def packed(host,path):
    code="import pathlib,gzip,base64;print(base64.b64encode(gzip.compress(pathlib.Path(PATH).read_bytes())).decode())".replace('PATH',repr(path))
    return json.loads(gzip.decompress(base64.b64decode(remote_text(host,code,timeout=120))))


def atomic_text(path, text):
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(text,encoding='utf-8')
    temp.replace(path)


def fetch_queue(launch, code, cache_root):
    """Checkpoint each verified transport payload instead of restarting all queues."""
    identity={k:launch[k] for k in ['host','root','plan_sha256']}
    name=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    path=cache_root/(name+'.json.gz')
    try:
        data=json.loads(gzip.decompress(base64.b64decode(remote_text(launch['host'],code,timeout=600))))
    except Exception as exc:
        if not path.exists():raise
        saved=json.loads(gzip.decompress(path.read_bytes()))
        if saved['identity']!=identity:raise ValueError('queue checkpoint identity changed')
        return saved['data'],str(exc)
    temp=path.with_name(path.name+'.tmp')
    temp.write_bytes(gzip.compress(json.dumps(dict(identity=identity,data=data)).encode(),mtime=0))
    temp.replace(path)
    return data,None


def main():
    scan=json.loads((ROOT/'remaining_family_scans_launch_20261023.json').read_text())
    base=scan['root']+'/results/'
    ledger=ROOT/'original_value_distance_ledger'
    scan_errors=[]
    try:
        summary=packed(scan['host'],base+'summary.json');coverage=packed(scan['host'],base+'coverage.json')
        bindings=packed(scan['host'],base+'bindings.json')
    except Exception as exc:
        old=ROOT/'remaining_family_scan_summary_20261023.json'
        if not old.exists():raise
        summary=json.loads(old.read_text())
        scan_errors.append(dict(host=scan['host'],root=scan['root'],error=str(exc),retained_previous_scan=True))
    else:
        atomic_text(ROOT/'remaining_family_scan_summary_20261023.json',json.dumps(summary,indent=2))
        atomic_text(ROOT/'remaining_family_scan_coverage_20261023.json',json.dumps(coverage,indent=2))
        atomic_text(ledger/'remaining_family_scan_sample_distances.jsonl',''.join(json.dumps(r)+'\n' for r in bindings))
    marker=ROOT/'conditional_family_launches_20261023.json'
    launches=json.loads(marker.read_text()) if marker.exists() else []
    output=[];progress=[];errors=list(scan_errors)
    cache_root=ROOT/'conditional_collector_checkpoints';cache_root.mkdir(exist_ok=True)
    old_ledger=ledger/'conditional_family_sample_distances.jsonl'
    previous=[json.loads(line) for line in old_ledger.read_text().splitlines()] if old_ledger.exists() else []
    previous_progress_path=ROOT/'conditional_family_progress_20261023.json'
    previous_progress=json.loads(previous_progress_path.read_text()).get('queues',[]) if previous_progress_path.exists() else []
    for launch in launches:
        plan_name=launch.get('local_plan','conditional_'+launch['kind']+'_jobs_20261023.json.gz')
        jobs=json.loads(gzip.decompress((ROOT/plan_name).read_bytes()))
        byid={j['job_id']:j for j in jobs}
        code=r'''
import pathlib,json,hashlib,gzip,base64,os,time
VERIFY
l=LAUNCH;root=pathlib.Path(l['root']);plan=pathlib.Path(l['plan'])
if hashlib.sha256(plan.read_bytes()).hexdigest()!=l['plan_sha256']:raise ValueError('frozen plan changed')
cache_path=root/'collector_probe_digest_cache.json';cache=json.loads(cache_path.read_text()) if cache_path.exists() else {};last=time.monotonic();rows=[]
def checkpoint():
 temp=cache_path.with_name(cache_path.name+'.'+str(os.getpid())+'.tmp');temp.write_text(json.dumps(cache));temp.replace(cache_path)
for path in root.glob('*/result.json'):
 row=json.loads(path.read_text())
 for p in row['probes']:
  folder=path.parent/format(p['theta'],'.12g');verify_probe_files(p,folder,cache)
  if json.loads((folder/'receipt.json').read_text())!=p:raise ValueError('probe measurement changed')
  if time.monotonic()-last>10:checkpoint();last=time.monotonic()
 for p,digest in row['backend_sources'].items():
  if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()!=digest:raise ValueError('backend changed')
 rows.append(row)
checks=[json.loads(p.read_text()) for p in root.glob('*/source_check.json')]
phase=json.loads((root/'pipeline_phase.json').read_text()) if (root/'pipeline_phase.json').exists() else {}
status=json.loads((root/'status.json').read_text()) if (root/'status.json').exists() else []
checkpoint();print(base64.b64encode(gzip.compress(json.dumps(dict(results=rows,source_checks=checks,status=status,phase=phase)).encode())).decode())
'''.replace('VERIFY',inspect.getsource(verify_probe_files)).replace('LAUNCH',repr(launch))
        try:
            data,error=fetch_queue(launch,code,cache_root)
        except Exception as exc:
            # Retain already verified bindings for this queue while other hosts
            # continue collecting. No fresh result is inferred from a failure.
            output.extend(r for r in previous if r.get('refinement_job_id') in byid)
            old=next((r for r in previous_progress if r['launch']['root']==launch['root'] and r['launch']['host']==launch['host']),dict(launch=launch))
            progress.append(dict(old,collection_stale=True,collection_error=str(exc)))
            errors.append(dict(host=launch['host'],root=launch['root'],error=str(exc)))
            continue
        if error:errors.append(dict(host=launch['host'],root=launch['root'],error=error))
        queue_output=[]
        try:
            for result in data['results']:
                bound=bind(byid[result['job_id']],result)
                for row in bound:row['refinement_execution_host']=launch['host']
                queue_output.extend(bound)
        except Exception as exc:
            output.extend(r for r in previous if r.get('refinement_job_id') in byid)
            old=next((r for r in previous_progress if r['launch']['root']==launch['root'] and r['launch']['host']==launch['host']),dict(launch=launch))
            progress.append(dict(old,collection_stale=True,collection_error=str(exc)))
            errors.append(dict(host=launch['host'],root=launch['root'],error=str(exc),validation_failed=True))
            continue
        output.extend(queue_output)
        done={r['job_id'] for r in data['results']}
        failed={r['job_id'] for r in data['status'] if r['status']=='failed'}-done
        checks={r['job_id']:r for r in data['source_checks']}
        counts=collections.defaultdict(collections.Counter)
        for job in jobs:
            key=job['scene_id']+'/'+job['family_id'];counts[key]['planned']+=1
            if job['job_id'] in done:counts[key]['completed']+=1
            if job['job_id'] in failed:counts[key]['failed_attempt']+=1
            if job['job_id'] in checks:counts[key]['source_checked']+=1
        progress.append(dict(launch=launch,phase=data['phase'],completed=len(done),failed_attempts=len(failed),
            source_checks=len(checks),families=dict(counts),source_event_mismatches=sum(len(r['source_event_mismatches']) for r in checks.values()),
            unseeded_completed_scans=sum(r['source_seed'] is None for r in data['results']),collection_stale=bool(error),collection_error=error))
    atomic_text(ledger/'conditional_family_sample_distances.jsonl',''.join(json.dumps(r)+'\n' for r in output))
    result=dict(queues=progress,conditional_bound_samples=len({(r['scene_id'],r['sample_id']) for r in output}),
                conditional_intervals=len(output),formal_admissions=0,source_scan_summary=summary,collection_errors=errors)
    atomic_text(ROOT/'conditional_family_progress_20261023.json',json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ['queues','source_scan_summary']}),flush=True)
    if errors:raise RuntimeError('Some queues could not refresh; previous verified results retained; see collection_errors')


if __name__=='__main__':main()
