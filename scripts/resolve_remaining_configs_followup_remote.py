"""Resolve ambiguous configs with source SHA, complete object specs and camera contracts."""
import collections,gzip,hashlib,io,json,os,multiprocessing
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=Path(os.environ.get('CONFIG_RECOVERY_OUT',str(R/'followup')));O.mkdir(exist_ok=True);B=Path('/data2/wangzijun_p25/phy2_standardization_20261027');ART=B/'phy2_release_v1.0.0_rc1'
def load(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
def sha(raw):return hashlib.sha256(raw).hexdigest()
WORKER=None
def run_worker(row):return WORKER(row)
def main():
    tasks={x['canonical_video_id']:x for x in load(R/'TASKS.jsonl.gz')}
    prior=load(O/'NEW_RECOVERIES.jsonl.gz') if (O/'NEW_RECOVERIES.jsonl.gz').exists() else []
    prior_ids={x['canonical_video_id'] for x in prior}
    pending_path=Path(os.environ.get('CONFIG_PENDING_MANIFEST',str(R/'unresolved_configs.jsonl.gz')))
    pending=[x for x in load(pending_path) if (os.environ.get('CONFIG_CHECK_ALL')=='1' or x['reason'].startswith(('Candidate','Multiple'))) and x['canonical_video_id'] not in prior_ids]
    names={tasks[x['canonical_video_id']]['native_sample_id'] for x in pending};paths=collections.defaultdict(set)
    roots=['/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer','/data2/wangzijun_p25/liyuhan/phydataset/ase_asset_importer','/data_cached/wangzijun_p25/isaac_out']
    skip={'metadata','videos','rgb','frames','depth','seg','previews','logs','__pycache__','.git','node_modules','assets_library','assets_external','assets_generated','assets','realistic_assets','visual_assets_v1','visual_assets_v2','visual_assets_v3'}
    for root in roots:
        for directory,dirs,files in os.walk(root):
            dirs[:]=[d for d in dirs if d not in skip]
            matched=set(Path(directory).parts)&names
            for name in files:
                if not name.endswith('.json'):continue
                own=set(matched);stem=name[:-5]
                if stem in names:own.add(stem)
                for cam in ['cam01','cam02','cam03']:
                    if stem.endswith('__'+cam) and stem[:-7] in names:own.add(stem[:-7])
                for native in own:paths[native].add(str(Path(directory)/name))
        print(json.dumps({'root_scanned':root,'case_names':len(paths)}),flush=True)
    imported_origins=collections.defaultdict(list)
    if (O/'P26_INDEX.jsonl.gz').exists():
        for x in load(O/'P26_INDEX.jsonl.gz'):
            p=str(O/'p26_raw'/(x['sha256']+'.json'));paths[x['native_sample_id']].add(p);imported_origins[p].append({'host':'p26','path':x['path'],'sha256':x['sha256']})
    source_exact={};source_hash=collections.defaultdict(list);meta_byrelease=collections.defaultdict(list)
    for line in (B/'processed.jsonl').open():
        a=json.loads(line)
        if a['kind']=='video':
            source_exact[a['repo'],a['revision'],a['source_path'],a.get('archive_member') or '']=a;source_hash[a['source_sha256']].append(a)
        elif ('/metadata/' in a['logical_path'] or Path(a['logical_path']).name in ['metadata.json.gz','media_binding.json']) and a['logical_path'].endswith(('.json','.json.gz')):meta_byrelease[a['release_id']].append(a)
    meta_index=collections.defaultdict(list)
    for release,values in meta_byrelease.items():
        for a in values:
            parts=Path(a['logical_path']).parts
            native=next((p for p in parts if p in names),None)
            if not native:
                base=parts[-1].removesuffix('.gz').removesuffix('.json').removesuffix('__trajectory')
                for cam in ['cam01','cam02','cam03']:
                    prefix=base.split('__'+cam)[0]
                    if prefix in names:native=prefix;break
            if native:meta_index[release,native].append(a)
    # Read only the input headers and object specs; frame states are never retained.
    meta_cache={};cfg_cache={};recovered=list(prior);remaining=[];attestations=[]
    def metadata(a):
        if a['path'] in meta_cache:return meta_cache[a['path']]
        p=ART/a['path']
        if not p.is_file():return None
        raw=p.read_bytes();assert sha(raw)==a['sha256']
        if a['path'].endswith('.gz'):raw=gzip.decompress(raw)
        # Decode only top-level input fields; never parse the enormous frame list.
        text=raw.decode('utf8');decoder=json.JSONDecoder();value={}
        for key in ['experiment','manifest','scene_overrides','render','camera_id','camera_bundle','dynamic_objects','media_binding.json','COMPLETED.json']:
            needle='\n  '+json.dumps(key)+':';position=text.rfind(needle)
            if position<0:value[key]=None;continue
            position+=len(needle)
            while position<len(text) and text[position].isspace():position+=1
            value[key]=decoder.raw_decode(text,position)[0]
        if not any(v is not None for v in value.values()) and text.lstrip().startswith('{"'):
            full=json.loads(text)
            value={key:full.get(key) for key in value}
        meta_cache[a['path']]=value
        return value
    def cfg(path):
        if path not in cfg_cache:
            p=Path(path)
            if p.stat().st_size>5*1024*1024:cfg_cache[path]=None
            else:
                raw=p.read_bytes()
                try:cfg_cache[path]=(sha(raw),json.loads(raw))
                except Exception:cfg_cache[path]=None
        return cfg_cache[path]
    def resolve_one(row):
        t=tasks[row['canonical_video_id']];cid=t['canonical_video_id'];camera=t['camera'];native=t['native_sample_id']
        exact=source_exact.get((t['source_repo'],t['source_revision'],t['source_path'],''))
        sources=[exact] if exact and exact['source_sha256']==t['video_sha256'] else [a for a in source_hash[t['video_sha256']] if a['engine']==t['engine'] and a['native_sample_id']==native and a['camera_id']==camera]
        good=[];why=collections.Counter();source_meta=[]
        for source in sources:
            for a in meta_index[source['release_id'],source['native_sample_id']]:
                logical=a['logical_path']
                shared=Path(logical).name in [native+'.json.gz',native+'.json',native+'__trajectory.json.gz']
                if not (shared or '__'+camera+'.json' in logical or logical.endswith('/'+camera+'.json.gz') or logical.endswith('/'+camera+'.json')):continue
                m=metadata(a)
                if not m:continue
                source_meta.append(a['path'])
                objects=[o.get('spec',o) for o in (m.get('dynamic_objects') or [])]
                exp=m.get('experiment') or {};scene=m.get('scene_overrides') or {};render=m.get('render') or {}
                binding=m.get('media_binding.json') or {};completed=m.get('COMPLETED.json') or {}
                attested=(exp.get('config_input_sha256') or binding.get('render_config_sha256') or completed.get('config_sha256') or '').lower()
                physics_attested=(binding.get('physics_config_sha256') or '').lower()
                config_paths=set(paths[native])
                if isinstance(binding.get('render_config'),str) and Path(binding['render_config']).is_file():config_paths.add(binding['render_config'])
                for path in sorted(config_paths):
                    got=cfg(path)
                    if not got:continue
                    h,c=got
                    if attested and h==attested:
                        good.append((path,h,'original_render_metadata_config_input_sha256',a));continue
                    if physics_attested and h==physics_attested:
                        good.append((path,h,'original_render_metadata_physics_config_sha256',a));continue
                    # A post-render metadata adapter is not the original Genesis input.
                    # Explicit execution input hashes above still admit genuinely executed inputs.
                    if t['engine']=='genesis' and c.get('dataset_version')=='hf_staging_normalized_v1' and '/metadata/' in (c.get('source_provenance') or {}).get('hf_path',''):
                        why['later_metadata_derived_adapter_not_original_input']+=1;continue
                    if not shared and Path(path).name.startswith('cam') and Path(path).stem!=camera:continue
                    if not objects or c.get('dynamic_objects')!=objects:why['object_specs_differ']+=1;continue
                    if c.get('manifest')!=m.get('manifest'):why['background_manifest_differs']+=1;continue
                    cs={k:v for k,v in (c.get('scene_overrides') or {}).items() if not k.startswith('raytracing')}
                    ms={k:v for k,v in scene.items() if not k.startswith('raytracing')}
                    if cs!=ms:why['physical_solver_settings_differ']+=1;continue
                    ce=dict(c.get('experiment') or {});me=dict(exp)
                    for k in ['production_qa_mode','config_input_sha256']:ce.pop(k,None);me.pop(k,None)
                    # Per-view metadata can carry the shared primary simulation's camera id.
                    if m.get('camera_bundle'):
                        for v in [ce,me]:
                            if isinstance(v.get('formal_sampling'),dict):v['formal_sampling']={k:x for k,x in v['formal_sampling'].items() if k!='camera_id'}
                    if ce!=me:why['experiment_inputs_differ']+=1;continue
                    cr=c.get('render') or {}
                    render_keys=['fps','frames','resolution','fixed_view','physics_steps_per_render_frame','pre_static_frames']
                    if any(cr.get(k)!=render.get(k) for k in render_keys if k in cr or k in render):why['camera_or_render_contract_differs']+=1;continue
                    if not cr.get('save_video') or Path(cr['save_video']).name!=Path(render.get('save_video') or '').name:why['output_video_name_differs']+=1;continue
                    good.append((path,h,'shared_trajectory_source_sha_complete_inputs_and_primary_render_contract' if shared else 'source_video_sha_full_object_specs_solver_and_camera_contract',a))
        attested_good=[g for g in good if g[2]=='original_render_metadata_config_input_sha256']
        if not attested_good:attested_good=[g for g in good if g[2]=='original_render_metadata_physics_config_sha256']
        if attested_good:good=attested_good
        hashes={g[1] for g in good}
        if len(hashes)==1:
            path,h,method,a=good[0];record=dict(canonical_video_id=cid,status='RECOVERED',local_path=path,sha256=h,method=method,
                evidence=dict(video_sha256=t['video_sha256'],metadata_source_key=a['source_key'],metadata_source_sha256=a['source_sha256'],metadata_artifact_sha256=a['sha256'],config_byte_sha256=h))
            if path in imported_origins:record['evidence']['config_original_locations']=imported_origins[path]
            return True,record
        else:return False,dict(canonical_video_id=cid,scene=t['scene'],reason=row['reason'],source_video_records=len(sources),source_metadata_objects=len(set(source_meta)),compatible_hashes=len(hashes),rejections=dict(why),candidate_paths=len(paths[native]),compatible_config_candidates=[{'path':g[0],'sha256':g[1],'method':g[2],'metadata_source_key':g[3]['source_key']} for g in good[:12]])
    global WORKER
    WORKER=resolve_one
    with multiprocessing.get_context('fork').Pool(32) as pool:
        for i,(ok,record) in enumerate(pool.imap_unordered(run_worker,pending,chunksize=6)):
            (recovered if ok else remaining).append(record)
            if (i+1)%250==0:
                with gzip.open(O/'NEW_RECOVERIES.partial.jsonl.gz','wt') as f:
                    for x in recovered:f.write(json.dumps(x)+'\n')
                (O/'PROGRESS.json').write_text(json.dumps({'processed':i+1,'total':len(pending),'recovered':len(recovered)}))
                print((O/'PROGRESS.json').read_text(),flush=True)
    with gzip.open(O/'NEW_RECOVERIES.jsonl.gz','wt') as f:
        for x in recovered:f.write(json.dumps(x)+'\n')
    with gzip.open(O/'REMAINING.jsonl.gz','wt') as f:
        for x in remaining:f.write(json.dumps(x)+'\n')
    summary=dict(targeted=len(pending)+len(prior),recovered=len(recovered),new_this_pass=len(recovered)-len(prior),remaining=len(remaining),by_scene=dict(collections.Counter(tasks[x['canonical_video_id']]['scene'] for x in recovered)))
    (O/'SUMMARY.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
