"""Compare independent seed0 runs; never replace original publication truth."""
import inspect
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT
from scripts.probe_verification_cache import verify_probe_files


def main():
    marker=ROOT/'t13_seed0_repeat_launch_20261025.json'
    if not marker.exists():return
    launch=json.loads(marker.read_text())
    code=r'''
import pathlib,json,hashlib,os
VERIFY
r=pathlib.Path(RUN);old=r.parent.parent/'t13_remaining_seeded_scans_20261021/run';cache_path=r/'collector_digest_cache.json';cache=json.loads(cache_path.read_text()) if cache_path.exists() else {};records=[]
for result in r.glob('*/receipt.json'):
 a=json.loads(result.read_text())
 if a.get('status')!='supplemental_grid_completed' or a.get('supplemental_init_seed')!=0:raise ValueError('unexpected repeat seed contract')
 previous=old/result.parent.name/'receipt.json';b=json.loads(previous.read_text())
 for key in ['backend_sha256','seed_bootstrap_sha256','source_state_sha256','reference_sample_ids']:
  if a[key]!=b[key]:raise ValueError('repeat setup changed: '+key)
 points=[]
 for p in a['grid_observations']:
  folder=result.parent/format(p['theta'],'.12g');verify_probe_files(p,folder,cache)
  q=old/result.parent.name/folder.name/'receipt.json'
  if not q.exists():continue
  before=json.loads(q.read_text());verify_probe_files(before,q.parent,cache)
  if p['config_sha256']==before['config_sha256']:same_config=True
  else:
   # Only output paths differ across independent runs.
   def physics(path):
    c=json.loads(path.read_text());c.pop('render',None);c.pop('annotations',None);return c
   same_config=physics(folder/'config.json')==physics(q.parent/'config.json')
  points.append(dict(theta=p['theta'],physics_configuration_matches=same_config,before=before['events'],after=p['events'],same_events=before['events']==p['events'],same_state=p['state_sha256']==before['state_sha256']))
 records.append(dict(job_id=a['job_id'],points=points,repeat_intervals=a['local_intervals'],previous_intervals=b['local_intervals']))
temp=cache_path.with_name(cache_path.name+'.tmp');temp.write_text(json.dumps(cache));temp.replace(cache_path)
status=json.loads((r/'status.json').read_text()) if (r/'status.json').exists() else []
print(json.dumps(dict(records=records,failed_attempts=[x for x in status if x.get('status')=='failed'],resource_status=json.loads((r/'resource_status.json').read_text()) if (r/'resource_status.json').exists() else {})))
'''.replace('VERIFY',inspect.getsource(verify_probe_files)).replace('RUN',repr(launch['root']))
    data=json.loads(remote_text(launch['host'],code,timeout=300))
    points=[p for r in data['records'] for p in r['points']]
    data['summary']=dict(planned=launch['planned_intervals'],completed=len(data['records']),compared_points=len(points),changed_events=sum(not p['same_events'] for p in points),configuration_mismatches=sum(not p['physics_configuration_matches'] for p in points),diagnostic_only=True,original_labels_changed=0)
    (ROOT/'t13_seed0_repeatability_20261025.json').write_text(json.dumps(data,indent=2))
    print(json.dumps(data['summary']))


if __name__=='__main__':main()
