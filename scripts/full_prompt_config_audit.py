"""Exhaustive field ledger; unsupported mappings are unresolved, never passed."""
from pathlib import Path
import collections, functools, gzip, hashlib, json, math, re, sys, zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SOURCE=ROOT/'review/t10_config_alignment_20261102/videos.jsonl.gz'
OUT=ROOT/'review/full_prompt_audit_20261102'
ARCHIVE=ROOT/'review/prompt_rewrite_release_20261101/source/configs.zip'
T19=json.loads(gzip.decompress((OUT/'T19_SOURCE_PROJECTION.json.gz').read_bytes())) if (OUT/'T19_SOURCE_PROJECTION.json.gz').exists() else {}
HEADERS={r['canonical_video_id']:r for r in json.loads(gzip.decompress((OUT/'ORIGINAL_METADATA_HEADERS.json.gz').read_bytes()))} if (OUT/'ORIGINAL_METADATA_HEADERS.json.gz').exists() else {}

def equal(a,b):
    if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
        return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    if isinstance(a,bool) or isinstance(b,bool):return type(a)==type(b) and a==b
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):return math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12)
    return a==b

def norm(v):return math.sqrt(sum(x*x for x in v)) if isinstance(v,list) else abs(v)

def flatten(d,prefix=''):
    out={}
    if isinstance(d,dict):
        for k,v in d.items():
            p=prefix+'.'+k if prefix else k
            if isinstance(v,dict):out.update(flatten(v,p))
            elif not isinstance(v,str) and v is not None:out[p]=v
    return out

def context(raw):
    c=raw
    if raw.get('physics',{}).get('source_config'):c=raw['physics']['source_config']
    obs={o.get('spec',o)['name']:o.get('spec',o) for o in c.get('dynamic_objects',c.get('objects',c.get('source_physics_objects',[])))}
    actual=raw.get('actual_physical_parameters',{})
    for o in actual.get('bodies',[]):
        original=obs.get(o['name'],{})
        obs[o['name']]={**original,**{k:v for k,v in o.items() if v is not None}}
    policy=raw.get('physics',{}).get('runtime',{}).get('material_policy',{})
    if isinstance(policy.get('restitution'),(float,int)):
        obs={k:{**o,'restitution':policy['restitution']} for k,o in obs.items()}
    return c,obs,actual,flatten(c)

