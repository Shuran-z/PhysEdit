"""Recover configs by registered hashes or exact source-video/config metadata links."""
import collections,gzip,hashlib,json,os,io
from pathlib import Path

R=Path('/data_cached/wangzijun_p25/config_bindings_20261031')
B=Path('/data2/wangzijun_p25/phy2_standardization_20261027')
ART=B/'phy2_release_v1.0.0_rc1'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
def input_prefix(packed):
    # Input headers precede frame states; retain the full compressed-object hash check.
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as f:prefix=f.read(256*1024).decode('utf8')
    decoder=json.JSONDecoder();i=prefix.index('{')+1;wanted={}
    while i<len(prefix):
        while prefix[i].isspace() or prefix[i]==',':i+=1
        if prefix[i]=='}':break
        key,i=decoder.raw_decode(prefix,i)
        while prefix[i].isspace() or prefix[i]==':':i+=1
        if key=='frames':break
        value,i=decoder.raw_decode(prefix,i)
        if key in ['experiment','scene_overrides','manifest']:wanted[key]=value
        if len(wanted)==3:return wanted
    return wanted
def main():
    tasks=load(R/'TASKS.jsonl.gz');rec={r['canonical_video_id']:r for r in load(R/('RECOVERED_LOCAL.jsonl.gz' if (R/'RECOVERED_LOCAL.jsonl.gz').exists() else 'RECOVERED.jsonl.gz'))}
    targets=[t for t in tasks if rec[t['canonical_video_id']]['status'] in ('UNRESOLVED','CURRENT_BUNDLE')]
    names={t['native_sample_id'] for t in targets};candidates=collections.defaultdict(list)
    for t in targets:
        c=t['current_render']
        if c:
            job=c['config_member'].split('/')[0]
            for p in Path('/data2/wangzijun_p25/resample_training_duplicates_20261030/jobs').glob(job+'/attempt*/'+t['camera']+'.json'):candidates[t['native_sample_id']].append(str(p))
            normalized=Path('/data2/wangzijun_p25/resample_training_duplicates_20261030/normalized_configs')/job/(t['camera']+'.json')
            if normalized.is_file():candidates[t['native_sample_id']].append(str(normalized))
    roots=[Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer'),Path('/data_cached/wangzijun_p25/isaac_out')]
    skip={'metadata','videos','rgb','frames','depth','seg','previews','logs','__pycache__','.git','node_modules','assets_library','assets_external','assets_generated','assets','realistic_assets','visual_assets_v1','visual_assets_v2','visual_assets_v3'}
    for root in roots:
        for directory,dirs,files in os.walk(root):
            dirs[:]=[d for d in dirs if d not in skip]
            p=Path(directory);matched=set(p.parts)&names
            for name in files:
                if not name.endswith('.json'):continue
                stem=name[:-5]
                own=set(matched)
                if stem in names:own.add(stem)
                for cam in ['cam01','cam02','cam03']:
                    if stem.endswith('__'+cam) and stem[:-7] in names:own.add(stem[:-7])
                if own:
                    for native in own:candidates[native].append(str(p/name))
        print(json.dumps({'scanned_root':str(root),'matched_cases':len(candidates)}),flush=True)
    ledger=[];video_index={};meta=collections.defaultdict(list)
    for line in (B/'processed.jsonl').open():
        a=json.loads(line)
        if a['kind']=='video':video_index[a['repo'],a['revision'],a['source_path'],a.get('archive_member') or '']=a
        elif a['logical_path'].endswith('.json.gz') and '/metadata/' in a['logical_path']:
            meta[a['release_id']].append(a)
    metabycase=collections.defaultdict(list)
    for release,items in meta.items():
        for a in items:
            parts=Path(a['logical_path']).parts
            native=next((v for v in parts if v in names),None)
            if native:metabycase[release,native].append(a)
    cache={};meta_cache={};unresolved=[];counts=collections.Counter()
    for t in targets:
        cid=t['canonical_video_id'];prev=rec[cid];expected=t['expected_sha256'];camera=t['camera']
        paths=list(dict.fromkeys(candidates.get(t['native_sample_id'],[])))
        if t['current_render']:
            paths=[p for p in paths if '/jobs/' in p]
        good=[]
        for path in paths:
            if path not in cache:
                p=Path(path)
                if p.stat().st_size>5*1024*1024:cache[path]=None;continue
                raw=p.read_bytes()
                try:d=json.loads(raw);cache[path]=(sha(raw),d)
                except Exception:cache[path]=None
            got=cache[path]
            if got and expected and got[0]==expected:good.append((path,got[0],'registered_config_sha256'))
        if not good and not expected:
            # Source path must identify this exact original video, not merely a lookalike filename.
            source=video_index.get((t['source_repo'],t['source_revision'],t['source_path'],''))
            if source and source['source_sha256']==t['video_sha256']:
                ms=metabycase[source['release_id'],source['native_sample_id']]
                ms=[a for a in ms if '__'+camera+'.json.gz' in a['logical_path'] or a['logical_path'].endswith('/'+camera+'.json.gz')]
                for a in ms:
                    if a['path'] not in meta_cache:
                        p=ART/a['path']
                        if not p.exists():meta_cache[a['path']]=None;continue
                        packed=p.read_bytes();assert sha(packed)==a['sha256']
                        try:m=input_prefix(packed)
                        except (ValueError,UnicodeDecodeError):m={}
                        meta_cache[a['path']]=m
                    m=meta_cache[a['path']]
                    if not m:continue
                    for path in paths:
                        got=cache.get(path)
                        if not got:continue
                        h,cfg=got
                        if Path(path).name.startswith('cam') and Path(path).stem!=camera:continue
                        exp=cfg.get('experiment');scene=cfg.get('scene_overrides')
                        # The renderer adds a QA-mode flag and resolves visual raytracing
                        # settings at runtime. They do not redefine physical source inputs.
                        clean_exp=lambda v:{k:x for k,x in (v or {}).items() if k!='production_qa_mode'}
                        clean_scene=lambda v:{k:x for k,x in (v or {}).items() if not k.startswith('raytracing')}
                        if exp and scene and clean_exp(exp)==clean_exp(m.get('experiment')) and clean_scene(scene)==clean_scene(m.get('scene_overrides')) and cfg.get('manifest')==m.get('manifest'):
                            good.append((path,h,'exact_video_source_physical_headers_runtime_visual_fields_excluded'))
        hashes={x[1] for x in good}
        if len(hashes)==1:
            path,h,method=good[0]
            rec[cid]=dict(canonical_video_id=cid,status='RECOVERED',sha256=h,local_path=path,method=method,
                expected_sha256=expected,previous_config_hash_existed=bool(expected))
            counts[method]+=1
        else:
            unresolved.append(dict(canonical_video_id=cid,config_candidates=len(paths),matching_hashes=len(hashes),
                expected_sha256=expected,example_paths=paths[:4],kind=prev['status']))
    with gzip.open(R/'RECOVERED_LOCAL.jsonl.gz','wt') as f:
        for t in tasks:f.write(json.dumps(rec[t['canonical_video_id']])+'\n')
    (R/'LOCAL_UNRESOLVED.json').write_text(json.dumps(unresolved,ensure_ascii=False,indent=2))
    print(json.dumps({'new_recoveries':counts,'overall':collections.Counter(x['status'] for x in rec.values()),'remaining':len(unresolved)}),flush=True)
    p29=[t for t in targets if t['evidence'].get('config_evidence',{}).get('host')=='p29']
    (R/'P29_REQUESTS.json').write_text(json.dumps(p29))

if __name__=='__main__':main()
