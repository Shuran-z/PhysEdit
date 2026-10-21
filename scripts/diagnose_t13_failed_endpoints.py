"""Retain numeric failure evidence without relabeling published T13 videos."""
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    launch=json.loads((ROOT/'t13_remaining_repetitions_launch_20261020.json').read_text())
    code=r'''
import pathlib,json,math,hashlib,collections
base=pathlib.Path(DIRECTORY);jobs={j['job_id']:j for j in json.loads((base/'plan.json').read_text())};out=[]
for directory in ROOTS:
 root=pathlib.Path(directory);status=root/'status.json'
 for result in json.loads(status.read_text()) if status.exists() else []:
  if result['status']!='failed':continue
  job=jobs[result['job_id']]
  for endpoint,theta in zip(job['endpoints'],job['bracket']):
   folder=root/job['job_id']/format(theta,'.12g');sp=folder/'physics.json';cp=folder/'config.json'
   if not sp.exists():continue
   raw=sp.read_bytes();state=json.loads(raw);config=json.loads(cp.read_text())
   if len(state['frames'])!=168:raise ValueError('incomplete failed-point state')
   names=['t13_driver_book','t13_falling_book','t13_drink_box']
   tracks={name:[next(o['position'] for o in f['objects'] if o['name']==name) for f in state['frames']] for name in names}
   original={name:[o['position'] for o in endpoint['tracks'][name]] for name in names}
   errors=[max(math.dist(original[n][i],tracks[n][i]) for n in names) for i in range(168)]
   def measurements(t):
    p=t['t13_drink_box'];return dict(max_displacement_m=max(math.dist(p[18],v) for v in p[18:]),max_vertical_drop_m=p[18][2]-min(v[2] for v in p[18:]))
   a,b=measurements(original),measurements(tracks)
   def label(v):return int(v['max_vertical_drop_m']>=.05) if job['target_event']=='drink_drop_ge_5cm' else int(v['max_displacement_m']>=.01)
   if label(a)!=endpoint['label']:raise ValueError('original event differs from frozen rule')
   out.append(dict(job_id=job['job_id'],sample_id=endpoint['sample_id'],root=directory,family=job['family'],theta=theta,target_event=job['target_event'],
    source_state_sha256=endpoint['state_sha256'],replay_state_sha256=hashlib.sha256(raw).hexdigest(),replay_config_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),
    dynamic_objects_identical=config['dynamic_objects']==endpoint['config']['dynamic_objects'],original=a,replay=b,
    expected_label=endpoint['label'],actual_label=label(b),label_matches=label(b)==endpoint['label'],
    pre_intervention_max_position_error_m=max(errors[:18]),max_position_difference_m=max(errors),first_difference_over_1mm_frame=next((i for i,v in enumerate(errors) if v>.001),None)))
print(json.dumps(out))
'''.replace('DIRECTORY',repr(launch['root'])).replace('ROOTS',repr(launch['repeat_roots']))
    result=subprocess.run(['ssh','-o','BatchMode=yes',launch['host'],'python3 -'],input=code.encode(),capture_output=True,timeout=240)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    rows=json.loads(result.stdout)
    (ROOT/'t13_failed_endpoint_diagnostics_20261020.json').write_text(json.dumps(rows,indent=2))
    summary=dict(examined_endpoint_states=len(rows),outcome_mismatches=sum(not r['label_matches'] for r in rows),
        dynamic_object_config_changes=sum(not r['dynamic_objects_identical'] for r in rows),
        pre_intervention_error_over_5mm=sum(r['pre_intervention_max_position_error_m']>.005 for r in rows),
        original_labels_unchanged=True,scope='Locates observed replay divergence; no unique solver-internal cause inferred.')
    (ROOT/'t13_failed_endpoint_diagnostic_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
