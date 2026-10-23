"""Prepare source-exact jobs for all named families, with explicit pending cases."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
try:
    from scripts.conditional_family_search import PROJECT,intervene
    from scripts.published_contact_vectors import vector
except ModuleNotFoundError:
    from conditional_family_search import PROJECT,intervene
    from published_contact_vectors import vector

T03=PROJECT.parent/'everyday_bifurcation_T03_v5_multilevel_cascade'


def close(a,b):
    if isinstance(a,(float,int)) and isinstance(b,(float,int)):return abs(a-b)<1e-8
    if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(close(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(close(x,y) for x,y in zip(a,b))
    return a==b


def header(path):
    data=b''
    with gzip.open(path,'rb') as stream:
        while len(data)<4*1024**2:
            block=stream.read(65536)
            if not block:break
            data+=block
            try:
                text=data.decode();i=text.index('"header":')+9
                return json.JSONDecoder().raw_decode(text,i+len(text[i:])-len(text[i:].lstrip()))[0]
            except (ValueError,UnicodeDecodeError):pass
    raise ValueError('published metadata header incomplete')


def build_job(scene,family,row,c,path,grid,expected,signature):
    theta=row['theta'];job=dict(scene_id=scene,family_id=family,sample_id=row['sample_id'],theta=theta,
        revision=row['revision'],fixed_context_sha256=signature,source_state_sha256=row['reference_state_sha256'],
        source_config_path=str(path),source_config_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),base_config=c,
        grid=sorted(set(grid+[theta])),normalization_domain=[min(grid+[theta]),max(grid+[theta])],
        parameter_unit=row['parameter_unit'],expected=expected,tolerance=.001 if row['parameter_unit']=='m/s' else .0005)
    if scene=='T03':
        token=row['sample_id'].split('__')[0]
        renderer=(T03/'scripts/render_t03_v5_multicam_r032.py' if 'R032' in token or 'R034' in token else
                  PROJECT.parent/'everyday_bifurcation_T01_v2_7s/scripts/render_t03_v5_multicam_r008.py')
        if not renderer.exists():raise ValueError('exact T03 renderer version not recovered: '+str(renderer))
        job['auditor']=str(T03/'scripts/audit_t03_v5_multilevel_cascade.py')
        dependencies=[renderer,Path(job['auditor'])]
    else:
        renderer=PROJECT/'scripts/render_sample.py'
        dependencies=[renderer,PROJECT/'scripts/build_project.py',PROJECT.parent/'scripts/render_t16_t20_physical_v5_20260816.py']
    job['renderer']=str(renderer)
    dependencies += [Path(__file__).with_name('conditional_family_search.py'),Path(__file__).with_name('published_contact_vectors.py')]
    job['backend_sources']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    identity={k:job[k] for k in ['scene_id','family_id','source_state_sha256','source_config_sha256','grid','expected','backend_sources']}
    job['job_id']=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]
    return job


def main():
    p=argparse.ArgumentParser();p.add_argument('--coverage',required=True);p.add_argument('--records',required=True)
    p.add_argument('--t03-parameters',required=True);p.add_argument('--t03-states',required=True);p.add_argument('--t03-reports',required=True);p.add_argument('--out',required=True)
    p.add_argument('--path-alias-proof')
    args=p.parse_args();jobs=[];pending=[];out=Path(args.out);out.mkdir(exist_ok=True,parents=True)
    proof=json.loads(Path(args.path_alias_proof).read_text()) if args.path_alias_proof else []
    aliases={r['published_path']:r['source_path'] for r in proof if r['matched'] or r.get('normalized_json_matches')}
    def resolve_paths(value):
        if isinstance(value,dict):return {k:resolve_paths(v) for k,v in value.items()}
        if isinstance(value,list):return [resolve_paths(v) for v in value]
        return aliases.get(value,value) if isinstance(value,str) else value
    for cov in json.loads(Path(args.coverage).read_text()):
        sid=cov['selected_samples'][len(cov['selected_samples'])//2]
        try:
            r=json.loads((Path(args.records)/(sid+'.json')).read_text());e=r['experiment'];param=e['parameter']
            path=PROJECT/'configs/production'/sid/'cam01.json';c=json.loads(path.read_text())
            if {o['name']:o for o in c['dynamic_objects']}!={a['name']:a['spec'] for a in r['actors']} or c['experiment']!=e or c['scene_overrides']!=r['scene_overrides']:
                raise ValueError('production config does not match published physical metadata')
            row=dict(sample_id=sid,theta=param['parameter_value'],revision=r['revision'],reference_state_sha256=r['metadata_sha256'],parameter_unit=param['parameter_unit'])
            job=build_job(r['scene_id'],param['parameter_name'],row,c,path,cov['released_grid'],vector(r),cov['fixed_context_sha256'])
            # A nontrivial intervention invokes the original builder and checks its source geometry.
            trial=next((v for v in job['grid'] if v!=job['theta']),None)
            if trial is None:raise ValueError('singleton released context; original domain still required')
            intervene(job,trial);jobs.append(job)
        except Exception as exc:pending.append(dict(scene_id=cov['scene_id'],family_id=cov['family_id'],sample_id=sid,reason=str(exc)))
    parameters=[json.loads(line) for line in Path(args.t03_parameters).read_text().splitlines()]
    states={r['sample_id']:r for r in json.loads(Path(args.t03_states).read_text())}
    reports={r['sample_id']:r['data'] for r in json.loads(Path(args.t03_reports).read_text()) if 'data' in r}
    configs=collections.defaultdict(list)
    roots=list(Path('/data_cached/wangzijun_p25').glob('t03_configs*'))+list((T03/'configs').iterdir())
    for root in roots:
        if root.is_dir():
            for path in root.glob('*/cam01.json'):configs[path.parent.name].append(path)
    groups=collections.defaultdict(list);domains=collections.defaultdict(set);semantic_domains=collections.defaultdict(set)
    for row in parameters:
        groups[row['fixed_context_sha256']].append(row)
        key=(row['family_id'],*row['sample_id'].split('__')[:3]);domains[key].add(row['theta'])
        semantic_domains[row['family_id']].add(row['theta'])
    def find_config(row):
        h=resolve_paths(header(states[row['sample_id']]['extracted_path']))
        expected={o['name']:o['spec'] for o in h['dynamic_objects']}
        for path in configs[row['sample_id']]:
            c=json.loads(path.read_text())
            physical=lambda scene:{k:v for k,v in scene.items() if not k.startswith('raytracing')}
            if {o['name']:o for o in c['dynamic_objects']}==expected and c['experiment']==h['experiment'] and physical(c['scene_overrides'])==physical(h['scene_overrides']):
                return path,c
        # r035 kept the intervention but changed solver settings. Restore those
        # settings from the selected published state, rather than using r032's.
        if h['experiment'].get('recovery',{}).get('revision')=='p29_r035_20261009':
            for path in configs[row['sample_id']]:
                c=json.loads(path.read_text())
                if {o['name']:o for o in c['dynamic_objects']}!=expected:continue
                c.update(experiment=h['experiment'],scene_overrides=h['scene_overrides'],render=h['render'])
                folder=out/'reconstructed_r035'/row['sample_id'];folder.mkdir(parents=True,exist_ok=True)
                restored=folder/'cam01.json';restored.write_text(json.dumps(c))
                (folder/'provenance.json').write_text(json.dumps(dict(kind='reconstructed_from_published_state_header',
                    source_config=str(path),source_config_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    published_state_sha256=states[row['sample_id']]['reference_state_sha256'],
                    restored_fields=['experiment','scene_overrides','render'],seed_origin='unchanged_original_config')))
                return restored,c
        raise ValueError('no recovered config matches selected published T03 header')
    for signature,members in groups.items():
        row=sorted(members,key=lambda r:r['theta'])[len(members)//2]
        try:
            path,c=find_config(row);report=reports[row['sample_id']]
            expected=dict(book_contacts_upper_can=int(report['first_contact_frame']['book_can'] is not None),
                upper_can_falls=int(report['observed_outcome'].startswith(('B1_','C'))),
                full_chain_phone_second_fall=int(report['observed_outcome']=='C2_full_chain_phone_second_fall'))
            key=(row['family_id'],*row['sample_id'].split('__')[:3]);grid=sorted(domains[key])
            grid_scope='same_version_background_gravity_released_values'
            if len(grid)<2:
                grid=sorted(semantic_domains[row['family_id']]);grid_scope='new_conditional_scan_using_same_semantic_axis_released_values'
            if len(grid)<2:raise ValueError('released axis domain has fewer than two values')
            job=build_job('T03',row['family_id'],row,c,path,grid,expected,signature)
            if (path.parent/'provenance.json').exists():
                job['config_reconstruction']=json.loads((path.parent/'provenance.json').read_text())
                job['probe_timeout_seconds']=7200
            job['grid_scope']=grid_scope
            if args.path_alias_proof:job['path_alias_proof_sha256']=hashlib.sha256(Path(args.path_alias_proof).read_bytes()).hexdigest()
            for endpoint in [min(members,key=lambda r:r['theta']),max(members,key=lambda r:r['theta'])]:
                if endpoint['theta']==row['theta']:continue
                _,other=find_config(endpoint)
                trial=intervene(job,endpoint['theta'])
                if not close(trial['dynamic_objects'],other['dynamic_objects']):raise ValueError('T03 axis recipe differs from original neighboring config')
            jobs.append(job)
        except Exception as exc:pending.append(dict(scene_id='T03',family_id=row['family_id'],sample_id=row['sample_id'],reason=str(exc)))
    # Round-robin by scene/family, so a long scene cannot starve the other families.
    buckets=collections.defaultdict(list)
    for job in jobs:buckets[(job['scene_id'],job['family_id'])].append(job)
    ordered=[]
    while any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key]:ordered.append(buckets[key].pop(0))
    (out/'plan.json').write_text(json.dumps(ordered))
    (out/'pending.json').write_text(json.dumps(pending,indent=2))
    summary=dict(prepared_jobs=len(jobs),by_scene=dict(collections.Counter(j['scene_id'] for j in jobs)),
        by_family=dict(collections.Counter(j['scene_id']+'/'+j['family_id'] for j in jobs)),pending=len(pending),
        pending_reasons=dict(collections.Counter(r['reason'] for r in pending)))
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
