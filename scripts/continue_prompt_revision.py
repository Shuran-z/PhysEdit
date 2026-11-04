"""Conservative second pass: de-duplicate source controls and move optional facts."""
from pathlib import Path
from fractions import Fraction
import sys,json,gzip,zipfile,hashlib,collections,re,math,functools,copy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from physedit.compact_prompt import counts,sentence,MODEL_BUDGETS
from physedit.natural_short_prompt import number
from scripts.revise_existing_prompts import wording,revise
OUT=ROOT/'review/prompt_revision_20261102'
OLD=ROOT/'review/prompt_revision_20261101'
SRC=ROOT/'review/prompt_rewrite_release_20261101/source'
counts=functools.lru_cache(32768)(counts)
sha=lambda s:hashlib.sha256(s.encode()).hexdigest()
EVIDENCE={r['video_id']:r for r in json.loads((OUT/'runtime_evidence.json').read_text(encoding='utf8'))} if (OUT/'runtime_evidence.json').exists() else {}
T01_HEADERS={r['source_record']['source_key']:r for r in json.loads((OUT/'T01_original_headers.json').read_text(encoding='utf8'))} if (OUT/'T01_original_headers.json').exists() else {}
T01_ALIGNMENT={r['canonical_video_id']:r for r in map(json.loads,gzip.open(ROOT/'review/scene_videos_20261031/MISSING_CONFIG_ALIGNMENT.jsonl.gz','rt',encoding='utf8')) if r['scene']=='T01'}

def normalize(s):
    # Only remove binary floating-point printing noise within eight ULPs.
    def fmt(m):
        v=float(m[0]);short=format(v,'.15g')
        # A fixed precision is idempotent: repeating formatting cannot drift.
        return short if abs(float(short)-v)<=8*math.ulp(v) and len(short)<len(m[0]) else m[0]
    s=re.sub(r'(?<![\w])[-+]?\d+\.\d{8,}(?:[eE][-+]?\d+)?',fmt,s)
    for a,b in [('Hold the initial scene for','Hold initially for'),('The removable support bar','The support bar'),('An off-screen actuator tilts','Tilt'),('An off-screen force pulse acts on','Apply an off-screen force pulse to'),('during controller frames','in frames'),('over controller frames','in frames'),('Force active in controller frames','Force active in frames'),('Controller step','Frame step'),('s after the static interval','s after the hold'),('with piecewise_quintic interpolation','with quintic interpolation')]:s=s.replace(a,b)
    s=s.replace('Apply +X force to the eraser:','Eraser +X force:').replace('The eraser starts at rest.','Eraser initially at rest.')
    s=s.replace('0 N for 0 frames, then stop.','stop immediately.')
    s=s.replace('An off-screen compression spring pulls marker along world axis (1, 0, 0):','Off-screen +X compression spring on marker:')
    s=s.replace('The gate has a spring-loaded hinge targeting angle 0.','Spring-loaded gate hinge target: 0.')
    s=re.sub(r'At ([\d./]+) s, launch striker with world velocity \(([^,]+), 0, 0\) m/s and world angular velocity \(0, ([^,]+), 0\) rad/s\.',r'At \1 s, launch striker along +X at \2 m/s, spinning about +Y at \3 rad/s.',s)
    s=s.replace('spinning about +Y at','+Y spin')
    return s

