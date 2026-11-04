"""Source-only short descriptions. Required controls never compete with optional facts."""
import collections
from fractions import Fraction
import json
import math
import re
from .compact_prompt import counts, label, priority, MODEL_BUDGETS

VERSION='natural-key-parameters-controls-v1'

def number(v):
    if isinstance(v,(list,tuple)):return '('+', '.join(number(x) for x in v)+')'
    if isinstance(v,bool):return str(v).lower()
    if not isinstance(v,(float,int)):return str(v)
    if isinstance(v,int) or v==int(v):return str(int(v))
    raw=str(v);best=raw
    for n in range(1,17):
        s=format(v,f'.{n}g')
        if abs(float(s)-v)<=8*math.ulp(v):best=s;break
    f=Fraction(v).limit_denominator(120)
    if abs(float(f)-v)<=8*math.ulp(v) and abs(f.numerator)<=120 and len(str(f))+2<len(best):best=str(f)
    return best

def name(k):
    s=label(k).replace('falling book','other book').replace('terminal eraser','eraser')
    s=s.replace('driver eraser','eraser').replace('relay pencil case','pencil case').replace('eyeglasses case','glasses case')
    return s

def objects(c):
    return {o.get('spec',o)['name']:o.get('spec',o) for o in c.get('objects',c.get('dynamic_objects',[]))}

