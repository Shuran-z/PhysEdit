import gzip,json
from pathlib import Path
B=Path('/data2/wangzijun_p25/phy2_standardization_20261027')
need={'src_genesis_t01_026','src_isaac_t06_006','src_isaac_t19_019'}
found=set()
for line in (B/'processed.jsonl').open():
    a=json.loads(line)
    if a['kind']!='artifact' or not a['logical_path'].endswith('.json.gz') or '/metadata/' not in a['logical_path']:continue
    key=a['engine'],a['scene_id']
    if key in found:continue
    p=B/'phy2_release_v1.0.0_rc1'/a['path']
    if not p.exists():continue
    try:d=json.loads(gzip.decompress(p.read_bytes()))
    except Exception:continue
    print(json.dumps({'artifact':a,'keys':{k:('dict:'+','.join(v.keys())[:600] if isinstance(v,dict) else type(v).__name__) for k,v in d.items()}},ensure_ascii=False),flush=True)
    found.add(key)
    if len(found)==40:break
