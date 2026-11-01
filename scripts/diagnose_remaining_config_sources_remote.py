"""Inspect disagreements against exact-source render metadata before choosing configs."""
import collections,gzip,hashlib,json
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');B=Path('/data2/wangzijun_p25/phy2_standardization_20261027');OUT=R/'followup';OUT.mkdir(exist_ok=True)
with gzip.open(R/'TASKS.jsonl.gz','rt') as f:tasks={x['canonical_video_id']:x for x in map(json.loads,f)}
with gzip.open(R/'unresolved_configs.jsonl.gz','rt') as f:pending=list(map(json.loads,f))
chosen={}
for x in pending:
    if x['reason'].startswith(('Candidate','Multiple')):chosen.setdefault((x['engine'],x['scene'],x['reason']),x)
sources={};artifacts=collections.defaultdict(list)
for line in (B/'processed.jsonl').open():
    a=json.loads(line)
    if a['kind']=='video':sources[a['repo'],a['revision'],a['source_path'],a.get('archive_member') or '']=a
    elif '/metadata/' in a['logical_path'] and a['logical_path'].endswith('.json.gz'):artifacts[a['release_id']].append(a)
results=[]
for key,row in chosen.items():
    t=tasks[row['canonical_video_id']];source=sources.get((t['source_repo'],t['source_revision'],t['source_path'],''));entry=dict(id=t['canonical_video_id'],scene=t['scene'],reason=row['reason'],source=source,candidates=[])
    if source:
        candidates=[a for a in artifacts[source['release_id']] if source['native_sample_id'] in a['logical_path'] and ('__'+t['camera']+'.json.gz' in a['logical_path'] or a['logical_path'].endswith('/'+t['camera']+'.json.gz'))]
        if len(candidates)==1:
            a=candidates[0];p=B/'phy2_release_v1.0.0_rc1'/a['path'];packed=p.read_bytes();assert hashlib.sha256(packed).hexdigest()==a['sha256'];meta=json.loads(gzip.decompress(packed));entry['metadata_artifact']=a
            entry['metadata_top_keys']=list(meta)
            for path in row['candidate_summary'].get('example_paths',[]):
                p=Path(path)
                if not p.exists() or p.stat().st_size>5*1024*1024:continue
                cfg=json.loads(p.read_bytes());comparison={'path':path,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sample_id':cfg.get('sample_id'),'dataset_version':cfg.get('dataset_version')}
                for field in ['experiment','scene_overrides','render']:
                    left=cfg.get(field,{}) or {};right=meta.get(field,{}) or {}
                    comparison[field+'_differences']={k:{'config':left.get(k),'metadata':right.get(k)} for k in set(left)|set(right) if left.get(k)!=right.get(k)}
                objects=[v.get('spec',v) for v in meta.get('dynamic_objects',[])]
                comparison['object_specs_equal']=cfg.get('dynamic_objects')==objects
                comparison['manifest_equal']=cfg.get('manifest')==meta.get('manifest')
                entry['candidates'].append(comparison)
            del meta
    results.append(entry)
    (OUT/'DIAGNOSES.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps({'scene':t['scene'],'reason':row['reason'],'metadata_found':'metadata_artifact' in entry,'candidates':len(entry['candidates'])}),flush=True)