def resolve(key,old,raw,ctx,row=None):
    c,obs,actual,flat=ctx
    if row and row.get('scene')=='T19' and row.get('engine')=='genesis':
        proj=T19.get(row['sha256'])
        if proj:
            assert proj['config']==c
            common=c['common'];job=c['experiment'];specs={s['role']:s for s in proj['trajectory']['specifications']}
            if key=='striker.initial_speed':return job['speed_m_s'],'original_config.experiment.speed_m_s'
            if key=='striker.rolling_radius':return max(abs(s[2]) for s in specs['striker']['bounds']),'original_trajectory.specifications.striker.bounds.z_extent'
            if key=='lateral_offset':return job.get('offset_m',0),'original_config.experiment.offset_m'
            if key=='surface_gap':return common['surface_gap_m'],'original_config.common.surface_gap_m'
            if '.' in key:
                role,field=key.split('.',1);s=specs.get(role)
                if s:
                    alias={'height':'height_m','radius':'radius_m','initial_position':'pos','initial_quaternion':'quat','initial_xy':'pos'}
                    k=alias.get(field,field)
                    if k in s:return (s[k][:2] if field=='initial_xy' else s[k]),'original_trajectory.specifications.'+role+'.'+k
    if row and row.get('scene')=='T14S':
        renderer=ROOT/'review/prompt_revision_20261102/t14s_renderer.py'
        assert hashlib.sha256(renderer.read_bytes()).hexdigest()=='5476f5e89ed048980304b849ff81e9b5e057e92edfa543ff63f310e82a3a4641'
        cap=c.get('spring_force_n',c.get('inputs',{}).get('spring_force'))
        if cap is not None:
            k=max(.52,cap*1.02/.55)
            derived={'gravity_strength':c.get('gravity_mps2',c.get('inputs',{}).get('gravity')),'spring_force_cap':cap,'spring_stiffness':k,'spring_damping':.03*math.sqrt(k/.52),
                     'marker_mass':.018,'marker_yaw':6.,'eraser_mass':.012,'ball_mass':.012,'gate_mass':.025}
            if key in derived:return derived[key],'sha256_bound_renderer_formula.'+key
    g=actual.get('gravity_mps2',c.get('scene_overrides',{}).get('gravity',c.get('gravity',c.get('metadata',{}).get('gravity',c.get('common',{}).get('physics',{}).get('gravity')))))
    if key in ['gravity','gravity_vector','gravity_strength','prescribed_parameters.gravity_magnitude_mps2','prescribed_parameters.gravity_vector_mps2']:
        if g is None:g=c.get('gravity_mps2')
        if g is not None:return (g if isinstance(old,list) else norm(g)),'gravity_input'
    if key.startswith('prescribed_parameters.'):
        leaf=key.split('.',1)[1];params=c.get('experiment',{}).get('parameter',{})
        physical_aliases={'case_mass_kg':('t11_eyeglasses_case','mass'),'driver_mass_kg':('t11_driver_eraser','mass'),
                          'pencil_tin_mass_kg':('t11_relay_pencil_case','mass'),'case_friction_coefficient':('t11_eyeglasses_case','friction')}
        if actual and leaf in physical_aliases:
            name,prop=physical_aliases[leaf]
            if name in obs:return obs[name][prop],'actual_physical_parameters.bodies.'+name+'.'+prop
        if leaf in params:return params[leaf],'experiment.parameter.'+leaf
    if '.' in key:
        name,field=key.rsplit('.',1)
        if name in obs:
            o=obs[name]
            if field in o and o[field] is not None:return o[field],'object.'+key
            aliases={'initial_position':('pose','position'),'initial_euler_xyz':('pose','euler_xyz'),
                     'initial_quaternion':('pose','quaternion'),'initial_velocity':('motion','initial_velocity'),
                     'initial_angular_velocity':('motion','initial_angular_velocity')}
            if field in aliases:
                a,b=aliases[field]
                if b in o.get(a,{}):return o[a][b],'object.'+name+'.'+a+'.'+b
            if field=='initial_speed' and 'initial_velocity' in o.get('motion',{}):return norm(o['motion']['initial_velocity']),'object.'+name+'.motion.initial_velocity.norm'
            if field in ['initial_X','initial_Y','initial_Z'] and 'position' in o.get('pose',{}):return o['pose']['position']['XYZ'.index(field[-1])],'object.'+name+'.pose.position.'+field[-1]
            if field=='initial_angle' and name=='t10_supported_folder':return abs(o['pose']['euler_xyz'][1]),'object.'+name+'.pose.euler_xyz.abs_y'
            if field=='angle' and name=='t17_ramp':return abs(o['pose']['euler_xyz'][1]),'object.'+name+'.pose.euler_xyz.abs_y'
            if field in ['control_tilt_start_deg','control_tilt_end_deg']:
                target='start_angle_deg' if 'start' in field else 'end_angle_deg'
                if target in o.get('motion',{}):return o['motion'][target],'object.'+name+'.motion.'+target
            if field=='commanded_travel':
                frames=o.get('motion',{}).get('keyframes',[])
                if frames:return norm([b-a for a,b in zip(frames[0]['position'],frames[-1]['position'])]),'object.'+name+'.motion.keyframe_displacement.norm'
            if field=='force_peak':
                forces=[f for f in actual.get('external_forces',c.get('runtime_forces',[])) if f.get('target')==name]
                if forces:return max(norm(f['force_world']) for f in forces),'runtime_forces.'+name+'.peak'
        force=re.fullmatch(r'(.+)\.prescribed_force_(\d+)\.(.+)',key)
        if force:
            name,index,field=force.groups()
            fs=[f for f in actual.get('external_forces',c.get('runtime_forces',[])) if f.get('target')==name]
            if int(index)<=len(fs) and field in fs[int(index)-1]:return fs[int(index)-1][field],'runtime_force.'+key
    # Exact same-name input fields only. Inconsistent duplicate declarations stay unresolved.
    if key.endswith('.center_distance'):
        a,b,_=key.split('.')
        if a in obs and b in obs:return norm([x-y for x,y in zip(obs[a]['pose']['position'],obs[b]['pose']['position'])]),'object_pair.euclidean_initial_center_distance'
    exp=c.get('experiment',{});primary=exp.get('parameter',{})
    if key=='book_gap' and primary.get('parameter_name')=='gap':return primary['parameter_value'],'experiment.parameter.value_for_gap'
    if key=='book_interface_friction' and 'static_friction' in exp:
        assert equal(exp['static_friction'],exp['dynamic_friction'])
        return exp['static_friction'],'experiment.static_and_dynamic_friction'
    if key=='overlap_parameter' and 'overlap_length_m' in exp:return exp['overlap_length_m'],'experiment.overlap_length_m'
    leaf=key.removeprefix('prescribed_parameters.')
    for section in [c.get('parameter',{}),c.get('event_spec',{})]:
        if leaf in section:return section[leaf],'actual_event_input.'+leaf
    if key=='release_lateral_offset' and c.get('parameter',{}).get('source_parameter',{}).get('name')=='release_lateral_offset':return c['parameter']['value'],'parameter.value'
    candidates=[(p,v) for p,v in flat.items() if p==leaf or p.endswith('.'+leaf)]
    if candidates and all(equal(candidates[0][1],v) for _,v in candidates):return candidates[0][1],candidates[0][0]
    if key.startswith('prescribed_parameters.') and not candidates:return None,'no_exact_config_field'
    return None,'ambiguous_config_fields' if candidates else 'no_exact_config_field'

