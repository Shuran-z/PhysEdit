"""Read completed original-family states against unchanged target predicates."""
import hashlib
import json
from pathlib import Path

from scripts.boundary_ssh import remote_text

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_continue_20261031'
REMOTE=r'''
import copy,gzip,hashlib,importlib.util,json,math
from pathlib import Path
roots=[('T04_C01','core100_continue_original_20261031/T04_C01'),
 ('T05_C01','core100_continue_families_20261031/T05_C01'),
 ('T10_C01','core100_continue_original_20261031/T10_C01'),
 ('T10_C02','core100_continue_original_20261031/T10_C02'),
 ('T11_C01','core100_continue_families_20261031/T11_C01__G_global_original'),
 ('T11_C02','core100_continue_families_20261031/T11_C02__G_global_original')]
output=[]
for cid,suffix in roots:
 root=Path('/data2/liyuhan')/suffix;job=json.loads((root/'jobs.json').read_text())[0]
 window=WINDOWS[cid]
 assert job['reference_video_sha256']==window['reference_video_sha256']
 assert job['sample_id']==window['sample_id']
 original_job=copy.deepcopy(job);job.update(end_frame_index=window['end_frame_index'],horizon_s=window['horizon_s'])
 spec=importlib.util.spec_from_file_location('readback_worker',root/'worker.py')
 worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
 deployment=json.loads((root/'deployment.json').read_text())
 for filename,digest in deployment['sources'].items():assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==digest
 item=dict(clip_id=cid,sample_id=job['sample_id'],reference_video_sha256=job['reference_video_sha256'],
  family=job['family'],source_theta=job['theta'],horizon_s=job['horizon_s'],end_frame_index=job['end_frame_index'],
  original_source_config_sha256=job['config_sha256'],probes=[],
  not_applicable_claimed=False,original_inputs_modified=False)
 for p in sorted((root/cid/'profile_0').glob('*/receipt.json')):
  if p.parent.name=='source_repeat':continue
  receipt=json.loads(p.read_text());state_path=Path(receipt['state_path'])
  raw=gzip.decompress(state_path.read_bytes());assert hashlib.sha256(raw).hexdigest()==receipt['state_sha256']
  cp=state_path.parent/'config.json';config_raw=cp.read_bytes();assert hashlib.sha256(config_raw).hexdigest()==receipt['config_sha256']
  c=json.loads(config_raw);state=json.loads(raw)
  assert len(state['frames'])==210
  assert c.get('seed')==job['base_config'].get('seed') and c.get('random_seed')==job['base_config'].get('random_seed')
  assert c['scene_overrides']['dt']==job['base_config']['scene_overrides']['dt']
  assert c['scene_overrides']['substeps']==job['base_config']['scene_overrides']['substeps']
  assert c['render']['physics_steps_per_render_frame']==job['base_config']['render']['physics_steps_per_render_frame']
  labels,peak=worker.observe(state,job)
  row=dict(theta=receipt['theta'],state_sha256=receipt['state_sha256'],config_sha256=receipt['config_sha256'],
   receipt=str(p),labels=labels,hashes_verified=True,original_solver_clock_seed_fields_preserved=True,
   native_peak_m=peak,intervention_valid=True)
  frames=state['frames'][5:job['end_frame_index']+1]
  if cid.startswith('T04'):
   track=[next(o for o in f['objects']if o['name']=='t04v3_chain_mug')for f in state['frames'][4:155]]
   row['mug_maximum_displacement_m']=max(math.dist(track[0]['position'],o['position'])for o in track)
   row['can2_mug_contact_observed']=any({a['entity_a'],a['entity_b']}=={'t04v3_chain_can_2','t04v3_chain_mug'}for f in frames for a in f.get('contacts',[]))
   v=next(o for o in c['dynamic_objects']if o['name']=='t04v3_removable_support_bar')['motion']['initial_velocity'][1]
   assert abs(v-receipt['theta'])<1e-9
   row['configured_support_speed_mps']=v
  elif cid.startswith('T05'):
   actual={name:state['physics_debug']['effective_entity_properties'][name]['effective_geom_friction_coefficients']for name in ['t05v2_moving_phone','t05v2_pbr_wood_sorting_tray']}
   row['friction_execution_readback']=actual
   row['intervention_valid']=all(v and all(abs(x-receipt['theta'])<1e-6 for x in v)for v in actual.values())
   row['maximum_phone_center_x_m']=max(o['position'][0]for f in frames for o in f['objects']if o['name']=='t05v2_moving_phone')
   row['full_passage_center_threshold_x_m']=job['full_pass_x_m']
  elif cid.startswith('T10'):
   actual=c['experiment']['t10_design']['support_x_m']
   assert next(o for o in c['dynamic_objects']if o['name']=='t10_support_pen')['pose']['position'][0]==actual
   baseline=next(o['position']for o in state['frames'][4]['objects']if o['name']=='t10_support_pen')
   row['effective_support_x_m']=actual
   row['maximum_pen_displacement_m']=max(math.dist(baseline,o['position'])for f in frames for o in f['objects']if o['name']=='t10_support_pen')
   row['event_threshold_m']=c['experiment']['support_ejection_threshold_m'];assert row['event_threshold_m']==.04
  else:
   row['joint_parameter_vector']=c['experiment']['parameter']['parameter_value']
   row['final_center_z_m']={o['name']:o['position'][2]for o in state['frames'][154]['objects']if o['name'].startswith('t11_')and not o.get('fixed',False)}
  item['probes'].append(row)
 valid=[p for p in item['probes']if p['intervention_valid']]
 item['verified_distinct_probes']=len(valid)
 item['labels_by_event']={event:sorted(set(p['labels'][event]for p in valid))for event in window['reference_events']}
 item['opposite_endpoints_observed']=any(len(v)>1 for v in item['labels_by_event'].values())
 output.append(item)
print(json.dumps(dict(schema='core100-pending-six-native-readback-v1',cases=output)))
'''


def main():
    from physedit.core100_bindings import load
    windows={r['clip_id']:{k:r[k]for k in ['sample_id','reference_video_sha256','reference_events','end_frame_index','horizon_s']}
             for r in load()['cases']}
    report=json.loads(remote_text('p25',REMOTE.replace('WINDOWS',repr(windows)),timeout=300,attempts=1))
    raw=json.dumps(report,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('pending_six_native_readback_'+digest[:12]+'.json')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    summary=dict(evidence=path.relative_to(ROOT).as_posix(),sha256=digest,cases=[
        {k:r[k]for k in ['clip_id','family','verified_distinct_probes','labels_by_event','opposite_endpoints_observed']}
        for r in report['cases']])
    (WORK/'pending_six_native_readback_latest.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary))


def apply_readback(cases,report,evidence_file):
    """Add verified finite-scan facts; never manufacture an interval/exclusion."""
    for item in report['cases']:
        row=cases[item['clip_id']]
        for key in ['sample_id','reference_video_sha256','end_frame_index','horizon_s']:
            if row[key]!=item[key]:raise ValueError('pending_readback_reference_or_window_changed')
        if set(row['reference_events'])!=set(item['labels_by_event']):
            raise ValueError('pending_readback_event_definition_changed')
        row['completed_original_scan_readback']={k:item[k]for k in
            ['family','verified_distinct_probes','labels_by_event','opposite_endpoints_observed']}
        row['completed_original_scan_readback'].update(evidence=evidence_file,
            no_applicability_exclusion_granted=True)


if __name__=='__main__':main()
