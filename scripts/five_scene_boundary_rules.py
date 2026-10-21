"""Original named event rules and restricted parameter interventions for five scenes."""
import copy
import math


def differences(a,b,path=()):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):raise ValueError('physical schema changes within parameter slice')
        return [p for k in a for p in differences(a[k],b[k],path+(k,))]
    if isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):raise ValueError('physical topology changes within parameter slice')
        return [p for i in range(len(a)) for p in differences(a[i],b[i],path+(i,))]
    return [] if a==b else [path]


def get(x,path):
    for k in path:x=x[k]
    return x


def put(x,path,value):
    for k in path[:-1]:x=x[k]
    x[path[-1]]=value


def physical(config):
    return dict(objects={o['name']:copy.deepcopy(o) for o in config['dynamic_objects']},forces=copy.deepcopy(config.get('runtime_forces') or []))


def allowed(scene,family,path):
    if len(path)<3 or path[0]!='objects':return False
    name=path[1];tail=path[2:]
    choices={
      ('T01','A'):[(['t01v2_folder_ramp','t01v2_sliding_book'],('friction',))],
      ('T01','B'):[(['t01v2_chain_can_2','t01v2_chain_mug'],('pose','position',0))],
      ('T01','C'):[(['t01v2_tabletop_collision_slab','t01v2_chain_can_1','t01v2_chain_can_2','t01v2_chain_mug'],('friction',))],
      ('T04','support_release'):[(['t04v3_removable_support_bar'],('motion','initial_velocity',1))],
      ('T04','stack_sliding'):[(['t04v3_folder_ramp_pbr','t04v3_stack_book_bottom'],('friction',))],
      ('T04','terminal_transfer'):[(['t04v3_chain_mug'],('pose','position',0))],
      ('T05','gate_passage'):[(['t05v2_guide_left','t05v2_guide_right'],('pose','position',1))],
      ('T05','terminal_transfer'):[(['t05v2_guide_left','t05v2_guide_right'],('friction',))],
      ('T08','A_book_initial_speed_mps'):[(['t08_lower_impactor_book'],('motion','initial_velocity',0))],
      ('T08','B_impact_eccentricity_m'):[(['t08_target_mug'],('pose','position',0))],
      ('T08','C_mug_total_mass_kg'):[(['t08_target_mug'],('mass',)),(['t08_target_mug'],('material_preset','mass'))],
    }
    return any(name in names and tail==field for names,field in choices.get((scene,family),[]))


def t11_intervention(config,family,old,new):
    c=copy.deepcopy(config);objects={o['name']:o for o in c['dynamic_objects']};forces=c.get('runtime_forces',[])
    def lerp(v,lo,hi,a,b):return a+max(0.,min(1.,(v-lo)/(hi-lo)))*(b-a)
    driver='t11_driver_eraser';relay='t11_relay_pencil_case';case='t11_eyeglasses_case'
    if family=='driver_initial_speed_mps':
        for f in forces:
            if f['target']!=driver:continue
            f['force_world'][0]+=lerp(new,1.8,3.6,.18,.30)-lerp(old,1.8,3.6,.18,.30)
            f['force_world_after_contact'][0]+=lerp(new,1.8,3.6,0,.60)-lerp(old,1.8,3.6,0,.60)
            f['stop_after_contact_delay_frames']+=int(round(lerp(new,1.8,3.6,0,20)))-int(round(lerp(old,1.8,3.6,0,20)))
    elif family in ['relay_case_gap_m','case_edge_margin_m']:
        delta=lambda t:lerp(t,.012,.085,.12,.27) if family=='relay_case_gap_m' else lerp(t,.025,.175,.008,.22)
        for n in ([driver,relay] if family=='relay_case_gap_m' else [driver,relay,case]):objects[n]['pose']['position'][0]-=delta(new)-delta(old)
    elif family=='relay_block_mass_kg':
        objects[relay]['mass']+=new-old
        if 'mass' in objects[relay].get('material_preset',{}):objects[relay]['material_preset']['mass']+=new-old
        delta=(.35+10*max(0.,new-.08))-(.35+10*max(0.,old-.08))
        for f in forces:
            if f['target']==driver:
                for k in ['force_world_after_first_contact','force_world_relay_phase']:f[k][0]+=delta
    else:raise ValueError('unknown original T11 family')
    return c


