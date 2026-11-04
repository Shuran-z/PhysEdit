"""Read-only source-config/receipt collector scoped to requested native cases."""
import collections,gzip,hashlib,io,json,os,tarfile
from pathlib import Path
R=Path('/tmp/physedit_config_lookup_6767');R.mkdir(exist_ok=True)
tasks=json.loads((R/'REQUESTS.json').read_text());names={x['native_sample_id'] for x in tasks}
roots=[Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer'),Path('/data2/wangzijun_p25/liyuhan/phydataset/ase_asset_importer')]
skip={'metadata','videos','rgb','frames','depth','seg','previews','__pycache__','.git','node_modules','assets_library','assets_external','assets_generated','assets','realistic_assets','visual_assets_v1','visual_assets_v2','visual_assets_v3'}
index=[];seen=set();counts=collections.Counter()
with tarfile.open(R/'source_files.tar.gz','w:gz',compresslevel=3) as tar:
    for root in roots:
        if not root.exists():continue
        for directory,dirs,files in os.walk(root):
            dirs[:]=[d for d in dirs if d not in skip]
            directory=Path(directory);matches=set(directory.parts)&names
            for name in files:
                if not name.endswith('.json'):continue
                own=set(matches);stem=name[:-5]
                if stem in names:own.add(stem)
                for cam in ['cam01','cam02','cam03']:
                    if stem.endswith('__'+cam) and stem[:-7] in names:own.add(stem[:-7])
                if not own:continue
                p=directory/name
                if p.stat().st_size>5*1024*1024:continue
                raw=p.read_bytes()
                try:doc=json.loads(raw)
                except Exception:continue
                if not isinstance(doc,dict):continue
                kind='config' if ('dynamic_objects' in doc or 'objects' in doc or 'physics' in doc) else 'receipt'
                h=hashlib.sha256(raw).hexdigest();member='raw/'+h+'.json'
                if h not in seen:
                    item=tarfile.TarInfo(member);item.size=len(raw);tar.addfile(item,io.BytesIO(raw));seen.add(h)
                for native in own:index.append(dict(native_sample_id=native,path=str(p),sha256=h,member=member,kind=kind,bytes=len(raw)))
                counts[kind]+=1
with gzip.open(R/'INDEX.jsonl.gz','wt') as f:
    for x in index:f.write(json.dumps(x)+'\n')
summary=dict(requested_videos=len(tasks),requested_cases=len(names),source_files=dict(counts),unique_payloads=len(seen),archive_bytes=(R/'source_files.tar.gz').stat().st_size)
(R/'SUMMARY.json').write_text(json.dumps(summary));print(json.dumps(summary),flush=True)
