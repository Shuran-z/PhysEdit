import gzip,json
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031')
with gzip.open(R/'unresolved_configs.jsonl.gz','rt') as f:
    ids={x['canonical_video_id'] for x in map(json.loads,f) if x['engine']=='isaac'}
p=Path('/data_cached/wangzijun_p25/colleague_download_check_20261031/physedit/catalog/videos.jsonl.gz')
done=set()
with gzip.open(p,'rt') as f:
    for r in map(json.loads,f):
        if r['canonical_video_id'] not in ids or r['quota_scene'] in done:continue
        done.add(r['quota_scene'])
        print(json.dumps({'id':r['canonical_video_id'],'fields':{k:v for k,v in r.items() if k in ['source_input_evidence','prompt_source_config_member','config_source_binding']}},ensure_ascii=False),flush=True)
