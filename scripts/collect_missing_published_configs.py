"""Fetch exact revision config sidecars; no model inference and no media downloads."""
import concurrent.futures,hashlib,json,urllib.request,urllib.parse
from pathlib import Path
from huggingface_hub import get_token
OUT=Path('review/scene_family_completion_20261018')
def main():
 inventory=[json.loads(l) for l in Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()]
 rows=[r for r in inventory if r['engine']=='genesis' and r['event_id'] in ['T06','T09','T10','T12']]
 cache=OUT/'published_configs';cache.mkdir(exist_ok=True)
 token=get_token()
 def fetch(r):
  path=next((p for p in r.get('sidecar_paths',[]) if '/configs/' in p and 'cam01' in p),None)
  item={'sample_id':r['sample_id'],'scene_id':r['event_id'],'revision':r['revision'],'repo_id':r['repo_id'],'sidecar':path}
  if not path:return {**item,'error':'no config sidecar registered'}
  dest=cache/(r['sample_id']+'.json')
  url='https://huggingface.co/datasets/'+r['repo_id']+'/resolve/'+r['revision']+'/'+urllib.parse.quote(path,safe='/')
  try:
   if not dest.exists():
    request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token} if token else {})
    with urllib.request.urlopen(request,timeout=20) as response:b=response.read()
    json.loads(b);dest.write_bytes(b)
   b=dest.read_bytes();c=json.loads(b)
   return {**item,'sha256':hashlib.sha256(b).hexdigest(),'local_path':str(dest),'config':c}
  except Exception as e:return {**item,'error':str(e)}
 # Bounded first pass: two actual config examples per scene, before expanding.
 chosen=[]
 for scene in ['T06','T09','T10','T12']:chosen += [r for r in rows if r['event_id']==scene][:2]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(fetch,chosen))
 (OUT/'published_config_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps([{k:v for k,v in r.items() if k!='config'} for r in result]))
if __name__=='__main__':main()
