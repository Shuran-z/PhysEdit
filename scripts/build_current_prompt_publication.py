"""Rebase audited prompts onto the live inventory, preserving all live media/splits."""
from pathlib import Path
import collections,copy,functools,gzip,hashlib,json,re,sqlite3,sys,zlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import full_prompt_config_audit as audit
from scripts.preflight_current_prompt_upload import Configs,DB,CURRENT,BASE
from scripts.repair_and_verify_all_prompts import source_controls,pieces,NUM,fact_patterns,match_fact,merge_friction,primary_clause,supplemental_clause,texts_hash
from scripts.repair_prompt_fact_units import typed_unit
from scripts.revise_existing_prompts import wording
from scripts.continue_prompt_revision import normalize
from physedit.compact_prompt import sentence,counts,MODEL_BUDGETS,label
from physedit.natural_short_prompt import name as actor_name
from physedit.prompt_contract import parameter_facts_sha
OUT=BASE/'rebased';OUT.mkdir(exist_ok=True)

def current_context(row,raw):
    c,obs,actual,flat=audit.context(raw)
    render=row.get('current_render') or {};download=row.get('config_download') or {}
    executed=bool(render.get('executed_request_sha256')==download.get('sha256') and download.get('sha256'))
    if executed:
        # Resampling modifies the executed adapter inputs. An inherited r3 snapshot
        # is historical when it disagrees with that hash-bound executed request.
        direct={o.get('spec',o)['name']:o.get('spec',o) for o in c.get('objects',c.get('dynamic_objects',[]))}
        if direct:
            obs=copy.deepcopy(direct)
            policy=raw.get('physics',{}).get('runtime',{}).get('material_policy',{})
            if isinstance(policy.get('restitution'),(int,float)):
                obs={k:{**o,'restitution':policy['restitution']} for k,o in obs.items()}
            actual={**actual,'bodies':list(obs.values()),'external_forces':copy.deepcopy(c.get('runtime_forces',[]))}
        profile=render.get('actual_execution_profile') or {};time=profile.get('time_diagnostic') or profile
        dt=time.get('sim_dt',time.get('physics_dt'));steps=time.get('physics_steps_per_render_frame',time.get('steps_per_frame'))
        if dt and steps:
            c=copy.deepcopy(c);c.setdefault('scene_overrides',{})['dt']=dt;c.setdefault('render',{})['physics_steps_per_render_frame']=steps
            if 'pre_static_frames' in time:c['render']['pre_static_frames']=time['pre_static_frames']
            if 'fps' in time:c['render']['fps']=time['fps']
    return c,obs,actual,flat

def resolve_current(key,value,raw,ctx,row):
    if key in ['book_initial_speed','book_initial_speed_mps']:
        for name in ['t03v5_impulsed_book','t15v4_driver_book','t08_lower_impactor_book','t20_book']:
            if name in ctx[1] and 'initial_velocity' in ctx[1][name].get('motion',{}):
                return audit.norm(ctx[1][name]['motion']['initial_velocity']),'executed_object.'+name+'.motion.initial_velocity.norm'
    return audit.resolve(key,value,raw,ctx,row)

def optional(key,required):
    return key not in required and (key.endswith(('.mass','.restitution','_mass_kg')) or key in ['marker_mass','eraser_mass','ball_mass','gate_mass'])

def covered_by_controller(key,value,ctx,keys):
    used=set(keys)
    if '.' in key:
        who,field=key.rsplit('.',1);o=ctx[1].get(who,{})
        if field in ['initial_velocity','initial_angular_velocity'] and who+'.'+field in used:
            return audit.equal(value,o.get('motion',{}).get(field))
        if field=='initial_speed' and who+'.initial_velocity' in used:
            return audit.equal(value,audit.norm(o.get('motion',{}).get('initial_velocity',[0,0,0])))
    if key in used:return True
    if '.' not in key and ('initial_speed' in key or '_speed_mps' in key):
        title=label(key)
        for suffix in [' initial speed mps',' initial speed',' speed mps',' speed']:
            if title.endswith(suffix):title=title[:-len(suffix)];break
        candidates=[]
        for who,o in ctx[1].items():
            if who+'.initial_velocity' not in used:continue
            aliases=[label(who),actor_name(who)]
            if not any(a==title or a.startswith(title+' ') for a in aliases):continue
            velocity=o.get('motion',{}).get('initial_velocity')
            if velocity is not None and audit.equal(audit.norm(velocity),value):candidates.append(who)
        return len(candidates)==1
    return False

