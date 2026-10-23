"""Join new family scans and verified fixed-source intervals into the existing ledger."""
import base64
import collections
import gzip
import inspect
import json
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


def main():
    scan=json.loads((ROOT/'remaining_family_scans_launch_20261023.json').read_text())
    base=scan['root']+'/results/'
    summary=packed(scan['host'],base+'summary.json');coverage=packed(scan['host'],base+'coverage.json')
    bindings=packed(scan['host'],base+'bindings.json')
    (ROOT/'remaining_family_scan_summary_20261023.json').write_text(json.dumps(summary,indent=2))
    (ROOT/'remaining_family_scan_coverage_20261023.json').write_text(json.dumps(coverage,indent=2))
    ledger=ROOT/'original_value_distance_ledger'
    (ledger/'remaining_family_scan_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bindings))
    marker=ROOT/'conditional_family_launches_20261023.json'
    launches=json.loads(marker.read_text()) if marker.exists() else []
    output=[];progress=[]
    for launch in launches:
        jobs=json.loads(gzip.decompress((ROOT/('conditional_'+launch['kind']+'_jobs_20261023.json.gz')).read_bytes()))
        if launch.get('local_plan'):jobs=json.loads(gzip.decompress((ROOT/launch['local_plan']).read_bytes()))
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
        data=json.loads(gzip.decompress(base64.b64decode(remote_text(launch['host'],code,timeout=600))))
        for result in data['results']:
            bound=bind(byid[result['job_id']],result)
            for row in bound:row['refinement_execution_host']=launch['host']
            output.extend(bound)
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
            source_checks=len(checks),families=dict(counts),source_event_mismatches=sum(len(r['source_event_mismatches']) for r in checks.values())))
    (ledger/'conditional_family_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in output))
    result=dict(queues=progress,conditional_bound_samples=len({(r['scene_id'],r['sample_id']) for r in output}),
                conditional_intervals=len(output),formal_admissions=0,source_scan_summary=summary)
    (ROOT/'conditional_family_progress_20261023.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':main()
