"""Edit existing three prompts, with explicit backups and clause-level change records."""
from pathlib import Path
import collections
import functools
import copy
import gzip
import hashlib
import json
import math
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from physedit.compact_prompt import counts, sentence, MODEL_BUDGETS
from physedit.natural_short_prompt import controls, number, objects
from physedit.core100_rebalanced import load

counts=functools.lru_cache(maxsize=32768)(counts)

BASE=ROOT/'review/prompt_rewrite_release_20261101'
OUT=ROOT/'review/prompt_revision_20261101'
sha=lambda b:hashlib.sha256(b).hexdigest()

def wording(text):
    # Local wording edits only; preserve every numeric token verbatim.
    for old,new in [('Can 1 can 2 edge gap','Can 1-to-can 2 edge gap'),('Can 2 mug edge gap','Can 2-to-mug edge gap'),
                    ('Ramp release position','Book release coordinate along ramp'),
                    ('Nominal drive','Nominal drive setting'),('Driver initial speed command','Nominal drive setting')]:
        text=text.replace(old,new)
    return text

def revise(row,c,clock,required=(),extra=()):
    old=row['prompt_variants_en'];assert len(old)==3
    ctl,encoded,issues=controls(c,row.get('external_control_inputs'),clock,row.get('parameter_facts',[]))
    if not c.get('objects') and not c.get('dynamic_objects') and not (row.get('external_control_inputs') or {}).get('objects') and 'registered.one_time_velocity_and_spin_assignment' not in encoded:
        issues.append('initial_motion_not_fully_recovered')
    changed=[];variants=[];optional={};represented={}
    required=set(required)
    obs=objects(c)
    scheduled=any(k.startswith('runtime_forces.') or k.endswith('.motion') for k in encoded)
    for f in row.get('parameter_facts',[]):
        k,v,u=f[0],f[-2],f[-1]
        covered=k in encoded
        parent=k.rsplit('.',1)[0];motion=obs.get(parent,{}).get('motion',{}) or {}
        if parent+'.motion' in encoded:
            covered |= k.endswith(('.tip_start','.tip_end','.commanded_travel'))
        if k.endswith('.force_peak') and 'runtime_forces.'+parent in encoded:
            fs=[x for x in c.get('runtime_forces',[]) if x.get('target')==parent]
            covered |= bool(fs) and math.isclose(float(v),max(math.sqrt(sum(t*t for t in x['force_world'])) for x in fs),rel_tol=1e-12)
        if k=='driver_initial_speed_mps':
            covered |= any(key+'.initial_velocity' in encoded and math.isclose(float(v),math.sqrt(sum(t*t for t in (o.get('motion') or {}).get('initial_velocity',[]))),abs_tol=1e-12) for key,o in obs.items())
        if covered:represented[wording(sentence(k,v,u))]=k
    for f in row.get('parameter_facts',[]):
        k=f[0]
        if k in required:continue
        # Only non-key material/mass properties may move out of text for the length budget.
        if k.endswith(('.mass','.friction','.restitution')) and 'table' not in k:
            optional[wording(sentence(k,f[-2],f[-1]))]=k
            optional[wording(sentence(k,f[-2],f[-1])).replace(' friction ',' material friction ')]=k
    for text in old:
        parts=re.split(r'(?<=\.)\s+',text.strip());kept=[]
        for part in parts:
            clean=wording(part.removeprefix('Then '))
            if clean.startswith('tape roll speed ') and 't10_tape_roll.initial_speed' in encoded:
                clean=wording(sentence('t10_tape_roll.initial_speed',next(f[-2] for f in row['parameter_facts'] if f[0]=='t10_tape_roll.initial_speed'),'m/s'))
            if clean in represented:
                changed.append({'before':part,'after':None,'reason':'same_parameter_expressed_in_source_control','key':represented[clean]})
            elif not issues and ((scheduled and re.match(r'^(Off-screen|An off-screen|Active force frames|Dynamics start time|Then pull the support bar)',part)) or ('clock.initial_hold_duration' in encoded and part.startswith('Hold initial'))):
                changed.append({'before':part,'after':None,'reason':'replaced_by_source_bound_control_schedule'})
            elif any(k.endswith('.motion') for k in encoded) and re.search(r' commanded (start|end) time ',clean):
                changed.append({'before':part,'after':None,'reason':'replaced_by_source_controller_frame_clock'})
            elif any(k.endswith('.motion') for k in encoded) and not issues and (re.match(r'^From .*off-screen actuator',clean) or clean.startswith('With a fixed camera, ') and 'off-screen actuator' in clean or clean.startswith('Control is released at ')):
                if clean.startswith('With a fixed camera'):kept.append('With a fixed camera, continue the scene.')
                changed.append({'before':part,'after':None,'reason':'replaced_by_source_controller_frame_clock'})
            else:kept.append(clean)
        kept.extend(extra)
        kept.extend(ctl)
        # Remove identical whole clauses, not substring truncation.
        variants.append(list(dict.fromkeys(kept)))
    moved=[]
    def fits():
        return all(all(counts(' '.join(parts))[k]<=MODEL_BUDGETS[k] for k in MODEL_BUDGETS) for parts in variants)
    # All variants use the same retained information. Removal is explicitly registered.
    for clause,key in reversed(list(optional.items())):
        if fits():break
        if any(clause in p for p in variants):
            variants=[[s for s in p if s!=clause] for p in variants];moved.append(key)
            changed.append({'before':clause,'after':None,'reason':'nonkey_parameter_preserved_in_metadata_for_token_budget','key':key})
    new=[' '.join(p) for p in variants];tc=[counts(s) for s in new]
    if not fits():issues.append('over_budget_required_information_not_truncated')
    if any(re.search(r'\bwill (?:fall|collide|hit|topple)|NearAcc|PairAcc|theta_star|expected_chain',s,re.I) for s in new):issues.append('outcome_wording_requires_review')
    return {'prompt_variants_en':new,'prompt_en':new[0],'prompt_variant_sha256':[sha(s.encode()) for s in new],
            'token_counts':tc,'moved_to_metadata':moved,'source_control_clauses':ctl,'control_keys':encoded,
            'changes':changed,'issues':issues,'status':'needs_review' if issues else 'revised'}

