import gzip,json
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031')
with gzip.open(R/'TASKS.jsonl.gz','rt') as f:
    rows=[t for t in map(json.loads,f) if t['evidence'].get('config_evidence',{}).get('host')=='p29']
(R/'P29_REQUESTS.json').write_text(json.dumps(rows))
print(len(rows))
