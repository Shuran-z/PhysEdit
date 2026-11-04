"""Verify repeated original-solver endpoints, keeping disagreements explicit."""
import hashlib
import json
from pathlib import Path

from scripts.boundary_ssh import remote_text

WORK=Path(__file__).resolve().parents[1]/'review/core100_continue_20261031'
REMOTE=r'''
import gzip,hashlib,importlib.util,json
from pathlib import Path
parent=Path('/home/wangzijun_p25/core100_endpoint_rechecks_20261101')
donor=Path('/data2/liyuhan/core100_continue_families_20261031/T11_C02__case_friction_original')
job=json.loads((donor/'jobs.json').read_text())[0]
result=json.loads((donor/'T11_C02/result.json').read_text())
source=job['base_config'];spec=importlib.util.spec_from_file_location('endpoint_worker',donor/'worker.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
endpoints=sorted(set(v for r in result['intervals']for v in r['bracket']))
coarse_roots=[parent/'T11_C02_r04_coarse',parent/'T11_C02_r05_coarse']
brackets=list(result['intervals'])
if all((p/'jobs.json').exists()for p in coarse_roots):
 low=json.loads((donor/'T11_C02/profile_0/1.2/receipt.json').read_text())
 high=json.loads((donor/'T11_C02/profile_0/2/receipt.json').read_text())
 for event in low['labels']:
  if low['labels'][event]!=high['labels'][event]:
   brackets.append(dict(event=event,bracket=[1.2,2.],labels=[low['labels'][event],high['labels'][event]],
    required_endpoint_execution_indices=[[0,4],[0,5]],matched_device_required=True,
    scope='Wider original-component bracket; two executions per endpoint, not a unique threshold.'))
 endpoints=sorted(set(endpoints+[1.2,2.]))
report=dict(schema='core100-endpoint-repeatability-v1',clip_id=job['clip_id'],
 sample_id=job['sample_id'],reference_video_sha256=job['reference_video_sha256'],
 source_config_sha256=job['config_sha256'],family=job['family'],
 horizon_s=job['horizon_s'],end_frame_index=job['end_frame_index'],
 source_vector=job['joint_source_nominal_parameters'],
 source_seed_fields={k:source.get(k)for k in ['seed','random_seed']},
 fixed_numeric_seed_claimed=False,
 brackets=brackets,probes=[],runs=[],
 original_inputs_modified=False,formal_admission=False)
for index,root in enumerate([donor,parent/'T11_C02_r01',parent/'T11_C02_r02',parent/'T11_C02_r03_same_device']+coarse_roots):
 if not(root/'jobs.json').exists():continue
 repeat_job=json.loads((root/'jobs.json').read_text())[0]
 for key in ['base_config','joint_source_nominal_parameters','config_sha256','state_sha256','end_frame_index','horizon_s','physical_frame_period_s']:
  assert repeat_job[key]==job[key],key
 deployment=json.loads((root/'deployment.json').read_text())
 for name,digest in deployment['sources'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
 status=root/'T11_C02/status.json'
 report['runs'].append(dict(root=str(root),repeat_index=index,status=json.loads(status.read_text())if status.exists()else None))
 for value in endpoints:
  receipt=root/'T11_C02/profile_0'/format(value,'.12g')/'receipt.json'
  if not receipt.exists():continue
  row=json.loads(receipt.read_text());raw=gzip.decompress(Path(row['state_path']).read_bytes())
  config=receipt.parent/'config.json';c=json.loads(config.read_text());state=json.loads(raw)
  assert hashlib.sha256(raw).hexdigest()==row['state_sha256']
  assert hashlib.sha256(config.read_bytes()).hexdigest()==row['config_sha256']
  expected=worker.intervention(job,value)
  for key in ['dynamic_objects','runtime_forces','experiment','seed','random_seed']:
   assert c.get(key)==expected.get(key),key
  for key,v in source['scene_overrides'].items():
   if key not in ['record_contacts','raytracing']:assert c['scene_overrides'].get(key)==v,key
  assert c['render']['physics_steps_per_render_frame']==source['render']['physics_steps_per_render_frame']
  assert abs(c['scene_overrides']['dt']*c['render']['physics_steps_per_render_frame']-job['physical_frame_period_s'])<1e-12
  actual=state['physics_debug']['effective_entity_properties']['t11_eyeglasses_case']['effective_geom_friction_coefficients']
  assert actual and all(abs(v-value)<1e-6 for v in actual)
  labels,peak=worker.observe(state,job);assert labels==row['labels']
  device_file=receipt.parent/'actual_gpu_selection.json';backend_file=receipt.parent/'runtime_backend.json'
  device=json.loads(device_file.read_text());backend=json.loads(backend_file.read_text())
  assert backend['backend']=='gpu32' and backend['actual_init_seed']==source.get('random_seed',source.get('seed'))
  report['probes'].append(dict(theta=value,repeat_index=index,labels=labels,native_peak_m=peak,
   gpu_identity=device,runtime_backend=backend,
   state_sha256=row['state_sha256'],config_sha256=row['config_sha256'],receipt=str(receipt),
   hashes_verified=True,original_solver_seed_clock_verified=True,forces_unchanged=True,
   friction_execution_readback=actual))
print(json.dumps(report))
'''