def t11_primary_prompt(r,n,c):
    p=c.get('experiment',{}).get('parameter',{});pk=p.get('parameter_name');pv=p.get('parameter_value')
    forces=c.get('runtime_forces',[])
    if not forces or not forces[0].get('first_contact_pair'):return n
    f=forces[0];obs={o.get('spec',o)['name']:o.get('spec',o) for o in c.get('objects',c.get('dynamic_objects',[]))}
    selected=pv if pk=='joint_global_configuration' else {pk:pv}
    labels={'driver_initial_speed_mps':('Drive setting','m/s'),'relay_case_gap_m':('Relay-case gap','m'),'case_edge_margin_m':('Case edge margin','m'),'relay_block_mass_kg':('Relay mass','kg'),'case_friction_coefficient':('Case friction','')}
    if not selected or any(k not in labels for k in selected):return n
    for key,obj,field in [('relay_block_mass_kg','t11_relay_pencil_case','mass'),('case_friction_coefficient','t11_eyeglasses_case','friction')]:
        if key in selected and not math.isclose(float(selected[key]),float(obs[obj][field]),rel_tol=1e-12):
            n['issues'].append('primary_parameter_does_not_match_body_spec');n['status']='needs_review';return n
    velocity=obs[f['target']].get('motion',{}).get('initial_velocity')
    if velocity != [0.,0.,0.]:return n
    vectors=[f['force_world'],f['force_world_after_first_contact'],f['force_world_after_contact']]
    if any(v[1:]!=[0.,0.] or v[0]<0 for v in vectors):return n
    render=c.get('render',{});pre=render.get('pre_static_frames');fps=render.get('fps')
    dt=c.get('scene_overrides',{}).get('dt');steps=render.get('physics_steps_per_render_frame')
    if not dt or not steps or not fps or pre is None:return n
    gravity=next((s for s in re.split(r'(?<=\.)\s+',n['prompt_en']) if s.startswith('Gravity ')),None)
    if not gravity:return n
    clauses=[labels[k][0]+' '+number(v)+(' '+labels[k][1] if labels[k][1] else '') for k,v in selected.items()]
    def exact_short(v):
        s=number(v);f=Fraction(v).limit_denominator(10000)
        return str(f) if abs(float(f)-v)<=8*math.ulp(v) and len(str(f))+2<len(s) else s
    a,b,d=[exact_short(v[0]) for v in vectors];delay=f['stop_after_contact_delay_frames']
    stop='stop immediately' if vectors[2][0]==0 and delay==0 else f'{d} N for {delay} frames, then stop'
    control=f'Hold {number(pre/fps)} s. Eraser rests. +X force: {a} N; if eraser contacts pencil case, {b} N; if pencil case contacts glasses case, {stop}. Frames {f["frame_start"]}-{f["frame_end"]} at {number(1/(dt*steps))} Hz.'
    body=gravity+' '+'; '.join(clauses)+'. '+control
    variants=[prefix+' '+body for prefix in ['Fixed camera.','Keep camera fixed.','Camera stays fixed.']]
    n.update(prompt_variants_en=variants,prompt_en=variants[0],prompt_variant_sha256=[sha(s) for s in variants],token_counts=[counts(s) for s in variants],source_control_clauses=[control])
    n['primary_input_metadata']={'source':'config.experiment.parameter','config_sha256':r['config_download']['sha256'],'selected':selected,'driver_setting_is_not_actual_initial_velocity':True}
    n['changes'].append({'reason':'preserve_declared_primary_inputs_and_complete_contact_controller_move_other_inputs_to_metadata','selected_primary_keys':list(selected)})
    # Each original parameter remains in parameter_facts and the original config binding.
    protected=['gravity','initial_velocity','prescribed_force']+list(selected)
    n['moved_to_metadata']=sorted(set(n['moved_to_metadata'])|{f[0] for f in r['parameter_facts'] if not any(k in f[0] for k in protected)})
    n['issues']=[i for i in n['issues'] if i!='over_budget_required_information_not_truncated']
    if any(any(tc[k]>v for k,v in MODEL_BUDGETS.items()) for tc in n['token_counts']):n['issues'].append('over_budget_required_information_not_truncated')
    n['status']='needs_review' if n['issues'] else 'revised'
    return n

def merge_equal_frictions(parts):
    groups=collections.defaultdict(list)
    for s in parts:
        m=re.fullmatch(r'Book (\d+) (?:material )?friction (\S+)\.',s)
        if m:groups[m[2]].append((s,m[1]))
    out=list(parts)
    for value,items in groups.items():
        if len(items)<2:continue
        originals={s for s,_ in items};index=min(out.index(s) for s in originals)
        out=[s for s in out if s not in originals]
        out.insert(index,'Books '+', '.join(i for _,i in items)+' friction '+value+'.')
    return out

