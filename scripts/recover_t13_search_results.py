"""Recover original T13 rendered search configs and states via actual run receipts."""
import json
from pathlib import Path
import subprocess

ROOT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import pathlib,json,hashlib,math
result=[]
for row in ROWS:
 try:
  cp=pathlib.Path(row['normalized_config']);sp=pathlib.Path(row['annotation']);c=json.loads(cp.read_text());d=json.loads(sp.read_text())
  metrics={}
  for name in ['t13_falling_book','t13_drink_box','t13_driver_book']:
   positions=[next(o['position'] for o in f['objects'] if o['name']==name) for f in d['frames']]
   peak=max(math.dist(positions[18],p) for p in positions[18:]);drop=positions[18][2]-min(p[2] for p in positions[18:])
   metrics[name]=dict(max_displacement_m=peak,max_drop_m=drop,motion_ge_1cm=int(peak>=.01),drop_ge_5cm=int(drop>=.05))
  result.append(dict(source_round=row['source_round'],input_config=row['input_config'],config_path=str(cp),state_path=str(sp),config_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),state_sha256=hashlib.sha256(sp.read_bytes()).hexdigest(),config=c,
    scene_overrides=d['scene_overrides'],runtime_objects=[o['spec'] for o in d['dynamic_objects']],metrics=metrics,
    frames_sha256=hashlib.sha256(json.dumps(d['frames'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),frame_count=len(d['frames'])))
 except Exception as e:result.append(dict(**row,error=type(e).__name__))
print(json.dumps(result))
'''

def main():
    reports=json.loads((ROOT/'t13_search_round_evidence_20261019.json').read_text(encoding='utf-8'));runs=[]
    for r in reports:
        if not r['path'].endswith('/batch_summary.json'):continue
        for row in json.loads(r['text']).get('runs',[]):
            if row.get('normalized_config') and row.get('annotation'):runs.append(dict(**row,source_round=r['path']))
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=REMOTE.replace('ROWS',repr(runs)).encode(),capture_output=True,timeout=90)
    p.check_returncode();rows=json.loads(p.stdout)
    (ROOT/'t13_original_measured_search_results_20261019.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(dict(search_runs=len(rows),recovered=sum('metrics' in r for r in rows),failed=sum('error' in r for r in rows))))


if __name__=='__main__':main()
