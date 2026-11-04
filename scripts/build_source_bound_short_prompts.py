"""Produce an additive candidate catalog, preserving every source row and split."""
from pathlib import Path
import collections
import gzip
import hashlib
import json
import sys
import zipfile
import copy

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from physedit.natural_short_prompt import build, VERSION
from physedit.core100_rebalanced import load
from audit_prompt_rewrite_sources import safe_inputs

OUT=ROOT/'review/prompt_rewrite_release_20261101'
sha=lambda b:hashlib.sha256(b).hexdigest()
def put(path,data):
    p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')

def required(scene,facts):
    # Keep source intervention coordinates, not just visually inferable defaults.
    keys={f[0] for f in facts}
    rules={'T10':['t10_support_pen.initial_X','t10_support_pen.initial_Y','t10_support_pen.initial_Z','t10_supported_folder.initial_angle'],
           'T15':['book_laptop_center_distance_m','laptop_phone_center_distance_m'],
           'T04':['t04v3_stack_book_bottom.friction']}
    return [k for k in rules.get(scene,[]) if k in keys]

def main():
    src=OUT/'source/videos.jsonl.gz';source_hash=sha(src.read_bytes())
    source_audit=json.loads((OUT/'audit/SOURCE_REPORT.json').read_text(encoding='utf8'))
    assert source_hash==source_audit['source_catalog_sha256']
    conflicts={r['video_id']:r['conflicts'] for r in json.loads((OUT/'audit/catalog_conflicts.json').read_text(encoding='utf8'))}
    fallback_audit={r['canonical_video_id']:r for r in map(json.loads,gzip.open(ROOT/'review/scene_videos_20261031/MISSING_CONFIG_ALIGNMENT.jsonl.gz','rt',encoding='utf8'))}
    core={r['clip_id']:r for r in map(json.loads,(OUT/'audit/core100_source_audit.jsonl').read_text(encoding='utf8').splitlines())}
    fresh={r['clip_id']:r for r in json.loads((OUT/'source/core_probe_result.json').read_text())}
    bindings={r['clip_id']:r for r in json.loads((ROOT/'annotation_site/resources/core100_distance_bindings.json').read_text(encoding='utf8'))['cases']}
    windows=json.loads((ROOT/'annotation_site/resources/core100_physical_windows_20261027.json').read_text(encoding='utf8'))['cases']
    _,m,tasks,_=load();coreout=[]
    for t in tasks:
        t=copy.deepcopy(t)
        a=core[t['clip_id']];c=a['inputs'];clock=dict(t.get('clock') or {})
        original_file=OUT/'source'/f"{t['clip_id']}_original.json"
        if original_file.exists():
            assert sha(original_file.read_bytes())==a['source']['recorded_sha256']
            fresh_config=json.loads(original_file.read_text(encoding='utf8'))
            c=safe_inputs(fresh_config)
            c['registered_controls']=t.get('external_control_inputs') or {}
            td=fresh_config.get('scene_overrides',{}).get('dt');steps=fresh_config.get('render',{}).get('physics_steps_per_render_frame')
            if td and steps:clock['physical_dt_s']=td*steps
        if t['clip_id'] in fresh:
            f=fresh[t['clip_id']]
            if f.get('actual_sha256')==f.get('recorded_sha256'):
                td=f.get('time_diagnostic') or {}
                if td.get('sim_dt') and td.get('physics_steps_per_render_frame'):clock['physical_dt_s']=td['sim_dt']*td['physics_steps_per_render_frame']
        binding=bindings.get(t['clip_id'],{});condition_origin=None
        if t.get('condition_frame_index') is not None:condition_origin=t['condition_frame_index']
        elif binding.get('reference_video_sha256')==t['reference']['sha256']:condition_origin=binding.get('condition_frame_index')
        elif t['clip_id'].startswith('T19'):condition_origin=0
        if condition_origin is not None and 'initial_hold_duration_s' not in clock:
            pre=c.get('render',{}).get('pre_static_frames',0)
            fps=c.get('render',{}).get('fps')
            window=windows.get(t['clip_id'],{})
            if window.get('reference_video_sha256')==t['reference']['sha256']:
                fps=window['reference_media_fps'];clock['physical_dt_s']=window['physical_frame_period_s']
            if fps and pre:
                remaining=max(0,pre-condition_origin-1)
                clock.update(remaining_static_frames=remaining,static_clock_hz=fps,initial_hold_duration_s=remaining/fps)
        critical=[]
        if binding.get('reference_video_sha256')==t['reference']['sha256']:
            critical=[(binding.get('parameter'),binding.get('theta'))]
        else:
            critical=[(k,v) for k,v in t.get('verified_parameter_truth',{}).items() if k!='gravity']
        original_facts=copy.deepcopy(t['parameter_facts']);extra_required=[];primary_evidence=[]
        for k,v in critical:
            if not isinstance(v,(int,float)) or k=='joint_global_configuration':continue
            exists=next((f for f in t['parameter_facts'] if f[0]==k),None)
            aliases={'support_x':'t10_support_pen.initial_X','commanded_support_extraction_speed_mps':'commanded_extraction_speed_mps',
                     'overlap_length':'overlap_length_m'}
            alias=next((f for f in t['parameter_facts'] if f[0]==aliases.get(k)),None)
            if alias:
                extra_required.append(alias[0]);primary_evidence.append({'key':k,'registered_value':v,'source_config_value':alias[-2],
                    'source_field':alias[0],'registration_conflict':abs(alias[-2]-v)>1e-9})
                continue
            if exists:
                assert abs(exists[-2]-v)<1e-9,(t['clip_id'],k)
            else:
                unit=('m/s' if 'speed' in k else 'N' if 'force' in k else 'degrees' if 'angle' in k else
                      '' if any(x in k for x in ['friction','ratio','normalized']) else 'm' if any(x in k for x in ['gap','distance','margin','overlap','support_x','offset','eccentricity','position']) else None)
                if unit is None:continue
                t['parameter_facts'].append([k,v,unit])
            extra_required.append(k);primary_evidence.append({'key':k,'value':v,'source':'same-reference input parameter registration; not a boundary threshold'})
        r=build(t,c,clock,required(t['clip_id'][:3],t['parameter_facts'])+extra_required)
        r.update(clip_id=t['clip_id'],sample_id=t['sample_id'],reference=t['reference'],original_prompt=t['prompt_variants_en'][0],
                 prompt_sha256=sha(r['prompt'].encode()),roster=m['version'],full_parameter_facts=original_facts,full_control_inputs=c,
                 primary_input_registration=primary_evidence)
        if a['conflicts']:r['issues'].append('source_parameter_conflict')
        # The choice of source-frame zero for retained inputs still needs a pinned condition-frame check.
        if condition_origin is None:r['issues'].append('condition_frame_origin_not_explicit_in_roster')
        r['condition_frame_index']=condition_origin
        r['resolved_control_clock']=clock
        r['status']='needs_review' if r['issues'] else 'candidate'
        coreout.append(r)
    put('core100/short_prompts.json',coreout)
    (OUT/'core100/完整对照.md').write_text('\n'.join(f"## {r['clip_id']}\n\n原版：\n```text\n{r['original_prompt']}\n```\n\n新版短版：\n```text\n{r['prompt']}\n```\n\n核查项：{', '.join(r['issues']) or '当前检查通过'}\n" for r in coreout),encoding='utf8')
    if '--core-only' in sys.argv:
        print(json.dumps({'cases':len(coreout),'issues':dict(collections.Counter(x for r in coreout for x in r['issues']))},ensure_ascii=False));return
    stats=collections.Counter();issues=collections.Counter();scenes=collections.Counter();cache={};examples={};textcache={}
    z=zipfile.ZipFile(OUT/'source/configs.zip');newdir=OUT/'catalog';newdir.mkdir(exist_ok=True)
    with gzip.open(newdir/'prompt_rewrites_72000.jsonl.gz','wt',encoding='utf8',compresslevel=1) as prompts,gzip.open(newdir/'original_rows_72000.jsonl.gz','wt',encoding='utf8',compresslevel=1) as originals,gzip.open(newdir/'metadata_72000.jsonl.gz','wt',encoding='utf8',compresslevel=1) as metadata:
        for line in gzip.open(src,'rt',encoding='utf8'):
            row=json.loads(line);vid=row['canonical_video_id'];d=row.get('config_download');scene=row['scene']
            binding_issues=[]
            if d:
                member=d['member']
                if member not in cache:
                    b=z.read(member);assert sha(b)==d['sha256'];cache[member]=json.loads(b)
                    if len(cache)>128:cache.pop(next(iter(cache)))
                c=cache[member]
            else:
                c={'objects':row.get('initial_objects',[]),'render':{}}
                proof=fallback_audit.get(vid,{})
                fh=sha(json.dumps([[f[0],'',f[-2],f[-1]] for f in row.get('parameter_facts',[])],ensure_ascii=True,sort_keys=True,separators=(',',':')).encode())
                if not (proof.get('source_video_and_parameters_consistent') and proof.get('video_sha256')==row['sha256'] and proof.get('audit_parameter_facts_sha256')==fh):
                    binding_issues.append('original_config_unresolved_registered_inputs_only')
            clock={}
            wrapped=c.get('physics',{})
            runtime=wrapped.get('runtime',{})
            if wrapped.get('source_config') and runtime.get('physics_dt') and runtime.get('steps_per_frame'):
                c=wrapped['source_config']
                clock['physical_dt_s']=runtime['physics_dt']*runtime['steps_per_frame']
            td=(row.get('current_render',{}).get('actual_execution_profile',{}).get('time_diagnostic') or c.get('time_diagnostic') or {})
            if not clock and td.get('sim_dt') and td.get('physics_steps_per_render_frame'):clock['physical_dt_s']=td['sim_dt']*td['physics_steps_per_render_frame']
            elif not clock and c.get('scene_overrides',{}).get('dt') and c.get('render',{}).get('physics_steps_per_render_frame'):
                clock['physical_dt_s']=c['scene_overrides']['dt']*c['render']['physics_steps_per_render_frame']
            elif not clock and c.get('physics',{}).get('outer_dt') and c.get('physics',{}).get('outer_steps_per_frame'):
                clock['physical_dt_s']=c['physics']['outer_dt']*c['physics']['outer_steps_per_frame']
            inp=safe_inputs(c)
            render_row=dict(row);render_row['parameter_facts']=list(row.get('parameter_facts',[]))
            primary=(c.get('experiment',{}).get('parameter') or {})
            primary_keys=[]
            if isinstance(primary,dict) and isinstance(primary.get('parameter_value'),(int,float)):
                k=primary.get('parameter_name','');v=primary['parameter_value']
                if k and not any(w in k.lower() for w in ['outcome','threshold','event','theta']):
                    unit=primary.get('parameter_unit')
                    if unit is None:unit='m/s' if 'speed' in k or k=='v_roll' else 'N' if 'force' in k else '' if 'friction' in k or 'ratio' in k else 'm' if k in ['gap','support_x'] else None
                    if unit is not None:
                        if not any(f[0]==k for f in render_row['parameter_facts']):render_row['parameter_facts'].append([k,v,unit])
                        primary_keys.append(k)
            # Cache is keyed by all text-driving inputs, never by scene or case ID alone.
            key=sha(json.dumps([inp,render_row.get('parameter_facts'),row.get('external_control_inputs'),clock,required(scene,row.get('parameter_facts',[]))+primary_keys],sort_keys=True).encode())
            if key not in textcache:
                textcache[key]=build(render_row,c,clock,required(scene,row.get('parameter_facts',[]))+primary_keys)
            r=dict(textcache[key]);r['issues']=list(r['issues'])+binding_issues
            if vid in conflicts:r['issues'].append('source_parameter_conflict_no_value_changed')
            r.update(video_id=vid,video_sha256=row['sha256'],download=row['download'],split=row.get('split'),
                     source_group_id=row.get('source_group_id'),prompt_version=VERSION,prompt_sha256=sha(r['prompt'].encode()),
                     source_config_sha256=d['sha256'] if d else None,
                     source_evidence_kind='raw_config_hash' if d else 'original_metadata_and_video_parameter_hash_crosscheck',
                     status='needs_review' if r['issues'] else 'candidate')
            prompts.write(json.dumps(r,ensure_ascii=False)+'\n');originals.write(line)
            metadata.write(json.dumps({'video_id':vid,'video_sha256':row['sha256'],'full_parameter_facts':row.get('parameter_facts',[]),
                                        'initial_inputs':inp,'registered_control_inputs':row.get('external_control_inputs'),
                                        'config_download':d,'split':row.get('split'),'source_group_id':row.get('source_group_id'),
                                        'old_prompt_variants':row.get('prompt_variants_en'),'old_prompt_hashes':row.get('prompt_variant_sha256'),
                                        'source_conflicts':conflicts.get(vid,[])},ensure_ascii=False)+'\n')
            stats['videos']+=1;stats[r['status']]+=1;scenes[row.get('quota_scene',scene)]+=1
            issues.update(r['issues']);examples.setdefault((row['engine'],scene),r)
            if stats['videos']%6000==0:print('written',stats['videos'],dict(stats),flush=True)
    assert stats['videos']==72000 and sha(src.read_bytes())==source_hash
    report={'version':VERSION,'source_catalog_sha256':source_hash,'catalog':dict(stats),'issues':dict(issues),'per_scene':dict(scenes),
            'core100':{'cases':len(coreout),'issues':dict(collections.Counter(x for r in coreout for x in r['issues']))},
            'published':False,'final_release':False,'media_modified':False,'split_modified':False,'old_prompts_retained':True}
    put('BUILD_REPORT.json',report);put('场景样例.json',list(examples.values()))
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
