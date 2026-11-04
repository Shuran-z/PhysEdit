"""Config-backed numeric clause audit and additive repair of all 72000 rows."""
from pathlib import Path
import collections,copy,functools,gzip,hashlib,json,math,re,sys,zipfile
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import full_prompt_config_audit as audit
from physedit.compact_prompt import counts,sentence,MODEL_BUDGETS
from physedit.prompt_contract import parameter_facts_sha
from scripts.revise_existing_prompts import revise,wording
from scripts.continue_prompt_revision import improve,normalize,t11_primary_prompt

SOURCE=audit.SOURCE;OUT=audit.OUT/'repaired';OUT.mkdir(exist_ok=True)
NUM=re.compile(r'(?<![\w])[-+]?\d+(?:\.\d+)?(?:/\d+|[eE][-+]?\d+)?')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def texts_hash(ss):return [hashlib.sha256(s.encode()).hexdigest() for s in ss]
def pieces(text):return [s.strip() for s in re.split(r'(?<=\.)\s+',text.strip()) if s.strip()]
def numeric_value(text):
    text=text.strip()
    if text.startswith('('):text='['+text[1:-1]+']'
    try:return json.loads(text)
    except (ValueError,TypeError):
        if re.fullmatch(r'[-+]?\d+/\d+',text):
            a,b=text.split('/');return float(a)/float(b)
        return None

def force_number(value):
    text=format(value,'.15g');fraction=Fraction(value).limit_denominator(10000)
    if abs(float(fraction)-value)<=8*math.ulp(float(value)) and len(str(fraction))+2<len(text):return str(fraction)
    return text

def clock_and_config(raw,ctx):
    c,obs,actual,_=ctx;c=copy.deepcopy(c);runtime=raw.get('physics',{}).get('runtime',{});meta=c.get('metadata',{})
    c['objects']=list(copy.deepcopy(obs).values())
    if 'external_forces' in actual:c['runtime_forces']=copy.deepcopy(actual['external_forces'])
    render=c.setdefault('render',{})
    for key in ['fps','pre_static_frames']:
        if key in runtime:render[key]=runtime[key]
        elif key in meta:render[key]=meta[key]
    dt=runtime.get('physics_dt',meta.get('physics_dt'))
    steps=runtime.get('steps_per_frame',meta.get('steps_per_frame'))
    if not dt or not steps:
        dt=c.get('scene_overrides',{}).get('dt',c.get('physics',{}).get('outer_dt'))
        steps=render.get('physics_steps_per_render_frame',c.get('scene_overrides',{}).get('physics_steps_per_render_frame',c.get('physics',{}).get('outer_steps_per_frame')))
    clock={'physical_dt_s':dt*steps} if dt and steps else {}
    return c,clock

def source_controls(row,raw,ctx):
    c,clock=clock_and_config(raw,ctx);r=copy.deepcopy(row)
    if 'external_forces' in ctx[2]:
        r['external_control_inputs']=copy.deepcopy(row.get('external_control_inputs') or {})
        r['external_control_inputs']['runtime_forces']=c['runtime_forces']
    n=revise({**r,'prompt_variants_en':['Fixed camera.']*3},c,clock)
    n.update(video_id=row['canonical_video_id'],parameter_conflicts=[])
    n=improve(r,n,c)
    if row['scene']=='T11' and row['engine']=='genesis':n=t11_primary_prompt(r,n,c)
    if row['scene']=='T11' and row['engine']=='genesis' and c.get('runtime_forces') and c['runtime_forces'][0].get('first_contact_pair'):
        f=c['runtime_forces'][0];assert f['force_world'][1:]==[0.,0.] and f['force_world_after_first_contact'][1:]==[0.,0.]
        assert f['force_world_after_contact'][1:]==[0.,0.]
        pre=c['render'].get('pre_static_frames',0);fps=c['render']['fps'];period=clock['physical_dt_s']
        after=f['force_world_after_contact'][0];delay=f['stop_after_contact_delay_frames']
        stop='stop immediately' if after==0 and delay==0 else f'{force_number(after)} N for {delay} frames, then stop'
        ctl=f"Hold {pre/fps:g} s. Eraser rests. +X force: {force_number(f['force_world'][0])} N; if eraser contacts pencil case, {force_number(f['force_world_after_first_contact'][0])} N; if pencil case contacts glasses case, {stop}. Frames {f['frame_start']}-{f['frame_end']} at {1/period:.15g} Hz."
        n['source_control_clauses']=[ctl];n['issues']=[]
    # Isaac r3 is a fixed-duration push, not the inherited contact-feedback recipe.
    if row['scene']=='T11' and row['engine']=='isaac' and ctx[2].get('external_forces'):
        forces=ctx[2]['external_forces'];assert len(forces)==1
        f=forces[0];assert f['force_world'][1:]==[0.,0.]
        pre=c['render'].get('pre_static_frames',0);fps=c['render']['fps'];period=clock['physical_dt_s']
        ctl=f"Hold {pre/fps:g} s. Eraser starts at rest. Apply +X force {f['force_world'][0]:.15g} N to eraser during frames {f['frame_start']}-{f['frame_end']} at {1/period:.15g} Hz."
        n['source_control_clauses']=[ctl];n['issues']=[]
        n['resolved_controller_metadata']={'authority':'actual_physical_parameters.external_forces','feedback':'none','frame_start':f['frame_start'],'frame_end':f['frame_end'],'rate_hz':1/period}
    return n,c,clock

