import json,subprocess
from pathlib import Path
OUT=Path('review/original_search_tasks_20261018')
REMOTE=r'''
import pathlib,json,hashlib
root=pathlib.Path('/data2/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T02_v2_causal_gate')
paths=[root/'manifests/t02_full_causal_chain_parameter_design_v2.json']
paths+=list((root/'reports/t02_full_chain_calibration_r006_p26').glob('**/*.json'))
paths+=list((root/'reports/g04_global_b_repair_r010_current_runtime').glob('*.json'))
result=[]
for p in paths:
 try:
  b=p.read_bytes();result.append(dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),text=b.decode()))
 except Exception as e:result.append(dict(path=str(p),error=str(e)))
print(json.dumps(result))
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','p26','python3 -'],input=REMOTE.encode(),capture_output=True,timeout=120)
p.check_returncode();(OUT/'t02_family_sources.json').write_bytes(p.stdout)
rows=json.loads(p.stdout)
print(json.dumps({'records':len(rows),'readable':sum('text' in r for r in rows)}))
