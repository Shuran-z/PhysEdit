"""CPU-only inventory of reusable old video latents and changed current media."""
from h3_new_prompt_common import *
import collections,random,sys
sys.path.insert(0,str(OLD))
import torch
def main():
 plan,data=rows();old={r['canonical_video_id']:r for r in map(json.loads,gzip.open(OLD/'train_manifest_runtime.jsonl.gz','rt'))};clocks=json.loads((OLD/'verified_clocks.json').read_text());stats=collections.Counter();reuse={};changed=[]
 for vid,row in data.items():
  fps,evidence=clock(row,old,clocks);stats['clock_'+evidence['kind']]+=1
  if vid not in old or old[vid]['sha256']!=row['sha256']:changed.append(dict(id=vid,sha256=row['sha256'],path=row['download']['path'],download=row['download']));stats['changed_or_new_video_bytes']+=1
  else:stats['same_video_bytes']+=1
  p=OLD/'h3_cache'/(vid+'.pt')
  if not p.exists():stats['old_cache_missing']+=1;continue
  d=torch.load(p,map_location='cpu',weights_only=True,mmap=True)
  rec=d['full_window_receipt']
  if d['source_sha256']!=row['sha256'] or abs(rec['fps']-fps)>1e-8:stats['old_cache_source_or_clock_changed']+=1;continue
  n=d['frames'];indices=[min(rec['frames']-1,round(i*fps/24)) for i in range(n)]
  assert d['fps']==24 and rec['model_sample_indices']==indices and tuple(d['first'].shape)==(1,24,1,18,32)
  assert tuple(d['latent'].shape)==(1,24,((n+16)//17)*5-3,18,32)
  reuse[vid]=dict(path=str(p),source_sha256=row['sha256'],physical_fps=fps,frames=n);stats['video_latents_reusable']+=1
 ids=sorted(data);random.Random(plan['seed']).shuffle(ids)
 save(R/'training_order.json',ids);save(R/'REUSE_INDEX.json',reuse);save(R/'CHANGED_MEDIA_REQUESTS.json',changed)
 result=dict(status='PASS',counts=dict(stats),training_videos=len(data),new_text_condition_cache_required=len(data),old_cache_files_untouched=True,model_loaded=False,cuda_initialized=False)
 save(R/'CACHE_INVENTORY.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