def main():
    OUT.mkdir(exist_ok=True);z=zipfile.ZipFile(ARCHIVE)
    @functools.lru_cache(maxsize=512)
    def config(member,h):
        b=z.read(member);assert hashlib.sha256(b).hexdigest()==h
        raw=json.loads(b);return raw,context(raw)
    stats=collections.Counter();missing=collections.Counter();bad=collections.Counter();examples={};schema={};by_scene=collections.defaultdict(collections.Counter)
    with gzip.open(SOURCE,'rt',encoding='utf8') as src,gzip.open(OUT/'FIELD_LEDGER.jsonl.gz','wt',encoding='utf8',compresslevel=1) as dst:
        for line in src:
            row=json.loads(line);vid=row['canonical_video_id'];d=row.get('config_download');tag=row['engine']+'/'+row['scene'];records=[]
            if d:raw,ctx=config(d['member'],d['sha256']);stats['config_hash_verified_videos']+=1
            elif vid in HEADERS:
                h=HEADERS[vid];assert h['video_sha256']==row['sha256'];raw=h['header'];ctx=context(raw);stats['original_metadata_header_verified']+=1
            else:raw,ctx={},context({});stats['no_original_config']+=1
            for f in row.get('parameter_facts',[]):
                k,v=f[0],f[-2];actual,path=resolve(k,v,raw,ctx,row) if raw else (None,'no_original_config')
                status='unresolved' if actual is None else 'equal' if equal(v,actual) else 'mismatch'
                rec={'key':k,'catalog_value':v,'config_value':actual,'source_path':path,'status':status};records.append(rec)
                stats[status]+=1;by_scene[tag][status]+=1
                if status=='unresolved':missing[(tag,k,path)]+=1
                if status=='mismatch':bad[(tag,k)]+=1
                if status!='equal':examples.setdefault(str((tag,k,status)),{'video_id':vid,**rec})
            dst.write(json.dumps({'video_id':vid,'config_sha256':d.get('sha256') if d else None,'fields':records},ensure_ascii=False)+'\n')
            stats['videos']+=1
            if stats['videos']%12000==0:print(json.dumps(dict(stats)),flush=True)
    summary={'counts':dict(stats),'by_scene':{k:dict(v) for k,v in by_scene.items()},
             'unresolved_keys':[{'scene':k[0],'key':k[1],'reason':k[2],'count':v} for k,v in missing.items()],
             'mismatch_keys':[{'scene':k[0],'key':k[1],'count':v} for k,v in bad.items()],
             'examples':list(examples.values())}
    (OUT/'FIELD_REPORT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'counts':dict(stats),'unresolved_key_count':len(missing),'mismatch_key_count':len(bad)}))

if __name__=='__main__':main()