def improve(r,n,c):
    n=copy.deepcopy(n)
    if n['parameter_conflicts']:return n
    facts=r['parameter_facts'];fmap={f[0]:f[-2] for f in facts}
    ctrl=r.get('external_control_inputs') or {}
    used=set(n['control_keys']);changes=n['changes'];moved=set(n['moved_to_metadata'])
    scheduled=any(k.startswith('runtime_forces.') or k.endswith('.motion') for k in used)
    controls=[normalize(s) for s in n['source_control_clauses']]
    evidence=EVIDENCE.get(n['video_id'],{})
    if r['scene']=='T18' and 'implicit_pull_timing_not_bound' in n['issues']:
        ev=evidence.get('runtime_evidence',{});complete=ev.get('complete.json',{}).get('content',{});signature=complete.get('signature',{})
        code=signature.get('code',{});expected=r['config_download']['sha256']
        classic=code.get('contract.py')=='5b06f5ef50bd39a6362ae489fdb2eb84611e81d9687de42592d412eb532696ad' and code.get('render.py')=='feb6633cfb7c963440f9f87edaa573f754ceafb1f324dc4f3ea04ce0e4d2958a'
        repair=code.get('contract.py')=='f626142f28631fd701350c4a6ac7c35d92c698b67c23960b567de0ecfe19be5b' and code.get('render.py')=='d23cf6d47f701bee23ca3fa23985cd3e26a5ae5b997752d14666e77b337e38cc'
        if signature.get('config_sha256')==expected and complete.get('files',{}).get(r['camera']+'.mp4')==r['sha256'] and (classic or repair):
            for filename,key in [('isaac_t16_t20_contract_snapshot.py','contract.py'),('isaac_t16_t20_render_snapshot.py','render.py')]:
                path=OUT/('t18_repair_'+key) if repair else ROOT.parent/'offscreen_control_audit_20261023'/filename
                assert hashlib.sha256(path.read_bytes()).hexdigest()==code[key]
            f=ctrl['implicit_control'];assert math.isclose(f['applied_force_newton'],c['event_spec']['applied_force_newton'],rel_tol=1e-12)
            who=f['target'].replace('t18_','').replace('_',' ')
            spec=c['event_spec'];travel=spec.get('pull_travel_limit_m',.24) if repair else .24;speedcap=spec.get('pull_speed_limit_earth_mps',.35) if repair else .35;duration=spec.get('pull_pulse_duration_s',80/30) if repair else 80/30
            controls=[f'Pull {who} -X: sine-squared pulse, start 32/30 s, duration {number(duration)} s, peak {number(f["applied_force_newton"])} N.', f'Speed cap {number(speedcap)}*sqrt(g/9.81) m/s; force fades over final 0.025 m to {number(travel)} m travel.']
            n['issues'].remove('implicit_pull_timing_not_bound');n['runtime_binding']=ev
            n['resolved_controller_metadata']={'clock':'recorded simulation time, excluding warmup','phase':'(t-32/30)/pulse_duration_s','pulse_duration_s':duration,'travel_limit_m':travel,'speed_limit_earth_mps':speedcap,'force_x':'-peak*sin(pi*phase)^2*max(0,1-max(0,-vx)/(speed_limit_earth_mps*sqrt(g/9.81)))*clip((travel_limit_m-travel)/.025,0,1)','active_phase':'0<phase<1','code_sha256':code}
    if r['scene']=='T14S' and evidence.get('renderer',{}).get('sha256')==evidence.get('renderer',{}).get('expected_sha256')=='5476f5e89ed048980304b849ff81e9b5e057e92edfa543ff63f310e82a3a4641':
        assert hashlib.sha256((OUT/'t14s_renderer.py').read_bytes()).hexdigest()==evidence['renderer']['sha256']
        if ctrl.get('type') is None:
            cap=ctrl['spring_force_cap_n'];stiff=ctrl['stiffness_n_per_m'];damping=ctrl['damping_ns_per_m']
            assert math.isclose(stiff,max(.52,cap*1.02/.55),rel_tol=1e-12) and math.isclose(damping,.03*math.sqrt(stiff/.52),rel_tol=1e-12)
            controls=['Hold initially for 4/5 s.',f'Off-screen +X compression spring on marker: stiffness {number(stiff)} N/m, damping {number(damping)} Ns/m, force cap {number(cap)} N, active frames (0, 11.375) at 30 Hz.','Spring-loaded gate hinge target: 0.']
            ctrl=dict(ctrl,type='capped_compression_spring_plus_velocity_damping')
        n['issues']=[i for i in n['issues'] if i not in ['initial_motion_not_fully_recovered','special_controller_needs_semantic_adapter']]
        n['runtime_binding']=evidence;n['resolved_controller_metadata']={'initial_velocities':'all four bodies zero linear and angular velocity','active_frame':'frame - 24 + substep/16 < 11.375','force_x':'clip(k*max(0,.65-(marker_x-.09+.59))-damping*vx,0,cap)','renderer_sha256':evidence['renderer']['sha256']}
    # Resolve oblique initial velocity from its own scalar speed and tray angle.
    angle=next((v for k,v in fmap.items() if k.endswith('tray_angle_deg')),None)
    speed=next((v for k,v in fmap.items() if k in ['initial_speed_mps','prescribed_parameters.initial_speed_mps']),None)
    if angle is not None and speed is not None:
        for i,s in enumerate(controls):
            m=re.fullmatch(r'The (.+) starts with world velocity \(([^)]+)\) m/s\.',s)
            if not m:continue
            try:v=[float(x.strip()) for x in m[2].split(',')]
            except ValueError:continue
            a=math.radians(angle)
            if len(v)==3 and all(math.isclose(x,y,abs_tol=1e-12,rel_tol=1e-12) for x,y in zip(v,[speed*math.cos(a),0,-speed*math.sin(a)])):
                controls[i]=f'The {m[1]} starts at {number(speed)} m/s along +X, {number(angle)} degrees downward.'
    controls=[normalize(s) for s in controls]
    represented={};optional={}
    for f in facts:
        k,v,u=f[0],f[-2],f[-1];cl=normalize(wording(sentence(k,v,u)))
        if '.prescribed_force_' in k:
            parent=k.split('.prescribed_force_')[0]
            if 'runtime_forces.'+parent in used:represented[cl]=k
        if k=='prescribed_parameters.driver_initial_speed_mps' and v==0 and any('initially at rest.' in t for t in controls):represented[cl]=k
        if k.endswith(('striker_speed_mps_fixed','probe_speed_mps_fixed')):
            actor='striker eraser' if 'striker' in k else 'probe marble'
            if any(f'The {actor} starts at {number(v)} m/s' in t for t in controls):represented[cl]=k
        if k in ['spring_force_cap','spring_stiffness','spring_damping'] and ctrl.get('type')=='capped_compression_spring_plus_velocity_damping':represented[cl]=k
        if ctrl.get('kind')=='one_time_velocity_and_spin_assignment' and ('initial_speed' in k or 'rolling_radius' in k):
            if 'initial_speed' in k and math.isclose(float(v),math.sqrt(sum(x*x for x in ctrl['world_linear_velocity_mps'])),rel_tol=1e-12):represented[cl]=k
        # Fixed support mass and non-key body masses do not define an intervention.
        primary=(c.get('experiment') or {}).get('parameter') or {}
        primary=primary if isinstance(primary,dict) else {}
        pk=primary.get('parameter_name','')
        required=r.get('required_parameter_keys') or []
        mass=k.endswith(('.mass','_mass','_mass_kg'))
        if mass and k not in required and not ('mass' in pk):optional[cl]=k
        # Derived projected width, radius and fixed pad geometry remain in metadata.
        if any(x in k for x in ['projected_width_at_initial_yaw','high_gravity_support_pad','rolling_radius']) and k not in required and not any(x in pk for x in ['radius','pad','projected']):optional[cl]=k
        if k=='prescribed_parameters.gravity_magnitude_mps2' and 'gravity_vector' in fmap:represented[cl]=k
    parts=[]
    original_controls=dict(zip(n['source_control_clauses'],controls))
    for text in n['prompt_variants_en']:
        if n.get('resolved_controller_metadata'):
            for a in n['source_control_clauses']:text=text.replace(a,'')
            text=text.strip()+' '+' '.join(controls)
        else:
            for a,b in original_controls.items():text=text.replace(a,b)
        ps=[]
        for s in re.split(r'(?<=\.)\s+',text.strip()):
            s=normalize(s)
            if not s:continue
            if n.get('resolved_controller_metadata') and r['scene']=='T18' and s.startswith('An off-screen actuator applies the prescribed pulling force'):continue
            if s in represented:
                changes.append({'before':s,'after':None,'reason':'same_input_already_in_source_control','key':represented[s]});continue
            if s.startswith('After ') and 'static pre-roll' in s and controls and (scheduled or any('initial_velocity' in k for k in used)):
                changes.append({'before':s,'after':None,'reason':'static_interval_and_initial_motion_already_explicit'});continue
            if ctrl.get('kind')=='one_time_velocity_and_spin_assignment' and s not in controls and s.startswith('At ') and 'launch striker along' in s:
                changes.append({'before':s,'after':None,'reason':'source_timed_velocity_and_spin_already_explicit'});continue
            if ctrl.get('type')=='capped_compression_spring_plus_velocity_damping' and s.startswith('Off-screen spring force drives'):
                changes.append({'before':s,'after':None,'reason':'full_spring_control_already_explicit'});continue
            ps.append(s)
        parts.append(list(dict.fromkeys(ps)))
    def fits():return all(all(counts(' '.join(p))[k]<=v for k,v in MODEL_BUDGETS.items()) for p in parts)
    for cl,k in optional.items():
        if fits():break
        if any(cl in p for p in parts):
            parts=[[s for s in p if s!=cl] for p in parts];moved.add(k)
            changes.append({'before':cl,'after':None,'reason':'nonkey_input_preserved_in_metadata','key':k})
    if not fits() and r['scene']=='T18':
        parts=[merge_equal_frictions(p) for p in parts]
        changes.append({'reason':'combine_equal_book_friction_clauses_without_removing_any_input'})
    if not fits() and r['scene']=='T18':
        def shorten(s):return s.replace('Keep the camera fixed.','Keep camera fixed.').replace('Speed cap 1*sqrt(g/9.81)','Speed cap sqrt(g/9.81)')
        parts=[[shorten(s) for s in p] for p in parts];controls=[shorten(s) for s in controls]
        changes.append({'reason':'remove_redundant_article_and_identity_multiplier_no_parameter_change'})
    new=[' '.join(p) for p in parts]
    # Evidence clauses may span multiple sentences, but must survive intact.
    assert all(all(clause in text for clause in controls) for text in new),(n['video_id'],'control_clause_lost')
    n.update(prompt_variants_en=new,prompt_en=new[0],prompt_variant_sha256=[sha(s) for s in new],token_counts=[counts(s) for s in new],source_control_clauses=controls,moved_to_metadata=sorted(moved))
    n['issues']=[i for i in n['issues'] if i!='over_budget_required_information_not_truncated']
    if not fits():n['issues'].append('over_budget_required_information_not_truncated')
    if new!=r['prompt_variants_en']:changes.append({'reason':'local_wording_and_equivalent_float_formatting','raw_numeric_inputs_preserved_in_parameter_facts':True})
    n['status']='needs_review' if n['issues'] else 'revised'
    return n

