import os,json,gzip,hashlib,collections
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'remaining2241';ids={x['canonical_video_id'] for x in map(json.loads,gzip.open(R/'remaining6767/REMAINING.jsonl.gz','rt'))};tasks=[x for x in map(json.loads,gzip.open(R/'TASKS.jsonl.gz','rt')) if x['canonical_video_id'] in ids];names={x['native_sample_id'] for x in tasks};roots=['/data2/wangzijun_p25','/data_cached/wangzijun_p25','/home/wangzijun_p25'];skip={'metadata','videos','frames','rgb','depth','seg','previews','assets','assets_library','assets_external','assets_generated','realistic_assets','visual_assets_v1','visual_assets_v2','visual_assets_v3','.git','.cache','node_modules','__pycache__','venv','.venv','site-packages','hunyuan_cache','h3_cache','wan_cache','ltx_cache','datasets_cache','caches','isaac_cache','isaac_runtime'};out=[];dirs_seen=0
for root in roots:
 for d,ds,fs in os.walk(root):
  ds[:]=[x for x in ds if x not in skip];dirs_seen+=1
  if not any(k in d.lower() for k in ['phys','isaac','ase_','backup','archive','formal','resample','source','provenance','quarantine']):continue
  inherited=names&set(Path(d).parts)
  for name in fs:
   if not name.endswith(('.json','.json.gz','.json.bak','.json.backup')):continue
   stem=name.removesuffix('.gz').removesuffix('.bak').removesuffix('.backup').removesuffix('.json');native=stem.rsplit('__cam',1)[0];matched=inherited|({native} if native in names else set())
   if not matched:continue
   p=Path(d)/name
   try:
    if not 100<p.stat().st_size<2000000:continue
    raw=p.read_bytes();raw=gzip.decompress(raw) if name.endswith('.gz') else raw;c=json.loads(raw)
    if not c.get('dynamic_objects') or 'frames' in c or not c.get('render'):continue
   except (OSError,ValueError):continue
   out.append(dict(path=str(p),native_sample_ids=sorted(matched),sha256=hashlib.sha256(raw).hexdigest(),dataset_version=c.get('dataset_version'),source_provenance=c.get('source_provenance')))
(O/'EXPANDED_CONFIG_CANDIDATES.json').write_text(json.dumps(out,indent=2));print(json.dumps({'directories_scanned':dirs_seen,'candidates':len(out),'by_scene':dict(collections.Counter(next(iter(x['native_sample_ids']))[:3] for x in out)),'previously_unscanned_roots':[p for p in sorted({str(Path(x['path']).parent) for x in out}) if not any(k in p for k in ['ase_asset_importer','isaac_out','config_bindings_20261031'])][:20]}),flush=True)
