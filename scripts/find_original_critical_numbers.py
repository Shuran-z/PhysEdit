"""Read original manifest/report numeric references; never run simulations.

Candidate numbers retain full JSON paths and original source hashes. A key name
alone does not prove correspondence to a current release; candidates are not
silently attached to all videos sharing a scene number.
"""
import argparse
import json
from pathlib import Path
import subprocess

ROOT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import pathlib,json,re,hashlib,os,time
starts=STARTS;begin=time.monotonic();records=[];read=0;errors=[];seen=set()
pattern=re.compile(r'theta_star|critical_value|critical_point|critical_parameter|critical_speed|critical_friction|boundary_value|solved_threshold|calibrated_star',re.I)
context_keys=['sample_id','scene_id','template_id','background_id','gravity_id','family','family_id','parameter_name','changed_variable','dataset_version','revision','status']
def walk(x,path=(),context=None):
 context=dict(context or {})
 if isinstance(x,dict):
  context.update({k:v for k,v in x.items() if k in context_keys and isinstance(v,(str,int,float))})
  for k,v in x.items():
   if pattern.search(k) and isinstance(v,(int,float)) and not isinstance(v,bool):yield dict(json_path=list(path+(k,)),value=v,context=context)
   if isinstance(v,(dict,list)):yield from walk(v,path+(k,),context)
 elif isinstance(x,list):
  for i,v in enumerate(x):
   if isinstance(v,(dict,list)):yield from walk(v,path+(i,),context)
for start in starts:
 base=pathlib.Path(start)
 if not base.exists():continue
 for folder,dirs,files in os.walk(base):
  depth=len(pathlib.Path(folder).relative_to(base).parts)
  dirs[:]=[d for d in dirs if depth<5 and d not in ['outputs','videos','metadata','hf_cache','.git','assets_generated','realistic_assets','retired','archive'] and not d.startswith(('T01F','T02V','T03V','T04F','T05F','PROD_'))]
  for name in files:
   if time.monotonic()-begin>100:break
   if not name.endswith('.json') or not re.search(r'manifest|matrix|report|summary|select|boundar|calibr|contract|search|triplet|build',name,re.I):continue
   p=pathlib.Path(folder)/name
   if str(p) in seen:continue
   seen.add(str(p))
   try:
    if p.stat().st_size>12*1024**2:continue
    raw=p.read_bytes();data=json.loads(raw);read+=1;hits=list(walk(data))
    if hits:records.append(dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),values=hits))
   except Exception as e:errors.append(dict(path=str(p),error_type=type(e).__name__))
  if time.monotonic()-begin>100:break
 if time.monotonic()-begin>100:break
print(json.dumps(dict(records=records,json_files_read=read,errors=errors,elapsed_seconds=time.monotonic()-begin,bounded_scan=True)))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--host',choices=['p25','p26','p29'],required=True);args=p.parse_args()
    if args.host=='p25':starts=['/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer']
    elif args.host=='p26':starts=['/data2/wangzijun_p25/liyuhan/phydataset/ase_asset_importer','/home/wangzijun_p25/t12_dualsim_v3_20261011/genesis_deploy/source']
    else:starts=['/21231_data1/liyuhan_t03_20261008/project','/21231_data1/liyuhan_t11_genesis_20261016']
    run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',args.host,'python3 -'],input=REMOTE.replace('STARTS',repr(starts)).encode(),capture_output=True,timeout=130)
    run.check_returncode();data=json.loads(run.stdout)
    output=ROOT/('original_critical_numbers_'+args.host+'_20261019.json');output.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(host=args.host,json_files_read=data['json_files_read'],sources=len(data['records']),numeric_values=sum(len(r['values']) for r in data['records']),errors=len(data['errors']),elapsed_seconds=data['elapsed_seconds'])))


if __name__=='__main__':main()
