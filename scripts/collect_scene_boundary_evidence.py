import concurrent.futures,json,subprocess,hashlib,csv
from pathlib import Path
OUT=Path('review/all_scene_boundary_audit_20261018')
def main():
 jobs={}
 choices=['ab_boundary_multigravity_calibration_v1/summary.json','chain_friction_calibration_v3_fine/summary.json',
 'calibration_formal_52800_r006_p26/g03_earth.json','yaw_stability_dryrun_r006/summary.json',
 'g05_robust_refinement_dryrun_r006/combined_summary.json','five_gravity_calibration_result.json',
 'calibration_r009_event_chain/probe_outcomes_v12.json','finalprofile_critical_audit.json',
 'build_t03_v5_formal_480p.py','build_t07_formal_v2_balanced.py','build_t08_v4_formal_480p.py',
 'everyday_bifurcation_72k_T06_T10_v1/scripts/build_project.py',
 'everyday_bifurcation_72k_T16_T20_v1/scripts/build_project.py']
 for host in ['p25','p26']:
  rows=json.loads((OUT/(host+'_sources.json')).read_text())
  jobs[host]=[r['path'] for r in rows if any(r['path'].endswith(x) for x in choices)]
 inventory=list(csv.DictReader((OUT/'inventory.csv').open(encoding='utf-8-sig')))
 jobs['p25'] += ['/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/scripts/'+name for name in ['build_t06_t10_referencequality_v6_20260816.py','build_t11_r010_formal.py','build_t12_multparam_production_configs.py','build_t13_frozen_formal_v3.py']]
 for scene in ['T16','T17','T18','T19','T20']:
  r=next((r for r in inventory if r['scene_id']==scene and 'boundary_d1_minus' in r['sample_id']),next(r for r in inventory if r['scene_id']==scene))
  jobs['p25'].append(str(Path(r['states_path']).parent/'input.json').replace('\\','/'))
 def fetch(item):
  host,paths=item
  code='import pathlib,json,hashlib\nresult=[]\nfor name in '+repr(paths)+':\n try:\n  p=pathlib.Path(name);b=p.read_bytes();result.append(dict(path=name,sha256=hashlib.sha256(b).hexdigest(),text=b.decode()))\n except Exception as e:result.append(dict(path=name,error=str(e)))\nprint(json.dumps(result))'
  r=subprocess.run(['ssh',host,'python3 -'],input=code.encode(),capture_output=True,timeout=90)
  (OUT/(host+'_evidence.json')).write_bytes(r.stdout)
  print(host,r.returncode)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(fetch,jobs.items()))
if __name__=='__main__':main()
