"""Search known original Isaac output roots by exact source-video hash."""
import hashlib
import json
from pathlib import Path
ROOT=Path('/data2/liyuhan/core100_remaining74_admission_20261101')
jobs=json.loads((ROOT/'RETIMED_PLAN.json').read_text())
base=Path('/data_cached/wangzijun_p25/isaac_out')
out=[]
for j in jobs:
    candidates=[]
    for root in base.glob('*'):
        if not root.is_dir():continue
        for folder in root.glob(j['sample_id']+'*'):
            for video in folder.glob('cam01.mp4'):
                digest=hashlib.sha256(video.read_bytes()).hexdigest()
                row=dict(video_path=str(video),sha256=digest,exact_original_parent_match=digest==j['parent_video_sha256'])
                state=folder/'state.json'
                if row['exact_original_parent_match']and state.exists():
                    raw=state.read_bytes();s=json.loads(raw)
                    row.update(state_path=str(state),state_sha256=hashlib.sha256(raw).hexdigest(),schema=s.get('metadata',{}).get('schema'),frames=len(s.get('trajectory',[])))
                candidates.append(row)
    out.append(dict(clip_id=j['clip_id'],candidates=candidates,exact_matches=[c for c in candidates if c['exact_original_parent_match']]))
(ROOT/'ISAAC_NATIVE_DISCOVERY.json').write_text(json.dumps(out,indent=2));print(json.dumps([dict(clip_id=r['clip_id'],candidates=len(r['candidates']),matched=len(r['exact_matches']))for r in out]))
