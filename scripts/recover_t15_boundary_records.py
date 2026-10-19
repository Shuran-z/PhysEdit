"""Read-only recovery of known T15 search records from p25; never runs simulation."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = '/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/'
FILES = [
 'CRITICAL_SEARCH.md',
 'configs/t15_production_v1/search/t15_home_earth_duration_boundary_v1.json',
 'configs/t15_production_v1/frozen/t15_home_earth_boundary_stay_v1.json',
 'configs/t15_production_v1/frozen/t15_home_earth_boundary_fallen_v1.json',
 'outputs/t15_s02_home_earth_force_duration/manifest.json',
 'outputs/t15_s02_home_earth_force_duration/run.log',
 'outputs/t15_s00_home_earth_overhang_1to1/search_plan.json',
 'outputs/t15_s01_home_earth_force_search/search_plan.json',
 'everyday_bifurcation_T15_v4_edge_transfer/PROJECT_MEMORY.md',
 'everyday_bifurcation_T15_v4_edge_transfer/T15_V11_REWORK.md',
 'scripts/build_t15_v4.py', 'scripts/build_t15_v11.py',
]

def main():
    out=Path('review/t15_server_boundary_20261018');out.mkdir(exist_ok=False)
    receipts=[]
    for i,name in enumerate(FILES):
        r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','p25','cat',ROOT+name],capture_output=True,timeout=60)
        item={'host':'p25','remote_path':ROOT+name,'returncode':r.returncode}
        if r.returncode==0:
            dest=out/(str(i).zfill(2)+'_'+Path(name).name);dest.write_bytes(r.stdout)
            item.update(local_path=str(dest),sha256=hashlib.sha256(r.stdout).hexdigest())
        else:item['error']=r.stderr.decode(errors='replace')
        receipts.append(item)
    (out/'receipt.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'recovered':sum(x['returncode']==0 for x in receipts),'requested':len(receipts)}))

if __name__=='__main__':main()