def main():
    OUT.mkdir(exist_ok=True);z=zipfile.ZipFile(SRC/'configs.zip');cache={};stats=collections.Counter();issues=collections.Counter();by_scene=collections.Counter()
    with gzip.open(OLD/'revised_72000.jsonl.gz','rt',encoding='utf8') as prev,gzip.open(SRC/'videos.jsonl.gz','rt',encoding='utf8') as source,gzip.open(OUT/'revised_72000.jsonl.gz','wt',encoding='utf8',compresslevel=1) as dst:
        for a,b in zip(source,prev):
            r,n=json.loads(a),json.loads(b);assert r['canonical_video_id']==n['video_id']
            if n['issues'] or r['scene']=='T11':
                d=r.get('config_download');c={}
                if d:
                    key=d['member']
                    if key not in cache:
                        raw=z.read(key);assert hashlib.sha256(raw).hexdigest()==d['sha256'];cache[key]=json.loads(raw)
                        if len(cache)>128:cache.pop(next(iter(cache)))
                    c=cache[key]
                if r['scene']=='T01' and 'initial_motion_not_fully_recovered' in n['issues']:
                    binding=T01_ALIGNMENT.get(r['canonical_video_id'],{});source=T01_HEADERS.get(binding.get('metadata_source_key'))
                    if source and source['source_record']['sha256']==binding['metadata_artifact_sha256'] and binding['video_sha256']==r['sha256'] and binding['source_video_and_parameters_consistent']:
                        c=source['header'];clock={};dt=c.get('scene_overrides',{}).get('dt');steps=c.get('render',{}).get('physics_steps_per_render_frame')
                        if dt and steps:clock['physical_dt_s']=dt*steps
                        new=revise(r,c,clock);n.update(new);n['runtime_binding']={'original_metadata_record':source['source_record'],'alignment':binding};n['original_config_recovered']=False
                n=improve(r,n,c)
                if r['scene']=='T11':n=t11_primary_prompt(r,n,c)
            dst.write(json.dumps(n,ensure_ascii=False)+'\n');stats[n['status']]+=1;issues.update(n['issues']);by_scene[(r['scene'],n['status'])]+=1
    report={'videos':sum(stats.values()),'status':dict(stats),'issues':dict(issues),'by_scene':{'/'.join(k):v for k,v in by_scene.items()},'previous_release_unchanged':True}
    (OUT/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