def main():
    db=sqlite3.connect(DB);cfg=Configs();stats=collections.Counter();pending=[];pool={};deltas=[]
    with gzip.open(CURRENT/'videos.jsonl.gz','rt',encoding='utf8') as src,gzip.open(OUT/'videos.jsonl.gz','wt',encoding='utf8',compresslevel=1) as dst,gzip.open(OUT/'train_final.jsonl.gz','wt',encoding='utf8',compresslevel=1) as train:
        for line in src:
            row=json.loads(line);original=copy.deepcopy(row);vid=row['canonical_video_id'];d=row.get('config_download') or {}
            indexed=db.execute('SELECT sha,config_sha,payload FROM patch WHERE id=?',(vid,)).fetchone()
            old=json.loads(zlib.decompress(indexed[2])) if indexed else None
            same=bool(indexed and indexed[1]==d.get('sha256'))
            if same and indexed[0]!=row['sha256']:
                encoding=(row.get('current_render') or {}).get('encoding_compatibility') or {}
                assert encoding.get('source_sha256')==indexed[0] and encoding.get('sha256')==row['sha256']
                assert encoding.get('physical_inputs_and_trajectories_unchanged') and encoding.get('timing_resolution_and_frame_count_preserved')
                stats['encoding_only_rows_preserved']+=1
            if d:
                raw,_=cfg.get(d['path'],d['member'],d['sha256']);ctx=current_context(row,raw);stats['config_rows']+=1
            else:
                h=audit.HEADERS[vid];assert same and h['video_sha256']==indexed[0]
                raw=h['header'];ctx=current_context(row,raw);stats['original_metadata_rows']+=1
            # Current facts remain the base. Preserve additional audited facts only
            # when the exact configuration identity is unchanged.
            if same:
                keys={f[0] for f in row['parameter_facts']}
                row['parameter_facts']+=copy.deepcopy([f for f in old['parameter_facts'] if f[0] not in keys])
            changes=[];issues=[]
            for f in row['parameter_facts']:
                value,path=resolve_current(f[0],f[-2],raw,ctx,row)
                if value is None:issues.append({'kind':'unresolved_fact','key':f[0],'reason':path});continue
                if not audit.equal(f[-2],value):changes.append({'key':f[0],'old':f[-2],'new':value,'source':path});f[-2]=value;stats['numeric_fields_corrected']+=1
                unit=typed_unit(f[0],f[-2],f[-1])
                if unit!=f[-1]:stats['unit_fields_corrected']+=1;f[-1]=unit
                stats['field_checks']+=1
            if row['engine']=='genesis' and row['scene']=='T19' and row['sha256'] not in audit.T19 and indexed:
                audit.T19[row['sha256']]=audit.T19[indexed[0]]
            n,c,clock=source_controls(row,raw,ctx);control=n['source_control_clauses']
            issues.extend({'kind':'controller_issue','reason':i} for i in n['issues'])
            facts={f[0]:f for f in row['parameter_facts']};required=set(row.get('required_parameter_keys') or row.get('required_prompt_keys') or [])
            for key in (row.get('current_render') or {}).get('changed_inputs',{}):
                if key in facts:required.add(key)
            if same:
                templates=old['prompt_variants_en'];oldcontrol=old['prompt_revision']['source_control_clauses']
                row['prompt_revision']=copy.deepcopy(old['prompt_revision'])
            else:
                selected=list(dict.fromkeys(list(row.get('selected_parameter_keys',[]))+list(required)))
                body=[normalize(wording(sentence(k,facts[k][-2],facts[k][-1]))) for k in selected if k in facts]
                templates=[prefix+' '+' '.join(body) for prefix in ['Fixed camera.','Keep camera fixed.','Camera stays fixed.']];oldcontrol=[]
                row['prompt_revision']={}
                stats['current_config_rows_recompiled']+=1
            pats=fact_patterns(row['parameter_facts']);new=[];body_keys=set();supp=[]
            for index,text in enumerate(templates):
                for cl in sorted(oldcontrol,key=len,reverse=True):text=text.replace(cl,' ')
                ps=[]
                for cl in pieces(text):
                    if not NUM.search(cl):ps.append(cl);continue
                    m=match_fact(cl,pats)
                    if m:
                        key,actual,value,prefix,suffix=m
                        if not audit.equal(actual,value):cl=normalize(wording(sentence(key,value,facts[key][-1])))
                        body_keys.add(key)
                    elif merge_friction(cl,row['parameter_facts']):body_keys.update(merge_friction(cl,row['parameter_facts']))
                    elif primary_clause(cl,row,raw):pass
                    else:
                        extra=supplemental_clause(cl,row,c,ctx)
                        if extra:cl=extra['replacement'];supp.append(extra)
                        else:issues.append({'kind':'unmapped_clause','variant':index+1,'clause':cl})
                    ps.append(cl)
                ps=list(dict.fromkeys(ps));ps+=control;new.append(' '.join(ps))
            if len(set(new))<3:
                new=[prefix+' '+text.split('. ',1)[1] for prefix,text in zip(['Fixed camera.','Keep camera fixed.','Camera stays fixed.'],new)]
            if any(any(counts(t)[m]>cap for m,cap in MODEL_BUDGETS.items()) for t in new):
                new=[prefix+' '+text.split('. ',1)[1] if 'camera' in text.split('. ',1)[0].lower() else text for prefix,text in zip(['Fixed camera.','Keep camera fixed.','Camera stays fixed.'],new)]
            moved=[]
            for key in reversed(list(facts)):
                if all(all(counts(t)[m]<=cap for m,cap in MODEL_BUDGETS.items()) for t in new):break
                if not optional(key,required) or key not in body_keys:continue
                texts=[];removed=False
                for text in new:
                    ps=[]
                    for cl in pieces(text):
                        m=match_fact(cl,pats)
                        if m and m[0]==key:removed=True
                        else:ps.append(cl)
                    texts.append(' '.join(ps))
                if removed:new=texts;body_keys.discard(key);moved.append(key)
            for index,text in enumerate(new):
                if any(counts(text)[m]>cap for m,cap in MODEL_BUDGETS.items()):issues.append({'kind':'token_budget','variant':index+1,'counts':counts(text)})
                assert all(cl in text for cl in control),(vid,'control_missing')
            row['prompt_variants_en']=new;row['prompt_en']=new[0];row['prompt_variant_sha256']=texts_hash(new);row['prompt_sha256']=row['prompt_variant_sha256'][0]
            row['prompt_variant_token_counts']=[counts(t) for t in new];row['prompt_token_counts']=counts(new[0]);row['parameter_facts_sha256']=parameter_facts_sha(row['parameter_facts'])
            row['selected_parameter_keys']=sorted(body_keys|({f[0] for f in row['parameter_facts']} & set(n.get('control_keys',[]))))
            row['omitted_parameter_keys']=sorted(set(facts)-set(row['selected_parameter_keys']))
            rev=row['prompt_revision'];rev.update(version='numeric-audit-current-inventory-20261102',source_control_clauses=control,status='needs_review' if issues else 'revised',issues=[i['kind'] for i in issues],moved_to_metadata=sorted(set(rev.get('moved_to_metadata',[]))|set(moved)))
            if n.get('resolved_controller_metadata'):rev['resolved_controller_metadata']=n['resolved_controller_metadata']
            if old and same and old['prompt_revision'].get('primary_input_metadata'):rev['primary_input_metadata']=copy.deepcopy(old['prompt_revision']['primary_input_metadata'])
            registered=copy.deepcopy(row.get('external_control_inputs') or {})
            if 'external_forces' in ctx[2]:registered['runtime_forces']=copy.deepcopy(ctx[2]['external_forces'])
            for obj in registered.get('objects',[]):
                actual=ctx[1].get(obj['name'])
                if actual:
                    for key in list(obj):
                        if key!='name' and key in actual:obj[key]=copy.deepcopy(actual[key])
            row['external_control_inputs']=registered;row['external_control_disclosure']={'kinds':n.get('control_keys',[]),'disclosure':' '.join(control)}
            row['prompt_policy']='config-runtime-numeric-audited-20261102';row['token_budget']=MODEL_BUDGETS['ltx']
            if 'video_sha256' in row:row['video_sha256']=row['sha256']
            row['full_numeric_audit']={'status':'needs_review' if issues else 'verified','source':{'type':'executed_config_or_runtime_overrides' if d else 'original_metadata','sha256':d.get('sha256') or audit.HEADERS[vid]['metadata_artifact_sha256']},'field_checks':len(facts),'issues':issues,'publication_base':'096d3d1fe9d78c57d2fe80de3636cbac04950e65'}
            for key in ['sha256','download','split','source_group_id','canonical_video_id','quality_admission_status','physical_qa','current_render']:
                assert row.get(key)==original.get(key),(vid,key)
            if changes:deltas.append({'video_id':vid,'changes':changes})
            if issues:pending.append({'video_id':vid,'issues':issues,'prompt':new[0]});stats['needs_review']+=1
            else:stats['verified']+=1
            encoded=json.dumps(row,ensure_ascii=False)+'\n';dst.write(encoded)
            if row['split']=='train_final':train.write(encoded);stats['training_rows']+=1
            stats['videos']+=1;stats['variants']+=3
            if stats['videos']%6000==0:print(json.dumps(dict(stats)),flush=True)
    assert stats['videos']==72000 and stats['training_rows']==45165
    (OUT/'PENDING.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'NUMERIC_CHANGES.json').write_text(json.dumps(deltas,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'BUILD_REPORT.json').write_text(json.dumps(dict(stats),indent=2),encoding='utf8');print(json.dumps(dict(stats)))

if __name__=='__main__':main()
