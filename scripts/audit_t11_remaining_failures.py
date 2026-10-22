"""Compare available failed T11 endpoints against their exact published states."""
import collections
import inspect
import json
from scripts.boundary_ssh import remote_text
from scripts.diagnose_t11_original_host_replays import compare_states
from scripts.export_original_boundary_distances import ROOT
from scripts.register_five_scene_refinements import LAUNCHES


def summarize(rows):
    compared=[r for r in rows if r['audit_status']=='compared'];changed=[r for r in compared if r['original_label']!=r['replay_label']]
    fields=['dynamic_specs_match','physical_scene_overrides_match','timing_match','effective_properties_match','force_config_match']
    phases=['first_contact_frame','first_contact_physics_step','contact_trigger_frame','contact_trigger_physics_step','scheduled_clear_frame','applied_frames']
    return dict(requested_endpoints=len(rows),statuses=dict(collections.Counter(r['audit_status'] for r in rows)),
        compared_endpoints=len(compared),changed_event_labels=len(changed),compared_unique_jobs=len({r['job_id'] for r in compared}),
        mismatched_fields={k:sum(not r[k] for r in compared) for k in fields},
        changed_labels_with_all_physics_fields_matching=sum(all(r[k] for k in fields) for r in changed),
        changed_labels_with_precontact_error_below_1mm=sum(r['pre_first_contact_max_difference_m']<.001 for r in changed),
        changed_label_force_phase_differences={k:sum(any(s.get(k)!=t.get(k) for s,t in zip(r['original_force_phases'],r['replay_force_phases'])) for r in changed) for k in phases},
        scope='observed execution and trajectory differences; no unique solver-internal cause asserted')


def main():
    catalog=json.loads((ROOT/'five_scene_refinement_evidence_20261020.json').read_text())
    plans={j['job_id']:j for _,name in LAUNCHES if (ROOT/name).exists() for j in json.loads((ROOT/name).read_text())}
    sources={r['sample_id']:r for r in json.loads((ROOT/'t11_published_final_states.json').read_text())}
    successful={x['job_id'] for b in catalog for x in b['rows'] if x['status']=='refined_local_interval'}
    requests=collections.defaultdict(list);seen=set();runtimes={}
    for bundle in catalog:
        launch=bundle['launch']
        if launch.get('python'):runtimes[launch['host']]=launch['python']
        for row in bundle['rows']:
            if row.get('scene_id')!='T11' or row['status']!='failed' or row['job_id'] in successful:continue
            job=plans[row['job_id']]
            for endpoint in job['endpoints']:
                identity=(launch['host'],launch['root'],row['job_id'],endpoint['sample_id'])
                if identity in seen:continue
                seen.add(identity)
                requests[launch['host']].append(dict(root=launch['root'],job_id=job['job_id'],family_id=job['family_id'],target_event=job['target_event'],endpoint={k:endpoint[k] for k in ['sample_id','theta','label','state_sha256']},source=sources[endpoint['sample_id']],execution_error=row['error']))
    rows=[]
    for host,items in requests.items():
        code=r'''
import pathlib,json,gzip,hashlib,re
COMPARE
out=[]
for request in REQUESTS:
 e=request['endpoint'];folder=pathlib.Path(request['root'])/request['job_id']/format(e['theta'],'.12g');rp=folder/'receipt.json'
 result={k:request[k] for k in ['root','job_id','family_id','target_event','execution_error']};result.update(sample_id=e['sample_id'],theta=e['theta'])
 try:
  if not rp.exists():
   result['audit_status']='no_completed_probe_receipt';out.append(result);continue
  receipt=json.loads(rp.read_text());raw=pathlib.Path(receipt['state_path']).read_bytes();plain=gzip.decompress(raw)
  if hashlib.sha256(raw).hexdigest()!=receipt['stored_state_sha256'] or hashlib.sha256(plain).hexdigest()!=receipt['state_sha256']:raise ValueError('probe state changed')
  cp=folder/'config.json'
  if hashlib.sha256(cp.read_bytes()).hexdigest()!=receipt['config_sha256']:raise ValueError('probe config changed')
  sp=pathlib.Path(request['source']['source_state']);original=sp.read_bytes()
  if hashlib.sha256(original).hexdigest()!=e['state_sha256']:raise ValueError('published source state changed')
  source=json.loads(gzip.decompress(original) if sp.suffix=='.gz' else original);replay=json.loads(plain)
  comparison=compare_states(source,replay,request['target_event'])
  if comparison['original_label']!=e['label'] or comparison['replay_label']!=receipt['label']:raise ValueError('worker or original event label mismatch')
  text=re.sub(r'\x1b\[[0-9;]*m','',(folder/'run.log').read_text(errors='replace'));seed=re.search(r'physics random_seed applied = (None|\d+)',text)
  result.update(audit_status='compared',source_state_sha256=e['state_sha256'],replay_state_sha256=receipt['state_sha256'],declared_seed=json.loads(cp.read_text()).get('random_seed'),actual_runtime_seed=seed.group(1) if seed else None,**comparison)
 except Exception as exc:result.update(audit_status='unavailable_or_validation_error',error=str(exc))
 out.append(result)
print(json.dumps(out))
'''.replace('COMPARE',inspect.getsource(compare_states)).replace('REQUESTS',repr(items))
        rows.extend(dict(host=host,**r) for r in json.loads(remote_text(host,code,timeout=600,python=runtimes.get(host,'/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'))))
        (ROOT/('t11_failed_endpoint_audit_'+host+'_20261021.json')).write_text(json.dumps([r for r in rows if r['host']==host],indent=2))
    summary=summarize(rows)
    (ROOT/'t11_failed_endpoint_audit_20261021.json').write_text(json.dumps(rows,indent=2))
    (ROOT/'t11_failed_endpoint_audit_summary_20261021.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