def controls(c,registered=None,clock=None,facts=()):
    registered=registered or {};clock=clock or {};obs=objects(c) or {o['name']:o for o in registered.get('objects',[])}
    pieces=[];issues=[];used=[];fmap={f[0]:f[-2] for f in facts}
    r=c.get('render',{}) or registered.get('render',{});fps=r.get('fps') or registered.get('fps') or registered.get('render_fps')
    pre=r.get('pre_static_frames',registered.get('pre_static_frames',0)) or 0
    if registered.get('kind')=='one_time_velocity_and_spin_assignment':
        pieces.append(f"At {number(registered['time_s'])} s, launch {registered['body']} with world velocity {number(registered['world_linear_velocity_mps'])} m/s and world angular velocity {number(registered['world_angular_velocity_radps'])} rad/s.")
        if registered.get('no_subsequent_external_drive'):pieces.append('No subsequent external drive.')
        used.append('registered.one_time_velocity_and_spin_assignment')
    if clock.get('initial_hold_duration_s') is not None:
        pieces.append('Hold the initial scene for '+str(Fraction(clock['remaining_static_frames'],int(clock['static_clock_hz'])))+' s.');used.append('clock.initial_hold_duration')
    elif pre and fps:
        pieces.append('Hold initially for '+str(Fraction(pre,int(fps)))+' s.');used.append('render.pre_static_frames')
    force=c.get('runtime_forces') or registered.get('runtime_forces',[])
    recipe=clock.get('conditional_force_recipe')
    if recipe:force=[recipe]
    grouped=collections.defaultdict(list)
    for f in force:grouped[f.get('target','object')].append(f)
    for target,fs in grouped.items():
        who=name(target);f=fs[0]
        if f.get('first_contact_pair') and f.get('force_world_after_contact') is not None:
            a,b=map(name,f['first_contact_pair']);u,v=map(name,f['stop_on_contact_pair'])
            xyz=f['force_world'];axis=max(range(3),key=lambda i:abs(xyz[i]));direction=('+' if xyz[axis]>=0 else '-')+'XYZ'[axis]
            pieces.append(f"Apply {direction} force to the {who}: {number(abs(xyz[axis]))} N; if {a} touches {b}, {number(abs(f['force_world_after_first_contact'][axis]))} N; if {u} touches {v}, {number(abs(f['force_world_after_contact'][axis]))} N for {f['stop_after_contact_delay_frames']} frames, then stop.")
            pieces.append(f"Force active in controller frames {f['frame_start']}-{f['frame_end']}.")
        elif len(fs)==1 and 'support_pull_force_duration_s' in fmap:
            pieces.append(f"Pull the support bar along +Y with {number(fmap['support_pull_force_magnitude_n'])} N for {number(fmap['support_pull_force_duration_s'])} s.")
            used.extend(['support_pull_force_duration_s','support_pull_force_magnitude_n'])
        elif len(fs)>1:
            peak=max(fs,key=lambda f:math.sqrt(sum(x*x for x in f['force_world'])))
            start=min(f['frame_start'] for f in fs);end=max(f['frame_end'] for f in fs)
            pieces.append(f"An off-screen force pulse acts on {who} during controller frames {start}-{end}, with peak world force {number(peak['force_world'])} N.")
        else:
            pieces.append(f"Apply off-screen world force {number(f['force_world'])} N to {who} during controller frames {f['frame_start']}-{f['frame_end']}.")
        used.append('runtime_forces.'+target)
    if force and 'support_pull_force_duration_s' not in fmap:
        dt=clock.get('physical_dt_s') or clock.get('active_frame_period_s')
        if dt:pieces.append('Controller step '+number(dt)+' s.')
        elif fps:pieces.append('Source controller rate '+number(fps)+' Hz.');issues.append('controller_clock_requires_renderer_check')
        else:issues.append('missing_controller_clock')
    for key,o in obs.items():
        m=o.get('motion') or {};typ=m.get('type','none');who=name(key)
        if typ=='scripted_keyframes':
            k=m['keyframes'];segments=[]
            for a,b in zip(k,k[1:]):
                d=[y-x for x,y in zip(a['position'],b['position'])]
                e=[y-x for x,y in zip(a.get('euler_xyz',[0,0,0]),b.get('euler_xyz',[0,0,0]))]
                if any(abs(x)>1e-12 for x in d+e):segments.append((a,b,d,e))
            for a,b,d,e in segments:
                pieces.append(f"Actuate {who}: translate {number(d)} m, rotate {number(e)} degrees over controller frames {a['frame']}-{b['frame']} with {m.get('interpolation',b.get('easing','registered'))} interpolation; hold afterward.")
            used.append(key+'.motion')
            if not segments:issues.append('stationary_scripted_path')
        elif typ=='scripted_tip_y_then_release':
            pieces.append(f"An off-screen actuator tilts {who} about world y from {number(m['start_angle_deg'])} to {number(m['end_angle_deg'])} degrees, starting at controller frame {m['start_frame']} for {m['frames']} frames, then releases it.")
            used.append(key+'.motion')
        elif typ not in ['none','physics','set_velocity',None]:issues.append('unsupported_motion:'+str(typ))
        vel=m.get('initial_velocity')
        if vel and any(vel):
            axes=[i for i,v in enumerate(vel) if v]
            if len(axes)==1:
                a=axes[0];pieces.append(f"The {who} starts at {number(abs(vel[a]))} m/s along {'+' if vel[a]>0 else '-'}{'XYZ'[a]}.")
            else:pieces.append(f"The {who} starts with world velocity {number(vel)} m/s.")
            used.extend([key+'.initial_velocity',key+'.initial_speed'])
            speed=math.sqrt(sum(v*v for v in vel))
            for k in ['initial_speed_mps','initial_speed']:
                if k in fmap and math.isclose(fmap[k],speed,rel_tol=1e-12,abs_tol=1e-12):used.append(k)
        elif vel and key in grouped:
            pieces.append(f'The {who} starts at rest.');used.extend([key+'.initial_velocity',key+'.initial_speed'])
        omega=m.get('initial_angular_velocity')
        if omega and any(omega):
            axes=[i for i,v in enumerate(omega) if v]
            if len(axes)==1:
                a=axes[0];pieces.append(f"The {who} starts spinning at {number(omega[a])} rad/s about {'XYZ'[a]}.")
            else:pieces.append(f"The {who} starts with world angular velocity {number(omega)} rad/s.")
            used.append(key+'.initial_angular_velocity')
    # Other controller families must not disappear behind an empty runtime_forces list.
    mechanisms={k:c.get(k) for k in ['spring_actuators','joint_spring_actuators','contact_driven_hinges'] if c.get(k)}
    implicit=registered.get('implicit_control') or {}
    if implicit.get('type')=='horizontal_pd_withdrawal':
        pieces.append(f"An off-screen actuator withdraws {name(implicit['target'])} by {number(implicit['withdrawal_distance_m'])} m and keeps its horizontal position controlled.")
        used.append('withdrawal_distance_m')
        if implicit.get('source_code_snapshot_sha256')=='5b06f5ef50bd39a6362ae489fdb2eb84611e81d9687de42592d412eb532696ad':
            pieces.append('Withdraw along -Y from 0.8 to 3.2 s with a smooth quintic position target.')
        else:issues.append('implicit_control_timing_not_bound')
    elif implicit.get('type')=='external_book_pull':
        pieces.append(f"An off-screen actuator pulls {name(implicit['target'])} with force setting {number(implicit['applied_force_newton'])} N.")
        used.append('applied_force_newton');issues.append('implicit_pull_timing_not_bound')
    elif implicit:issues.append('unsupported_implicit_controller')
    if registered.get('type')=='capped_compression_spring_plus_velocity_damping':
        f=registered
        pieces.append(f"An off-screen compression spring pulls {name(f['target'])} along world axis {number(f['force_axis'])}: stiffness {number(f['stiffness_n_per_m'])} N/m, damping {number(f['damping_ns_per_m'])} Ns/m, force cap {number(f['force_cap_n'])} N, active frames {number(f['active_frames'])} at {number(f['render_fps'])} Hz.")
        h=f.get('hinge_drive')
        if h:pieces.append(f"The gate has a spring-loaded hinge targeting angle {number(h['target_angle'])}.")
        used.extend(['spring_force_cap_n','stiffness_n_per_m','damping_ns_per_m'])
    elif mechanisms or registered.get('hinge_drive') or registered.get('stiffness_n_per_m'):
        issues.append('special_controller_needs_semantic_adapter')
    if any('scripted' in (o.get('motion') or {}).get('type','') for o in obs.values()):
        dt=clock.get('physical_dt_s') or clock.get('active_frame_period_s')
        if dt:pieces.append('Controller step '+number(dt)+' s after the static interval.')
        else:issues.append('scripted_controller_clock_requires_check')
    return pieces,used,issues