def fact_patterns(facts):
    pats=[]
    for f in facts:
        key,value,unit=f[0],f[-2],f[-1]
        raw=sentence(key,'__VALUE__',unit)
        for template in set([raw,wording(raw),normalize(wording(raw)),wording(raw).replace(' friction ',' material friction ')]):
            prefix,suffix=template.split('"__VALUE__"')
            pats.append((re.compile('^'+re.escape(prefix)+r'(?P<value>.+?)'+re.escape(suffix)+'$',re.I),key,value,unit,prefix,suffix))
    return pats

def match_fact(clause,pats):
    matches=[]
    for pat,key,value,unit,prefix,suffix in pats:
        m=pat.fullmatch(clause)
        if m:
            parsed=numeric_value(m['value'])
            if parsed is None:continue
            expected=value
            if key=='gravity' and isinstance(value,list) and value[:2]==[0,0]:expected=abs(value[2])
            if isinstance(value,list) and value[:2]==[0,0] and isinstance(parsed,(int,float)) and prefix.strip().lower()=='gravity':expected=abs(value[2])
            matches.append((key,parsed,expected,prefix,suffix))
    if not matches:return None
    assert all(audit.equal(matches[0][2],r[2]) for r in matches),('ambiguous_fact_label',clause,matches)
    return matches[0]

def merge_friction(clause,facts):
    m=re.fullmatch(r'Books ([\d, ]+) friction (.+)\.',clause)
    if not m:return None
    ids=[s.strip() for s in m[1].split(',')];value=numeric_value(m[2]);keys=[]
    for num in ids:
        found=[f for f in facts if f[0].endswith('book_'+num+'.friction')]
        if len(found)!=1 or not audit.equal(found[0][-2],value):return None
        keys.append(found[0][0])
    return keys

def primary_clause(clause,row,raw):
    selected=row.get('prompt_revision',{}).get('primary_input_metadata',{}).get('selected',{})
    labels={'driver_initial_speed_mps':('Drive setting','m/s'),'relay_case_gap_m':('Relay-case gap','m'),'case_edge_margin_m':('Case edge margin','m'),'relay_block_mass_kg':('Relay mass','kg'),'case_friction_coefficient':('Case friction','')}
    if not selected:return None
    params=raw.get('experiment',{}).get('parameter',{})
    expected=params.get('parameter_value')
    current={params.get('parameter_name'):expected} if params.get('parameter_name')!='joint_global_configuration' else expected
    if not isinstance(current,dict):return None
    wanted=[]
    for k in selected:
        if k not in current or k not in labels:return None
        lab,u=labels[k];wanted.append(lab+' '+str(current[k])+(' '+u if u else ''))
    # Numeric values checked by label and unit, not by occurrence elsewhere in text.
    fragments=clause.rstrip('.').split('; ')
    if len(fragments)!=len(wanted):return None
    for text,k in zip(fragments,selected):
        lab,u=labels[k];m=re.fullmatch(re.escape(lab)+r' (.+?)'+(' '+re.escape(u) if u else ''),text)
        if not m or not audit.equal(numeric_value(m[1]),current[k]):return None
    return list(selected)

