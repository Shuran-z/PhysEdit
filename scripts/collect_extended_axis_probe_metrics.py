import json,subprocess
from pathlib import Path
code=r'''
import pathlib,json,hashlib,math
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t06_t09_t10_original_axes_raster_20261018')
rows=json.loads((root/'status.json').read_text());result=[]
interior=root.parent/'t10_interior_raster_20261018/status.json'
if interior.exists():rows+=json.loads(interior.read_text())
extra=root.parent/'t06_t09_interior_raster_20261018/status.json'
if extra.exists():rows+=json.loads(extra.read_text())
for row in rows:
 p=pathlib.Path(row['output'])/'physics.json'
 if not p.exists():continue
 d=json.loads(p.read_text());frames=d.get('frames',[])
 if not frames:continue
 initial={o['name']:o for o in frames[0]['objects']};metrics={}
 for name in d['experiment']['tracked_objects']:
  a=initial[name];samples=[o for f in frames for o in f['objects'] if o['name']==name]
  def angle(o):return math.degrees(2*math.acos(min(1,abs(sum(v*w for v,w in zip(a['quaternion_xyzw'],o['quaternion_xyzw']))))))
  metrics[name]=dict(final_displacement_m=math.dist(a['position'],samples[-1]['position']),max_displacement_m=max(math.dist(a['position'],o['position']) for o in samples),final_rotation_deg=angle(samples[-1]),max_rotation_deg=max(map(angle,samples)))
 result.append(dict(sample_id=row['sample_id'],scene_id=row['scene_id'],parameter=row['parameter'],state_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),frame_count=len(frames),metrics=metrics,original_event_graph=d['experiment'].get('event_graph'),original_event_thresholds={k:v for k,v in d['experiment'].items() if 'threshold' in k},status='kinematic_probe_not_certified_boundary'))
print(json.dumps(result))
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True,timeout=60);p.check_returncode()
Path('review/scene_family_completion_20261018/t06_t09_t10_extended_kinematic_probe.json').write_bytes(p.stdout)
r=json.loads(p.stdout)
for x in r:print(x['sample_id'],x['frame_count'],x['original_event_thresholds'])