# Intervention/geometry fields; masses/material defaults remain in metadata unless an explicit required list names them.
def key_fact(k):
    low=k.lower()
    if low.startswith('prescribed_parameters.'):return False
    if any(x in low for x in ['expected','event','threshold','distance_to_boundary']):return False
    if low in ['gravity','gravity_vector']:return True
    return '.' not in low and any(x in low for x in ['angle','gap','offset','eccentricity','overlap','release_position','friction','initial_speed','extraction','pull_force','support_angle','contact_position'])

def fact_sentence(f):
    k,v,u=f[0],f[-2],f[-1];n=name(k);unit={'m/s²':'m/s^2','°':'degrees'}.get(u,u)
    if k=='gravity':return f'Gravity is {number(v)} m/s^2 downward.'
    if k=='gravity_vector':return f'World gravity is {number(v)} {unit}.'
    if n.endswith(' mass'):return f"The {n[:-5]} has mass {number(v)} {unit}."
    if n.endswith(' friction'):return f"The {n[:-9]} friction coefficient is {number(v)}."
    return f"{n.capitalize()} is {number(v)}{' '+unit if unit else ''}."

def build(row,c,clock=None,required_keys=()):
    obs=objects(c)
    # Names refer to object identities, not observed outcomes or target event labels.
    actors=[name(k) for k,o in obs.items() if not o.get('fixed') and o.get('visualization') is not False]
    intro='Keep the camera fixed. '
    if actors:intro+='The scene contains '+', '.join(actors)+'. '
    else:intro+='Preserve the objects and their layout in the supplied image. '
    ctl,used,issues=controls(c,row.get('external_control_inputs'),clock,row.get('parameter_facts',[]))
    facts=row.get('parameter_facts',[]);explicit=set(required_keys)|set(row.get('required_parameter_keys') or [])
    scene=row.get('scene') or row.get('clip_id','')[:3]
    req=[f for f in facts if f[0] in explicit or (key_fact(f[0]) and (scene!='T11' or f[0] in ['gravity','gravity_vector']))]
    # A quantity already expressed by the control record is retained there rather than repeated.
    control_keys=set(used)
    req=[f for f in req if f[0] not in control_keys]
    sentences=[];groups=collections.defaultdict(list)
    for f in req:
        if 'friction' in f[0] and isinstance(f[-2],(int,float)):groups[(f[-2],f[-1])].append(f)
        else:sentences.append(fact_sentence(f))
    for (_,unit),fs in groups.items():
        if len(fs)>1:sentences.append('Friction coefficients for '+', '.join(name(f[0]).replace(' friction','') for f in fs)+' are '+number(fs[0][-2])+'.')
        else:sentences.append(fact_sentence(fs[0]))
    sentences=list(dict.fromkeys(sentences))
    text=intro+' '.join(sentences+ctl)
    if not all(counts(text)[k]<=MODEL_BUDGETS[k] for k in MODEL_BUDGETS):
        # Shorten context only; never remove required numeric inputs or controls to pass a length check.
        intro='Fixed camera. ';text=intro+' '.join(sentences+ctl)
    selected=[f[0] for f in req]
    for f in sorted((f for f in facts if f[0] not in selected and f[0] not in control_keys),key=lambda f:priority(f[0])):
        if not isinstance(f[-2],(int,float)):continue
        if f[0].endswith('.mass') and f[-2]==0:continue
        if any(s in f[0].lower() for s in ['prescribed_parameters.','event','threshold','expected','frame','force_peak']):continue
        candidate=text+' '+fact_sentence(f)
        if all(counts(candidate)[k]<=MODEL_BUDGETS[k] for k in MODEL_BUDGETS):text=candidate;selected.append(f[0])
    token=counts(text);overflow=[k for k in MODEL_BUDGETS if token[k]>MODEL_BUDGETS[k]]
    if overflow:issues.append('required_text_over_budget:'+','.join(overflow))
    return {'prompt':text,'token_counts':token,'selected_parameter_keys':selected,'control_keys':used,
            'metadata_parameter_keys':[f[0] for f in facts if f[0] not in selected and f[0] not in control_keys],
            'issues':issues,'status':'needs_review' if issues else 'candidate'}
