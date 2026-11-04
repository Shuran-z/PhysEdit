from huggingface_hub import HfApi
import json,collections,concurrent.futures
from pathlib import Path
O=Path('/data_cached/wangzijun_p25/config_bindings_20261031/remaining2241');api=HfApi()
queries=[('aliensco2025/Phyediting','fc4b3cb011ead914b36d0db3aaa422924eba53a8','staging/t04_t05/formal_880_v1_480p_20260903T1310CST/T04'),('phyeditingvideo/Phyediting','3856c258368789c942dbc16d4983e756881ad986','staging/t04_t05/formal_880_v1_480p_20260903T1310CST/T04'),('phyeditingvideo/Phyediting','3856c258368789c942dbc16d4983e756881ad986','staging/t04_t05/formal_880_v1_480p_20260904_delta/T04')]
def get(q):
 repo,rev,prefix=q;rows=[]
 for x in api.list_repo_tree(repo,path_in_repo=prefix,repo_type='dataset',revision=rev,recursive=True):
  if x.__class__.__name__=='RepoFile':rows.append({'path':x.path,'size':x.size,'blob_id':x.blob_id,'lfs_sha256':x.lfs.sha256 if x.lfs else None})
 name=repo.split('/')[0]+'_'+('delta' if '_delta/' in prefix else 'initial');(O/(name+'_TREE.json')).write_text(json.dumps(rows,indent=2));s={'repo':repo,'revision':rev,'prefix':prefix,'files':len(rows),'extensions':dict(collections.Counter(''.join(Path(x['path']).suffixes) for x in rows)),'config_named_files':[x for x in rows if any(k in x['path'].lower() for k in ['/configs/','config.json','config_snapshot','backup','.zip','.tar'])]};print(json.dumps(s),flush=True);return s
with concurrent.futures.ThreadPoolExecutor(3) as pool:out=list(pool.map(get,queries))
(O/'UPLOAD_TREE_AUDIT.json').write_text(json.dumps(out,indent=2))
