"""Read original execution logs for exact remaining sample IDs; no new labels."""
import collections,json
from pathlib import Path
ROOT=Path('/data_cached/wangzijun_p25/core100_remaining20_20261101')
jobs=json.loads((ROOT/'ORIGINAL_SOURCE_JOBS.json').read_text());by={j['sample_id']:j['clip_id']for j in jobs}
project=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer')
files=set()
for pattern in ('*genesis*.log','*t06*.log','*t09*.log','*t10*.log','*prod_render*.log'):
    files.update(Path('/tmp').glob(pattern))
for pattern in ('resume_t06*','t06_t07_t08*'):
    for p in (project/'runtime_queues').glob(pattern):
        if p.is_file():files.add(p)
        elif p.is_dir():files.update(p.rglob('*.log'))
files.update((project/'everyday_bifurcation_72k_T06_T10_v1/logs').glob('*.log'))
matches=[];counts=collections.Counter();read_files=[]
for path in sorted(files):
    if not path.is_file():continue
    recent=collections.deque(maxlen=2);n=0;hits=0
    try:
        with path.open(errors='replace')as f:
            for n,line in enumerate(f,1):
                own=[cid for name,cid in by.items()if name in line]
                if own:
                    hits+=1
                    for cid in own:
                        counts[cid]+=1
                        if counts[cid]<=80:matches.append(dict(clip_id=cid,file=str(path),line=n,preceding=list(recent),text=line.rstrip()[:2500]))
                recent.append(line.rstrip()[:1200])
        read_files.append(dict(path=str(path),bytes=path.stat().st_size,lines=n,matches=hits))
    except OSError:continue
(ROOT/'EXECUTION_LOG_SEARCH.json').write_text(json.dumps(dict(files=read_files,match_counts=dict(counts),matches=matches),indent=2))
print(json.dumps(dict(files=len(read_files),bytes=sum(x['bytes']for x in read_files),match_counts=dict(counts))))
