"""Recover source MP4 hashes at the original pinned revisions for coverage joins."""
import os,json,logging,time,collections
from pathlib import Path
logging.disable(logging.CRITICAL);os.environ['NO_PROXY']='.amazonaws.com';os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import HfApi,get_token
b=Path('/data_cached/wangzijun_p25/t19_review_20261029');api=HfApi(token=get_token())
queries=json.loads((b/'coverage_original_video_queries_20261030.json').read_text());byrev=collections.defaultdict(list)
for q in queries:byrev[q['revision']].append(q['path'])
records=[]
for revision,paths in byrev.items():
    for start in range(0,len(paths),300):
        batch=paths[start:start+300]
        for i in range(8):
            try:items=api.get_paths_info('phy2/phydataset',batch,repo_type='dataset',revision=revision);break
            except Exception:
                if i==7:raise
                time.sleep(2)
        found={x.path:x for x in items}
        for path in batch:
            x=found.get(path);records.append({'revision':revision,'path':path,'sha256':x.lfs.sha256 if x and x.lfs else None,'bytes':x.size if x else None,'missing':x is None})
        (b/'coverage_original_video_hashes_20261030.json').write_text(json.dumps({'records':records,'complete':len(records)==len(queries)},indent=2))
        print(json.dumps({'checked':len(records),'total':len(queries),'missing':sum(r['missing'] for r in records)}),flush=True)
