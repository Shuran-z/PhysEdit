"""Fetch hash-bound current media from short-lived signed read URLs; no HF account token."""
from h3_new_prompt_common import *
import concurrent.futures,threading,requests,traceback
def main():
 payload=json.loads((R/'media_read_urls.private.json').read_text());items=payload['items'];lock=threading.Lock();stats={'completed':0,'failed':0,'total':len(items)};errors=[]
 def one(x):
  p=R/'current_media'/(x['id']+'.mp4')
  try:
   if not (p.exists() and sha(p)==x['sha256']):
    temp=p.with_suffix('.download')
    for attempt in range(3):
     try:
      with requests.get(x['url'],headers=x.get('headers',{}),stream=True,timeout=(30,120)) as response:
       response.raise_for_status()
       with temp.open('wb') as f:
        for b in response.iter_content(1<<20):f.write(b)
      break
     except requests.RequestException as exc:
      status=getattr(getattr(exc,'response',None),'status_code',None)
      if attempt==2 or status in [401,403,404]:raise
      time.sleep(2**(attempt+1))
    assert sha(temp)==x['sha256'];temp.replace(p)
   with lock:stats['completed']+=1
  except Exception as exc:
   with lock:stats['failed']+=1;errors.append(dict(id=x['id'],type=type(exc).__name__,status=getattr(getattr(exc,'response',None),'status_code',None)))
  with lock:save(R/'MEDIA_PREFETCH_STATUS.json',dict(**stats,time=time.time(),errors=errors[-20:],signed_urls_not_logged=True))
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:list(pool.map(one,items))
 save(R/'MEDIA_PREFETCH_COMPLETE.json',dict(**stats,time=time.time(),errors=errors));assert not errors
if __name__=='__main__':main()