def close(a,b):
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):return abs(a-b)<1e-8
    if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(close(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(close(x,y) for x,y in zip(a,b))
    return a==b


def intervene(job,theta):
    a,b=job['bracket'];left,right=[e['config'] for e in job['endpoints']]
    if left['scene_overrides']!=right['scene_overrides']:raise ValueError('different fixed scene physics')
    timing=['fps','frames','pre_static_frames','physics_steps_per_render_frame']
    if any(left['render'].get(k)!=right['render'].get(k) for k in timing):raise ValueError('different simulation timing')
    if job['scene_id']=='T11':
        if not close(physical(t11_intervention(left,job['family_id'],a,b)),physical(right)):raise ValueError('original T11 recipe does not reproduce right endpoint')
        c=t11_intervention(left,job['family_id'],a,theta)
    else:
        lo,hi=physical(left),physical(right);changed=differences(lo,hi)
        if not changed or any(not allowed(job['scene_id'],job['family_id'],p) for p in changed):raise ValueError('intervention changes fields outside original family')
        value=copy.deepcopy(lo)
        for p in changed:
            x,y=get(lo,p),get(hi,p)
            if not isinstance(x,(int,float)) or not isinstance(y,(int,float)):raise ValueError('non-numeric interpolation')
            put(value,p,x+(theta-a)/(b-a)*(y-x))
        c=copy.deepcopy(left);c['dynamic_objects']=list(value['objects'].values());c['runtime_forces']=value['forces']
    # At source points use exact original bytes' values, never rounded interpolation.
    if theta==a:c=copy.deepcopy(left)
    if theta==b:c=copy.deepcopy(right)
    # A conditional refinement fixes one recorded endpoint seed throughout.
    # T11 pairs already share a seed; other scene scans may use different ones.
    seed_endpoint=job.get('seed_endpoint',0)
    if seed_endpoint not in [0,1]:raise ValueError('conditional seed must come from a published endpoint')
    seed_config=[left,right][seed_endpoint]
    for key in ['random_seed','seed']:
        if key in seed_config:c[key]=seed_config[key]
        else:c.pop(key,None)
    for key in ['random_seed','seed','simulation_seed']:
        if key in seed_config.get('experiment',{}):c.setdefault('experiment',{})[key]=seed_config['experiment'][key]
        else:c.setdefault('experiment',{}).pop(key,None)
    c.setdefault('experiment',{})['supplemental_intervention']=dict(family=job['family_id'],theta=theta,source_bracket=job['bracket'])
    return c


def event(config,state,target):
    frames=state['frames']
    if len(frames)!=210 or any(not math.isfinite(v) for f in frames for o in f['objects'] for v in o['position']):raise ValueError('incomplete/nonfinite state')
    def track(n):return [next(o for o in f['objects'] if o['name']==n) for f in frames]
    def contact(a,b):
        if not any('contacts' in f for f in frames):raise ValueError('native contacts missing')
        return int(any({c.get('entity_a'),c.get('entity_b')}=={a,b} for f in frames for c in f.get('contacts',[])))
    def rotation(n):
        ss=track(n);q=ss[0]['quaternion_xyzw']
        return max(math.degrees(2*math.acos(min(1.,abs(sum(x*y for x,y in zip(q,o['quaternion_xyzw'])))/math.sqrt(sum(x*x for x in q)*sum(x*x for x in o['quaternion_xyzw']))))) for o in ss)
    if target=='book_can_1_contact':return contact('t01v2_sliding_book','t01v2_chain_can_1')
    if target=='can_1_can_2_contact':return contact('t01v2_chain_can_1','t01v2_chain_can_2')
    if target=='support_bar_displacement_reaches_original_release_clearance':
        ss=track('t04v3_removable_support_bar');return int(max(abs(o['position'][1]-ss[0]['position'][1]) for o in ss)>=config['experiment']['parameter']['estimated_support_release_threshold_m'])
    if target=='stack_motion':
        ss=[track('t04v3_stack_book_'+v) for v in ['bottom','middle','top']]
        return int(any(max(o['position'][0]-s[0]['position'][0] for o in s)>.12 or max(s[0]['position'][2]-o['position'][2] for o in s)>.025 for s in ss))
    if target=='can2_mug_contact_and_rotation_ge_18deg':return int(contact('t04v3_chain_can_2','t04v3_chain_mug') and rotation('t04v3_chain_mug')>=18.)
    if target=='gate_passage':return int(max(o['position'][0] for o in track('t05v2_moving_phone'))>=config['experiment']['geometry_contract']['phone_center_full_pass_x_m'])
    if target=='terminal_contact':return contact('t05v2_moving_phone','t05v2_downstream_can')
    if target.startswith('t08_') and target.endswith('_below_table_8cm'):
        return int(any(o['position'][2]<config['experiment']['table_top_z']-.08 for o in track(target[:-len('_below_table_8cm')])))
    if target.endswith('_final_center_below_minus_20cm'):return int(track(target[:-len('_final_center_below_minus_20cm')])[-1]['position'][2]<-.20)
    raise ValueError('unregistered event '+target)