def write(name,obj):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')

def main():
    OUT.mkdir(exist_ok=True)
    _,manifest,tasks,mapping=load()
    audited={r['clip_id']:r for r in json.loads((BASE/'core100/short_prompts.json').read_text(encoding='utf8'))}
    core=[];compare=[]
    write('backup/Core100_original.json',{'version':manifest['version'],'tasks':tasks})
    for task in tasks:
        a=audited[task['clip_id']];required=[];extra=[];conflicts=[]
        for reg in a.get('primary_input_registration',[]):
            if reg.get('registration_conflict'):conflicts.append(reg);continue
            if reg.get('source_field'):required.append(reg['source_field'])
            elif reg.get('key') in {f[0] for f in task['parameter_facts']}:required.append(reg['key'])
            elif 'friction' in reg.get('key',''):
                required.extend(f[0] for f in task['parameter_facts'] if 'friction' in f[0])
        row=revise(task,a['full_control_inputs'],a['resolved_control_clock'],required)
        # A critical input absent from the old text must not disappear merely
        # because editing is minimal. Use only the already source-bound registry.
        for reg in a.get('primary_input_registration',[]):
            if reg.get('registration_conflict'):continue
            value=reg.get('value',reg.get('source_config_value'));key=reg.get('key','')
            if not isinstance(value,(int,float)):continue
            values=[]
            for token in re.findall(r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:/\d+|[eE][-+]?\d+)?',row['prompt_en']):
                if '/' in token:
                    n,d=token.split('/');values.append(float(n)/float(d))
                else:values.append(float(token))
            if any(math.isclose(value,v,rel_tol=1e-12,abs_tol=1e-12) for v in values):continue
            unit='m/s' if key.endswith('_mps') or key=='book_drive_speed' else 'm' if key.endswith('_m') or key=='gap' else 'N' if key in ['impact_force','pull_force'] else ''
            title=key.removesuffix('_mps').removesuffix('_m').replace('_',' ')
            if key in ['driver_initial_speed_command_mps','book_drive_speed','impact_force','pull_force']:title+=' setting'
            extra.append(f'{title.capitalize()} {number(value)}'+(' '+unit if unit else '')+'.')
        if extra:
            row=revise(task,a['full_control_inputs'],a['resolved_control_clock'],required,extra)
            row['changes'].extend({'before':None,'after':s,'reason':'restore_source_bound_primary_input_missing_from_old_prompt'} for s in extra)
        row.update(clip_id=task['clip_id'],sample_id=task['sample_id'],reference=task['reference'],
                   original_prompt_variants_en=task['prompt_variants_en'],parameter_facts=task['parameter_facts'],
                   full_control_inputs=a['full_control_inputs'],resolved_clock=a['resolved_control_clock'],
                   parameter_conflicts=conflicts,primary_input_registration=a.get('primary_input_registration',[]),roster=manifest['version'])
        if conflicts:row['issues'].append('parameter_registration_conflict_original_values_preserved');row['status']='needs_review'
        core.append(row)
        text=f"## {task['clip_id']}\n\n"
        for i,(before,after) in enumerate(zip(task['prompt_variants_en'],row['prompt_variants_en']),1):
            text+=f"变体{i}原版：\n```text\n{before}\n```\n\n变体{i}修订版：\n```text\n{after}\n```\n\n"
        compare.append(text)
    write('Core100_revised.json',core)
    (OUT/'Core100完整对照.md').write_text('\n'.join(compare),encoding='utf8')
    write('CORE100_REPORT.json',{'cases':100,'variants':300,'roster':manifest['version'],'status':dict(collections.Counter(r['status'] for r in core)),
                               'issues':dict(collections.Counter(i for r in core for i in r['issues'])),'original_preserved':True})
    print('Core100',collections.Counter(r['status'] for r in core),flush=True)
    if '--core-only' in sys.argv:return
    src=BASE/'source/videos.jsonl.gz';z=zipfile.ZipFile(BASE/'source/configs.zip');cache={};stats=collections.Counter();issues=collections.Counter()
    bad={r['video_id']:r['conflicts'] for r in json.loads((BASE/'audit/catalog_conflicts.json').read_text(encoding='utf8'))}
    source_hash=sha(src.read_bytes())
    with gzip.open(OUT/'revised_72000.jsonl.gz','wt',encoding='utf8',compresslevel=1) as dst,gzip.open(OUT/'backup/original_72000.jsonl.gz','wt',encoding='utf8',compresslevel=1) as backup:
        for line in gzip.open(src,'rt',encoding='utf8'):
            r=json.loads(line);d=r.get('config_download');clock={}
            if d:
                member=d['member']
                if member not in cache:
                    b=z.read(member);assert sha(b)==d['sha256'];cache[member]=json.loads(b)
                    if len(cache)>128:cache.pop(next(iter(cache)))
                c=cache[member]
            else:c={'objects':r.get('initial_objects',[]),'render':{}}
            if c.get('source_physics_objects'):
                meta=c['metadata'];c={'objects':c['source_physics_objects'],'render':{k:meta[k] for k in ['fps','pre_static_frames'] if k in meta}}
                clock['physical_dt_s']=meta['physics_dt']*meta['steps_per_frame']
            wrapper=c.get('physics',{});runtime=wrapper.get('runtime',{})
            if wrapper.get('source_config') and runtime.get('physics_dt'):
                c=wrapper['source_config'];clock['physical_dt_s']=runtime['physics_dt']*runtime['steps_per_frame']
            if not clock:
                if c.get('scene_overrides',{}).get('dt') and c.get('render',{}).get('physics_steps_per_render_frame'):clock['physical_dt_s']=c['scene_overrides']['dt']*c['render']['physics_steps_per_render_frame']
                elif c.get('physics',{}).get('outer_dt'):clock['physical_dt_s']=c['physics']['outer_dt']*c['physics']['outer_steps_per_frame']
            result=revise(r,c,clock,r.get('required_parameter_keys') or [])
            if r['canonical_video_id'] in bad:
                result['issues'].append('parameter_conflict_original_values_preserved');result['status']='needs_review'
                # A conflicting velocity must never be introduced alongside the old one.
                result['prompt_variants_en']=list(r['prompt_variants_en']);result['prompt_en']=r['prompt_en']
                result['prompt_variant_sha256']=[sha(s.encode()) for s in result['prompt_variants_en']]
                result['token_counts']=[counts(s) for s in result['prompt_variants_en']]
                result['changes']=[];result['moved_to_metadata']=[];result['source_control_clauses']=[]
            result.update(video_id=r['canonical_video_id'],video_sha256=r['sha256'],download=r['download'],split=r.get('split'),source_group_id=r.get('source_group_id'),
                          parameter_facts=r.get('parameter_facts',[]),external_control_inputs=r.get('external_control_inputs'),config_download=d,
                          original_prompt_variant_sha256=[sha(s.encode()) for s in r['prompt_variants_en']],parameter_conflicts=bad.get(r['canonical_video_id'],[]))
            dst.write(json.dumps(result,ensure_ascii=False)+'\n');backup.write(line)
            stats['videos']+=1;stats[result['status']]+=1;issues.update(result['issues'])
            if stats['videos']%12000==0:print(dict(stats),flush=True)
    assert stats['videos']==72000 and sha(src.read_bytes())==source_hash
    write('REPORT.json',{'videos':72000,'variants':216000,'status':dict(stats),'issues':dict(issues),'source_catalog_sha256':source_hash,
                        'published':False,'video_and_split_modified':False,'all_original_prompts_backed_up':True})
    print('DONE',dict(stats),dict(issues),flush=True)

if __name__=='__main__':main()
