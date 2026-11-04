import json,gzip,hashlib
from pathlib import Path
from huggingface_hub import HfApi,hf_hub_download
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'remaining2241';api=HfApi();repo='phyeditingvideo/Phyediting';rev='3856c258368789c942dbc16d4983e756881ad986'
ids={x['canonical_video_id'] for x in map(json.loads,gzip.open(R/'remaining6767/REMAINING.jsonl.gz','rt'))};tasks=[x for x in map(json.loads,gzip.open(R/'TASKS.jsonl.gz','rt')) if x['canonical_video_id'] in ids];chosen={}
for x in tasks:
 if x['scene']=='T01' or (x['scene']=='T04' and not any(y['scene']=='T04' for y in chosen.values())):chosen[x['native_sample_id']]=x
records=[]
for native,t in chosen.items():
 parent=t['source_path'].split('/videos/')[0]
 for x in api.list_repo_tree(repo,path_in_repo=parent,repo_type='dataset',revision=rev,recursive=True):
  if x.__class__.__name__!='RepoFile' or not (x.path.endswith('.log') or Path(x.path).name in ['COMPLETED.json','FORMAL_COMPLETED.json']):continue
  p=Path(hf_hub_download(repo,x.path,repo_type='dataset',revision=rev));raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest();dest=O/'execution_records';dest.mkdir(exist_ok=True);(dest/(h+Path(x.path).suffix)).write_bytes(raw);records.append({'native_sample_id':native,'path':x.path,'sha256':h,'local_path':str(dest/(h+Path(x.path).suffix))})
  if x.path.endswith('.log'):print('LOG',native,Path(x.path).name,'\n'+'\n'.join(l for l in raw.decode(errors='replace').splitlines() if any(k in l.lower() for k in ['freeze','background','config','seed','json']))[:3000],flush=True)
  else:print('RECEIPT',native,raw.decode()[:1600],flush=True)
(O/'EXECUTION_RECORDS.json').write_text(json.dumps(records,indent=2))
for prefix in ['data/T04','releases']:
 try:print('PHY2TREE',prefix,[x.path for x in api.list_repo_tree('phy2/phydataset',path_in_repo=prefix,revision='0df3971705a89673a2913566ae888ab5fbc444be',repo_type='dataset')][:25])
 except Exception as e:print(type(e).__name__)
