"""Read original upload/reuse receipts and source bytes; never run a renderer."""
import gzip,hashlib,json
from pathlib import Path

ROOT=Path('/data_cached/wangzijun_p25/core100_remaining20_20261101');ROOT.mkdir(exist_ok=True)
BASE=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1')
jobs=json.loads((ROOT/'ORIGINAL_SOURCE_JOBS.json').read_text())
plan_path=Path('/data_cached/wangzijun_p25/genesis_reuse_plan.json')
plan=json.loads(plan_path.read_text())
out=[]
for j in jobs:
    row=dict(clip_id=j['clip_id'],sample_id=j['sample_id'],transfer_records=j['transfer_records'])
    stem=j['sample_id']+'__cam01';scene=j['clip_id'][:3]
    entries=plan[scene]['reuse'];matches=[x for x in entries if x['new']==stem]
    row['reuse_matches']=matches;row['reuse_plan_sha256']=hashlib.sha256(plan_path.read_bytes()).hexdigest()
    row['render_plan_contains']=stem in plan[scene]['render']
    row['transfer_source_checks']=[]
    for record in j['transfer_records']:
        p=Path(record['source']);check=dict(path=str(p),exists=p.exists())
        if p.is_file():
            raw=p.read_bytes();check.update(sha256=hashlib.sha256(raw).hexdigest(),matches_original_transfer=hashlib.sha256(raw).hexdigest()==record['sha256'])
            if p.suffix=='.json':
                s=json.loads(raw);check['config_keys']=list(s);check['render']=s.get('render');check['scene_overrides']=s.get('scene_overrides')
        row['transfer_source_checks'].append(check)
    row['nearby_original_sidecars']=[]
    for group in ('production','pilot'):
        for name in {stem,j['sample_id'],*[x.get('old','')for x in matches]}:
            if not name:continue
            folder=BASE/'outputs'/group/name
            if folder.is_dir():
                row['nearby_original_sidecars'].append(dict(folder=str(folder),files=[str(p)for p in folder.glob('*/*')if p.is_file()and p.suffix in('.json','.gz','.log')]))
    out.append(row)
(ROOT/'ORIGINAL_REUSE_TRACE.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
