import json
import gzip
from pathlib import Path
from huggingface_hub import HfApi
R=Path('/data_cached/wangzijun_p25/colleague_download_check_20261031')
api=HfApi()
samples=json.loads((R/'SAMPLE_ROWS.json').read_text())
want={r['canonical_video_id']:r for r in samples}
oldids={r['video_id'] for r in samples}
for p in [Path('/data2/wangzijun_p25/phy2_standardization_20261027/phy2_release_v1.0.0_rc1/manifests/videos.jsonl.gz'),Path('/data_cached/wangzijun_p25/author_release_20261029/metadata/videos.jsonl.gz')]:
    with gzip.open(p,'rt') as f:
        for line in f:
            r=json.loads(line)
            if r.get('video_id') in oldids:
                print(json.dumps({'manifest':str(p),'row':r},ensure_ascii=False),flush=True)
    print('MANIFEST_DONE',str(p),flush=True)
raise SystemExit()
for r in samples:
    print(json.dumps({'id':r['canonical_video_id'],'config':r.get('prompt_source_config'),
        'extra':{k:r[k] for k in ['current_render','resampling','prompt_source_config_member','media_version_update','previous_video_versions'] if k in r}},ensure_ascii=False),flush=True)
for prefix,rev in [('releases/physedit/shards','cacc80bb8060a1479c2a34f0810b21ad57432181'),('data/T03/qualified_existing_480p_569_20261010','0df3971705a89673a2913566ae888ab5fbc444be'),('data/T11/isaac_320_480p_reconciled_20261015','0df3971705a89673a2913566ae888ab5fbc444be'),('releases/physedit','e910d3227a632901193277db0c96b7a2f383969d')]:
    try:
        print(json.dumps({'prefix':prefix,'rev':rev,'files':[{'path':x.path,'size':getattr(x,'size',None)} for x in api.list_repo_tree('phy2/phydataset',path_in_repo=prefix,revision=rev,repo_type='dataset')]}),flush=True)
    except Exception as e:print(type(e).__name__,str(e)[:200],flush=True)