def supplemental_clause(clause,row,c,ctx):
    m=re.fullmatch(r'Book (\d+) of (\d+) stays kinematic\.',clause)
    canonical=re.fullmatch(r'Book (\d+) stays kinematic; the stack has (\d+) books\.',clause)
    short=re.fullmatch(r'Book (\d+) kinematic; (\d+) books\.',clause)
    canonical=canonical or short
    if m or canonical:
        exp=c.get('experiment',{});who=exp.get('extracted_book_name');o=ctx[1].get(who,{})
        assert row['scene']=='T18' and o.get('fixed') and o.get('motion',{}).get('type')=='scripted_keyframes'
        if m:assert int(m[1])==exp['extraction_position_one_based'] and int(m[2])==exp['book_count']
        else:assert int(canonical[1])==exp['extraction_index_zero_based'] and int(canonical[2])==exp['book_count']
        replacement=f"Book {exp['extraction_index_zero_based']:02d} kinematic; {exp['book_count']} books."
        return {'kind':'kinematic_object_identity','replacement':replacement,'source':'experiment.extraction_index_zero_based/book_count and object.fixed/motion'}
    m=re.fullmatch(r'(\d+) static frames; ([\d.]+) fps\.',clause)
    if m:
        assert int(m[1])==c['render']['pre_static_frames'] and float(m[2])==c['render']['fps']
        return {'kind':'static_frames_and_media_rate','replacement':clause,'source':'render.pre_static_frames/fps'}
    return None

