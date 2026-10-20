"""Bind T15 completed scans/refinements to published parameters, without QA gates."""
import collections
import json
from pathlib import Path
import subprocess

from scripts.export_original_boundary_distances import distances

ROOT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import pathlib,json,hashlib,math,copy
base=pathlib.Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T15_v4_edge_transfer')
original=json.loads((base/'configs/v11_20260914/delivery/manifest.json').read_text(encoding='utf-8'))
roots=[pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t15_all_original_contexts_20261019'),pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t15_expanded_original_contexts_20261019')]
fields={'cfA':'initial_velocity_mps','cfB':'laptop_edge_margin_m','cfC':'phone_offset_y_scan_m'}
paths={'cfA':[('t15v4_driver_book','motion','initial_velocity',0)],'cfB':[('t15v4_driver_book','pose','position',0),('t15v4_closed_laptop','pose','position',0)],'cfC':[('t15v4_floor_phone','pose','position',1)]}
def at(x,path):
 for k in path:x=x[k]
 return x
def put(x,path,value):
 for k in path[:-1]:x=x[k]
 x[path[-1]]=value
def stable(x):
 if isinstance(x,float):return round(x,9)
 if isinstance(x,list):return [stable(v) for v in x]
 if isinstance(x,dict):return {k:stable(v) for k,v in x.items()}
 return x
scans={};receipts=[]
for root in roots:
 for row in json.loads((root/'status.json').read_text(encoding='utf-8')):
  if not row['transitions']:continue
  key=tuple(row['context']);scans[key]=row;receipts.append(row)
refined=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t15_refined_missing_intervals_20261019/status.json')
refined=json.loads(refined.read_text(encoding='utf-8')) if refined.exists() else []
result=[]
for ref in original:
 if not ref['slot'].startswith('cf'):continue
 family=ref['slot'].split('_')[0];key=(ref['background_id'],ref['gravity_id'],family);scan=scans.get(key)
 if not scan:continue
 cpath=pathlib.Path(ref['config']);raw=cpath.read_bytes();c=json.loads(raw);theta=c['sample_metadata'][fields[family]]
 probes=json.loads((pathlib.Path(scan['output'])/'manifest.json').read_text(encoding='utf-8'));lo,hi=probes[0],probes[-1]
 a,b=lo['theta'],hi['theta'];left=json.loads(pathlib.Path(lo['config']).read_text(encoding='utf-8'));right=json.loads(pathlib.Path(hi['config']).read_text(encoding='utf-8'))
 expected={o['name']:o for o in copy.deepcopy(left['dynamic_objects'])};l={o['name']:o for o in left['dynamic_objects']};h={o['name']:o for o in right['dynamic_objects']}
 for path in paths[family]:put(expected,path,at(l,path)+(theta-a)/(b-a)*(at(h,path)-at(l,path)))
 actual={o['name']:o for o in c['dynamic_objects']}
 matched=stable(expected)==stable(actual)
 profile={k:v for k,v in c['sample_metadata']['physics_profile'].items() if k!='config_sha256'}
 scanprofile={k:v for k,v in scan['profile'].items() if k!='config_sha256'}
 matched=matched and stable(profile)==stable(scanprofile)
 windows=[]
 for window in scan['transitions']:
  replacement=next((r for r in refined if tuple(r['context'])==key and r['source_bracket']==window['bracket'] and r['status']=='refined_local_interval'),None)
  windows.append(dict(bracket=replacement['bracket'] if replacement else window['bracket'],labels=window['labels'],kind='supplemental_refined_interval' if replacement else 'supplemental_scan_interval',refinement_job_id=replacement['job_id'] if replacement else None))
 result.append(dict(scene_id='T15',engine='genesis',sample_id=ref['sample_id'],family_id=family,background=ref['background_id'],gravity=ref['gravity_id'],theta=theta,
  parameter_name=fields[family],parameter_unit='m/s' if family=='cfA' else 'm',source_config_path=str(cpath),source_config_sha256=hashlib.sha256(raw).hexdigest(),physical_mapping_matches=matched,
  intervals=windows,source_scan_output=scan['output'],original_reference_kind='supplemental_solver_interval',extra_validation_separate=True))
print(json.dumps(dict(rows=result,scan_receipts=receipts,refinements=refined)))
'''


def main():
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=REMOTE.encode(),capture_output=True,timeout=90);p.check_returncode();proof=json.loads(p.stdout)
    (ROOT/'t15_all_context_distance_evidence.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    source=json.loads(Path('review/t15_boundary_pilot_20261014/reference_audit.json').read_text(encoding='utf-8'))
    original={r['sample_id']:r for r in source['rows']};inventory={r['sample_id']:r for r in map(json.loads,Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()) if r['engine']=='genesis' and r['event_id']=='T15'}
    result=[];unmatched=[]
    for r in proof['rows']:
        original_ref=original[r['sample_id']]
        if r['source_config_sha256']!=original_ref['config_sha256'] or not r['physical_mapping_matches']:
            unmatched.append(dict(sample_id=r['sample_id'],reason='configuration_or_fixed_physics_mismatch'));continue
        published=inventory[r['sample_id']]
        for window in r['intervals']:
            result.append({**r,'intervals':None,'original_boundary_interval':window['bracket'],'interval_kind':window['kind'],'refinement_job_id':window['refinement_job_id'],
                **distances(r['theta'],bracket=window['bracket']),'reference_state_sha256':original_ref['state_sha256'],'repo_id':published['repo_id'],'revision':published['revision'],'release':published['release'],'videos':published['videos'],
                'mapping_status':'matched','source_file':str((ROOT/'t15_all_context_distance_evidence.json').resolve())})
    target=ROOT/'original_value_distance_ledger';target.mkdir(exist_ok=True)
    (target/'t15_supplemental_sample_distances.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in result),encoding='utf-8')
    summary=dict(sample_interval_records=len(result),unique_published_samples=len({r['sample_id'] for r in result}),contexts=len({(r['background'],r['gravity'],r['family_id']) for r in result}),mapping_failures=unmatched,refined_records=sum(r['interval_kind']=='supplemental_refined_interval' for r in result))
    (target/'t15_supplemental_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