def summarize(report):
    result=[]
    for bracket in report['brackets']:
        event=bracket['event'];ends=[]
        for side,(value,expected)in enumerate(zip(bracket['bracket'],bracket['labels'])):
            rows=[r for r in report['probes']if abs(r['theta']-value)<1e-10]
            repeats={r['repeat_index']for r in rows}
            if len(repeats)!=len(rows):raise ValueError('duplicate_endpoint_execution')
            if any(not all(r.get(k)for k in ['hashes_verified','original_solver_seed_clock_verified','forces_unchanged'])for r in rows):
                raise ValueError('unverified_endpoint_execution')
            labels=[r['labels'][event]for r in sorted(rows,key=lambda r:r['repeat_index'])]
            agrees=all(label==expected for label in labels)
            required=bracket.get('required_endpoint_execution_indices',[[0,1,2],[0,1,2]])[side]
            complete=set(required).issubset(repeats)
            ends.append(dict(theta=value,expected_label=expected,labels=labels,
                independent_executions=len(rows),complete=complete,agrees_with_original=agrees))
            if rows and 'gpu_identity'in rows[0]:
                original=next(r for r in rows if r['repeat_index']==0)
                uuid=original['gpu_identity']['selected_gpu_uuid']
                same=[r['labels'][event]for r in rows if r['gpu_identity']['selected_gpu_uuid']==uuid]
                if bracket.get('matched_device_required') and any(r['repeat_index']in required and
                    r['gpu_identity']['selected_gpu_uuid']!=uuid for r in rows):
                    raise ValueError('endpoint_recheck_requested_device_mismatch')
                ends[-1].update(original_gpu_uuid=uuid,same_device_labels=same,
                    same_device_repeat_observed=len(same)>1,
                    same_device_agrees_with_original=all(label==expected for label in same))
        state=('discordant'if any(not e['agrees_with_original']for e in ends)else
               'reproduced'if all(e['complete']for e in ends)else'pending')
        result.append(dict(event=event,bracket=bracket['bracket'],endpoints=ends,status=state,
            scope=bracket.get('scope','Refined local single-run bracket with repeated endpoints.'),
            numerical_endpoint_repeatability_confirmed=state=='reproduced',
            unique_or_global_threshold_certified=False,physics_quality_approval_granted=False))
    return result


def apply_report(cases, report, evidence_file):
    """Attach repeat checks without changing source truth or deleting records."""
    row=cases[report['clip_id']]
    for key in ['sample_id','reference_video_sha256','horizon_s','end_frame_index']:
        if row[key]!=report[key]:raise ValueError('endpoint_recheck_source_or_window_mismatch')
    if row['theta']!=report['source_vector']:
        raise ValueError('endpoint_recheck_source_vector_mismatch')
    original=row['original_reference_review']['original_record']['original_config_sha256']
    if original!=report['source_config_sha256']:
        raise ValueError('endpoint_recheck_original_config_mismatch')
    axis=row['conditional_axes'][report['family']]
    checks=summarize(report)
    from physedit.core100_bindings import interval_distance
    for check in checks:
        if check['status']!='reproduced':continue
        if any(r['event']==check['event']and r['bracket']==check['bracket']for r in axis['boundary_records']):continue
        original=next(b for b in report['brackets']if b['event']==check['event']and b['bracket']==check['bracket'])
        # New records are admitted only from complete, checked endpoint runs.
        # Their wider uncertainty is retained; the narrow discordant records
        # are never silently overwritten.
        endpoints=[next(p for p in report['probes']if p['repeat_index']==0 and abs(p['theta']-value)<1e-10)
                   for value in check['bracket']]
        axis['boundary_records'].append(dict(event=check['event'],bracket=check['bracket'],
            endpoint_labels=original['labels'],exact_theta_star=None,
            interval_kind='conditional_local_search',endpoints=endpoints,
            distance=interval_distance(axis['theta'],check['bracket'],axis['normalization_span'])))
    for record in axis['boundary_records']:
        matches=[r for r in checks if r['event']==record['event']and r['bracket']==record['bracket']]
        if len(matches)!=1:raise ValueError('endpoint_recheck_bracket_changed')
        record['endpoint_repeatability']=dict(matches[0],evidence=evidence_file)
    axis['endpoint_repeatability_evidence']=evidence_file
    axis['formal_admission']=False


def collect():
    report=json.loads(remote_text('p25',REMOTE,timeout=120))
    report['interval_repeatability']=summarize(report)
    raw=json.dumps(report,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('t11_c02_endpoint_repeatability_'+digest[:12]+'.json')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    pointer=dict(file=path.relative_to(WORK.parents[1]).as_posix(),sha256=digest,
        completed_new_endpoint_executions=sum(r['repeat_index']>0 for r in report['probes']),
        requested_new_endpoint_executions=11 if len(report['runs'])==6 else 9 if len(report['runs'])>=4 else 8,
        intervals=report['interval_repeatability'])
    temporary=WORK/'endpoint_repeatability_latest.tmp'
    temporary.write_text(json.dumps(pointer,indent=2),encoding='utf8')
    temporary.replace(WORK/'endpoint_repeatability_latest.json')
    return pointer


if __name__=='__main__':print(json.dumps(collect()))