def main():
    assert len(audit.HEADERS)==2640,'original metadata headers must be available'
    z=zipfile.ZipFile(audit.ARCHIVE);stats=collections.Counter();pending=[];changed=[];residual=collections.Counter();residual_examples={};all_ids=set()
    @functools.lru_cache(maxsize=512)
    def load(member,h):
        b=z.read(member);assert hashlib.sha256(b).hexdigest()==h;raw=json.loads(b);return raw,audit.context(raw)
    resume='--resume' in sys.argv and (OUT/'videos.jsonl.gz').exists()
    if resume:
        for line in gzip.open(OUT/'videos.jsonl.gz','rt',encoding='utf8'):
            r=json.loads(line);all_ids.add(r['canonical_video_id']);a=r['full_numeric_audit'];stats['videos']+=1;stats['variants']+=3
            stats['fields_checked']+=a['field_checks'];stats['numeric_clause_checks']+=a['numeric_clause_checks']
            if r['split']=='train_final':stats['train_final_candidates']+=1
            if a['issues']:
                pending.append({'video_id':r['canonical_video_id'],'issues':a['issues']});stats['needs_review']+=1
                for issue in a['issues']:
                    if issue['kind']=='unmapped_numeric_clause':residual[issue['clause']]+=1;residual_examples.setdefault(issue['clause'],r['canonical_video_id'])
            else:stats['verified']+=1
        for line in gzip.open(OUT/'CHANGES.jsonl.gz','rt',encoding='utf8'):
            r=json.loads(line);stats['changed_rows']+=1;stats['field_corrections']+=len(r['field_changes'])
        print(json.dumps({'resumed_completed_rows':len(all_ids)}),flush=True)
    handles={name:gzip.open(OUT/name,'at' if resume else 'wt',encoding='utf8',compresslevel=1) for name in ['videos.jsonl.gz','train_final_candidates.jsonl.gz','AUDIT_LEDGER.jsonl.gz','CHANGES.jsonl.gz']}
    try:
        for line in gzip.open(SOURCE,'rt',encoding='utf8'):
            row=json.loads(line);vid=row['canonical_video_id']
            if resume and vid in all_ids:continue
            original=copy.deepcopy(row);assert vid not in all_ids;all_ids.add(vid)
            d=row.get('config_download')
            if d:raw,ctx=load(d['member'],d['sha256']);proof={'type':'hash_verified_config','sha256':d['sha256']}
            else:
                h=audit.HEADERS[vid];assert h['video_sha256']==row['sha256'];raw=h['header'];ctx=audit.context(raw)
                proof={'type':'hash_verified_original_metadata','sha256':h['metadata_artifact_sha256']}
            field_records=[];issues=[];fact_changes=[]
            for fact in row['parameter_facts']:
                value,path=audit.resolve(fact[0],fact[-2],raw,ctx,row)
                if value is None:issues.append({'kind':'unresolved_parameter','key':fact[0],'reason':path})
                else:
                    field_records.append({'key':fact[0],'value':value,'source_path':path})
                    if not audit.equal(value,fact[-2]):fact_changes.append({'key':fact[0],'old':fact[-2],'new':value});fact[-2]=value
            n,c,clock=source_controls(row,raw,ctx)
            issues.extend({'kind':'unresolved_controller','reason':s} for s in n['issues'])
            old_ctrl=row.get('prompt_revision',{}).get('source_control_clauses',[])
            new_ctrl=n['source_control_clauses'];pats=fact_patterns(row['parameter_facts']);newtexts=[];numeric_checks=[];body_keys=set();moved=[]
            for variant,text in enumerate(row['prompt_variants_en']):
                # Strip registered old controllers before installing freshly derived ones.
                for clause in sorted(old_ctrl,key=len,reverse=True):text=text.replace(clause,' ')
                parts=[]
                for clause in pieces(text):
                    if clause.startswith('After ') and 'static pre-roll' in clause and any(s.startswith('Hold') for s in new_ctrl):continue
                    if not NUM.search(clause):parts.append(clause);continue
                    match=match_fact(clause,pats)
                    if match:
                        key,actual,expected,prefix,suffix=match
                        if not audit.equal(actual,expected):
                            v=expected
                            if isinstance(v,(float,int)) and not isinstance(v,bool):vstr=format(v,'.15g')
                            else:vstr=json.dumps(v,separators=(',',':'))
                            clause=prefix+vstr+suffix
                        body_keys.add(key);numeric_checks.append({'variant':variant+1,'key':key,'source':'fact_clause'});parts.append(clause)
                    elif merge_friction(clause,row['parameter_facts']):
                        keys=merge_friction(clause,row['parameter_facts']);body_keys.update(keys);parts.append(clause)
                        numeric_checks.extend({'variant':variant+1,'key':k,'source':'merged_friction_clause'} for k in keys)
                    elif primary_clause(clause,row,raw):
                        parts.append(clause);numeric_checks.extend({'variant':variant+1,'key':k,'source':'config_primary_setting'} for k in primary_clause(clause,row,raw))
                    else:
                        issues.append({'kind':'unmapped_numeric_clause','variant':variant+1,'clause':clause});parts.append(clause)
                        residual[clause]+=1;residual_examples.setdefault(clause,vid)
                # Exact duplicate facts/controls consume budget and carry no extra input.
                parts=list(dict.fromkeys(parts));parts.extend(new_ctrl)
                newtexts.append(' '.join(parts))
            if len(set(newtexts))<3:
                for i,text in enumerate(newtexts):
                    first,tail=text.split('. ',1);assert 'camera' in first.lower()
                    newtexts[i]=['Fixed camera.','Keep camera fixed.','Camera stays fixed.'][i]+' '+tail
            # Only non-intervention material/mass facts may move to metadata for length.
            required=set(row.get('required_parameter_keys') or [])
            primary=c.get('experiment',{}).get('parameter',{});primaryname=primary.get('parameter_name','') if isinstance(primary,dict) else ''
            if any(any(counts(t)[m]>v for m,v in MODEL_BUDGETS.items()) for t in newtexts):
                for i,t in enumerate(newtexts):
                    first,tail=t.split('. ',1)
                    if 'camera' in first.lower():newtexts[i]=['Fixed camera.','Keep camera fixed.','Camera stays fixed.'][i]+' '+tail
            for f in reversed(row['parameter_facts']):
                if all(all(counts(t)[m]<=v for m,v in MODEL_BUDGETS.items()) for t in newtexts):break
                key=f[0]
                if key in required or not key.endswith(('.mass','.friction','.restitution')) or any(x in primaryname for x in ['mass','friction','restitution']):continue
                if key not in body_keys:continue
                removed=False;nexttexts=[]
                for text in newtexts:
                    ps=[]
                    for cl in pieces(text):
                        match=match_fact(cl,pats)
                        if match and match[0]==key:removed=True
                        else:ps.append(cl)
                    nexttexts.append(' '.join(ps))
                if removed:newtexts=nexttexts;moved.append(key);body_keys.discard(key)
            for i,text in enumerate(newtexts):
                if any(counts(text)[m]>v for m,v in MODEL_BUDGETS.items()):issues.append({'kind':'over_token_budget','variant':i+1,'counts':counts(text)})
                assert all(cl in text for cl in new_ctrl),(vid,'controller_lost')
            row['prompt_variants_en']=newtexts;row['prompt_en']=newtexts[0];row['prompt_variant_sha256']=texts_hash(newtexts)
            row['prompt_sha256']=row['prompt_variant_sha256'][0];row['prompt_variant_token_counts']=[counts(t) for t in newtexts];row['prompt_token_counts']=counts(newtexts[0])
            row['parameter_facts_sha256']=parameter_facts_sha(row['parameter_facts'])
            if 'video_sha256' in row:row['video_sha256']=row['sha256']
            rev=row.setdefault('prompt_revision',{});rev['source_control_clauses']=new_ctrl
            rev['moved_to_metadata']=sorted(set(rev.get('moved_to_metadata',[]))|set(moved));row['selected_parameter_keys']=sorted(body_keys|({f[0] for f in row['parameter_facts']} & set(n.get('control_keys',[]))))
            row['omitted_parameter_keys']=sorted({f[0] for f in row['parameter_facts']}-set(row['selected_parameter_keys']))
            if n.get('resolved_controller_metadata'):rev['resolved_controller_metadata']=n['resolved_controller_metadata']
            rev['status']='needs_review' if issues else 'revised';rev['issues']=[i['kind'] for i in issues]
            registered=copy.deepcopy(row.get('external_control_inputs') or {})
            if 'external_forces' in ctx[2]:registered['runtime_forces']=copy.deepcopy(ctx[2]['external_forces'])
            for obj in registered.get('objects',[]):
                current=ctx[1].get(obj['name'])
                if current:
                    for key in list(obj):
                        if key!='name' and key in current:obj[key]=copy.deepcopy(current[key])
            row['external_control_inputs']=registered
            if new_ctrl:row['external_control_disclosure']={'kinds':n.get('control_keys',[]),'disclosure':' '.join(new_ctrl)}
            row['full_numeric_audit']={'status':'needs_review' if issues else 'verified','source':proof,'field_checks':len(field_records),'numeric_clause_checks':len(numeric_checks),'controller_keys':n.get('control_keys',[]),'issues':issues}
            for key in ['sha256','download','split','source_group_id','canonical_video_id']:assert row.get(key)==original.get(key)
            entry={'video_id':vid,'video_sha256':row['sha256'],'source':proof,'fields':field_records,'numeric_checks':numeric_checks,'source_controls':new_ctrl,'issues':issues}
            handles['AUDIT_LEDGER.jsonl.gz'].write(json.dumps(entry,ensure_ascii=False)+'\n')
            if row['parameter_facts']!=original['parameter_facts'] or newtexts!=original['prompt_variants_en']:
                handles['CHANGES.jsonl.gz'].write(json.dumps({'video_id':vid,'field_changes':fact_changes,'old_prompts':original['prompt_variants_en'],'new_prompts':newtexts,'old_hashes':original['prompt_variant_sha256'],'new_hashes':row['prompt_variant_sha256']},ensure_ascii=False)+'\n');stats['changed_rows']+=1
            encoded=json.dumps(row,ensure_ascii=False)+'\n';handles['videos.jsonl.gz'].write(encoded)
            if row.get('split')=='train_final':handles['train_final_candidates.jsonl.gz'].write(encoded);stats['train_final_candidates']+=1
            stats['videos']+=1;stats['fields_checked']+=len(field_records);stats['numeric_clause_checks']+=len(numeric_checks);stats['variants']+=3;stats['field_corrections']+=len(fact_changes)
            if issues:pending.append({'video_id':vid,'issues':issues});stats['needs_review']+=1
            else:stats['verified']+=1
            if stats['videos']%6000==0:print(json.dumps(dict(stats)),flush=True)
    finally:
        for f in handles.values():f.close()
    (OUT/'PENDING.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'RESIDUAL_NUMERIC_CLAUSES.json').write_text(json.dumps([{'clause':k,'count':v,'example':residual_examples[k]} for k,v in residual.most_common()],ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'REPORT.json').write_text(json.dumps({'counts':dict(stats),'source_manifest_sha256':sha(SOURCE),'source_configs_zip_sha256':sha(audit.ARCHIVE),'semantic_final_approval':False,'active_training_or_release_changed':False},indent=2),encoding='utf8')
    print(json.dumps(dict(stats)))

def preflight():
    z=zipfile.ZipFile(audit.ARCHIVE);seen=set();result=[]
    for line in gzip.open(SOURCE,'rt',encoding='utf8'):
        row=json.loads(line);tag=row['engine']+'/'+row['scene']
        if tag in seen or not row.get('config_download'):continue
        seen.add(tag);raw=json.loads(z.read(row['config_download']['member']));ctx=audit.context(raw)
        try:
            n,c,clock=source_controls(row,raw,ctx)
            result.append({'scene':tag,'issues':n['issues'],'controls':n['source_control_clauses']})
        except Exception as exc:result.append({'scene':tag,'exception':repr(exc)})
    (OUT/'CONTROL_PREFLIGHT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':
    if '--preflight' in sys.argv:preflight()
    else:main()
