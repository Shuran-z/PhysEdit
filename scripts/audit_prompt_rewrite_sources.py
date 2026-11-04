"""Read-only source audit for a separately versioned prompt rewrite."""
from pathlib import Path
import collections
import gzip
import hashlib
import json
import math
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from physedit.core100_rebalanced import load
OUT=ROOT/'review/prompt_rewrite_release_20261101'
sha=lambda b:hashlib.sha256(b).hexdigest()

def bodies(c):
    return {o.get('spec',o)['name']:o.get('spec',o) for o in c.get('objects',c.get('dynamic_objects',[]))}

def safe_inputs(c):
    return {'objects':[{k:o[k] for k in ['name','semantic_label','fixed','visualization','mass','friction','restitution','size','pose','motion'] if k in o} for o in bodies(c).values()],
            'runtime_forces':c.get('runtime_forces',[]),
            'mechanisms':{k:c[k] for k in ['spring_actuators','joint_spring_actuators','contact_driven_hinges'] if c.get(k)},
            'render':{k:v for k,v in c.get('render',{}).items() if k in ['fps','pre_static_frames','frames','physics_steps_per_render_frame']},
            'physics':{k:v for k,v in c.get('scene_overrides',{}).items() if k in ['gravity','dt','substeps']}}

def compare(facts,c):
    objects=bodies(c);checks=[];conflicts=[]
    for fact in facts:
        key,value=fact[0],fact[-2]
        if '.' not in key:continue
        name,field=key.rsplit('.',1)
        if name not in objects:continue
        o=objects[name];actual=None
        if field in ['mass','friction','restitution']:actual=o.get(field)
        elif field=='initial_speed':
            v=o.get('motion',{}).get('initial_velocity')
            if v is not None:actual=math.sqrt(sum(x*x for x in v))
        if actual is not None:
            same=isinstance(value,(int,float)) and math.isclose(actual,value,rel_tol=1e-10,abs_tol=1e-12)
            rec={'key':key,'catalog_value':value,'object_spec_value':actual,'equal':same}
            checks.append(rec)
            if not same:conflicts.append(rec)
    return checks,conflicts

def main():
    (OUT/'audit').mkdir(parents=True,exist_ok=True)
    _,manifest,tasks,mapping=load();changed={r['clip_id'] for r in mapping}
    headers=json.loads((ROOT/'review/annotation_event_contracts_20261023/merged_source_headers.json').read_text(encoding='utf8'))
    rows=[]
    for t in tasks:
        cid=t['clip_id']
        if cid in changed:
            p=ROOT/f"benchmarks/critical_supplement_v1_20261101/evidence/{t['supplement_point_id']}.json.gz"
            c=json.loads(gzip.decompress(p.read_bytes()));source={'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes()),'type':'sealed_source_header'}
        elif cid.startswith('T19'):
            p=ROOT/f'benchmarks/core100_t19_isaac_v1_20261031/references/{cid}/config.json'
            c=json.loads(p.read_text(encoding='utf8'));source={'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes()),'type':'original_isaac_config'}
        else:
            c=headers[cid]
            assert c['sample_id']==t['sample_id'],cid
            source={'path':c['path'],'recorded_sha256':c['sha256'],'type':'previous_original_header_snapshot'}
            if cid=='T10_C05':
                p=ROOT.parent/'core100_author_audit_20261021/recovery_v3/T10_C05_recovery_config.json'
                c=json.loads(p.read_text(encoding='utf8'));source={'path':str(p),'sha256':sha(p.read_bytes()),'type':'registered_pre_generation_reconstruction'}
        checks,conflicts=compare(t['parameter_facts'],c)
        s=safe_inputs(c)
        control=t.get('external_control_inputs') or {}
        # Source header runtime_forces can omit conditional branches. Preserve the separately registered input recipe too.
        s['registered_controls']=control
        if t.get('clock',{}).get('conditional_force_recipe'):s['conditional_force_recipe']=t['clock']['conditional_force_recipe']
        row={'clip_id':cid,'sample_id':t['sample_id'],'reference':t['reference'],'source':source,
             'checks':checks,'conflicts':conflicts,'inputs':s,'clock':t.get('clock'),
             'parameter_facts':t['parameter_facts']}
        rows.append(row)
    (OUT/'audit/core100_source_audit.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf8')
    report={'roster':manifest['version'],'core100_cases':100,'core100_body_checks':sum(len(r['checks']) for r in rows),
            'core100_conflicts':[{'clip_id':r['clip_id'],'conflicts':r['conflicts']} for r in rows if r['conflicts']]}
    path=OUT/'source/videos.jsonl.gz';z=zipfile.ZipFile(OUT/'source/configs.zip');stats=collections.Counter();cache={};conflicts=[]
    with gzip.open(OUT/'audit/video_source_audit.jsonl.gz','wt',encoding='utf8') as dest:
        for i,line in enumerate(gzip.open(path,'rt',encoding='utf8')):
            r=json.loads(line);d=r.get('config_download');status='registered_inputs_only_original_config_unresolved';n=0;bad=[]
            if d:
                member=d['member'];h=d['sha256']
                if member not in cache:
                    b=z.read(member);assert sha(b)==h,member
                    cache[member]=json.loads(b)
                    if len(cache)>128:cache.pop(next(iter(cache)))
                c=cache[member];checks,bad=compare(r.get('parameter_facts',[]),c);n=len(checks);status='config_hash_verified'
            if bad:conflicts.append({'video_id':r['canonical_video_id'],'conflicts':bad})
            stats[status]+=1;stats['body_checks']+=n;stats['videos']+=1;stats['conflicting_videos']+=bool(bad)
            dest.write(json.dumps({'video_id':r['canonical_video_id'],'video_sha256':r['sha256'], 'config_sha256':d['sha256'] if d else None,
                                   'status':status,'checks':n,'conflicts':bad},ensure_ascii=False)+'\n')
            if (i+1)%12000==0:print(f'audited {i+1}/72000',flush=True)
    assert stats['videos']==72000
    report['full_catalog']=dict(stats);report['source_catalog_sha256']=sha(path.read_bytes());report['config_archive_sha256']=sha((OUT/'source/configs.zip').read_bytes())
    (OUT/'audit/catalog_conflicts.json').write_text(json.dumps(conflicts,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'audit/SOURCE_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
