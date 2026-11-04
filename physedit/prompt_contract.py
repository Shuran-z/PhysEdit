"""Shared English, initial-condition-only generation prompt contract.

No reference events, outcomes, future states, boundary labels, or captions are read.
Numeric inputs are serialized without rounding. Source names are not model inputs.
"""
import hashlib
import json
import math
import re

VERSION = 'english-key-parameters-three-prompts-v3-20261020'
OBJECT_FIELDS = {'mass', 'friction', 'static_friction', 'dynamic_friction',
                 'restitution', 'linear_damping', 'angular_damping', 'size',
                 'radius', 'height', 'fixed', 'position', 'quaternion',
                 'initial_velocity', 'initial_angular_velocity'}
CONTEXTS = {
    'bg01': 'a home tabletop setting', 'bg02': 'a physics laboratory setting',
    'bg03': 'a neutral studio setting', 'bg04': 'a library tabletop setting',
}
FORBIDDEN = re.compile(r'(?i)(?:theta[_ -]?(?:star|plus|minus)|nearacc|pairacc|'
                       r'boundary[_ -]?(?:value|distance|label)|reference[_ -]?(?:event|outcome)|'
                       r'will (?:fall|hit|collide|topple)|finally |eventually |'
                       r'falls off|fall to the floor|chain reaction)')
def english_label(value):
    value = str(value)
    if re.search(r'[\u3400-\u9fff]', value):
        raise ValueError('non_english_physical_input_key')
    value = re.sub(r'(?i)\bt\d+s?(?:v\d+)?_', '', value)
    return value.replace('_', ' ').replace('.', ' / ').strip()
def numeric(value):
    if isinstance(value, bool): return True
    if isinstance(value, (int, float)): return math.isfinite(value)
    return isinstance(value, (list,tuple)) and bool(value) and all(numeric(v) for v in value)
def render_full_facts(facts, *, context=None, variant=1, duration_s=None):
    """facts: [English source key, ignored historical label, numeric value, unit]."""
    parameters=[]
    for fact in facts:
        if len(fact)!=4: raise ValueError('invalid_physical_fact')
        key,_,value,unit=fact
        if not numeric(value): raise ValueError('non_numeric_physical_fact')
        label=english_label(key)
        if FORBIDDEN.search(label): raise ValueError('outcome_or_boundary_in_physical_inputs')
        unit=str(unit).replace('m/s²','m/s^2').replace('°','degrees')
        if re.search(r'[\u3400-\u9fff]',unit):raise ValueError('non_english_unit')
        parameters.append({'quantity':label,'value':value,'unit':unit or 'dimensionless'})
    leads={1:'Continue the physical motion from the supplied initial image.',
           2:'Generate a continuous physical continuation of the supplied initial image.',
           3:'Use the supplied image as the initial state and continue the motion.'}
    text=leads[variant]+' Keep the camera fixed and preserve the visible objects, their identities, and scene geometry.'
    if context: text+=' The setting is '+context+'.'
    if duration_s is not None:
        if not numeric(duration_s) or duration_s<=0:raise ValueError('invalid_duration')
        text+=' The requested observation duration is '+json.dumps(duration_s)+' seconds.'
    text+=' Apply the specified initial states and prescribed controls; let the subsequent interactions follow from them.'
    text+=' Physical input parameters:\n'+json.dumps(parameters,ensure_ascii=True,allow_nan=False,separators=(',',':'))
    validate_text(text)
    return text

def render_facts(facts, *, context=None, variant=1, duration_s=None, required_keys=()):
    """Shared short model text. Complete facts remain in the task metadata.

    Duration/camera/background are configured by the registered media task;
    observation time is not duplicated into the limited text budget.
    """
    from .compact_prompt import build
    return build(facts,variant=variant,required_keys=required_keys)['prompt_en']
def validate_text(text):
    if not isinstance(text,str) or not text.strip():raise ValueError('empty_generation_prompt')
    if re.search(r'[\u3400-\u9fff]',text):raise ValueError('generation_prompt_must_be_english')
    if FORBIDDEN.search(text):raise ValueError('generation_prompt_discloses_reference_outcome_or_boundary')
    return text
def object_facts(objects):
    facts=[]
    if isinstance(objects,list):objects={s.get('name',f'object_{i+1}'):s for i,s in enumerate(objects)}
    if not isinstance(objects,dict):return facts
    for name,obj in objects.items():
        if not isinstance(obj,dict):continue
        for key in sorted(OBJECT_FIELDS):
            units={'mass':'kg','size':'m','radius':'m','height':'m','position':'m',
                   'initial_velocity':'m/s','initial_angular_velocity':'rad/s',
                   'linear_damping':'1/s','angular_damping':'1/s'}
            if key in obj and numeric(obj[key]):facts.append([name+'.'+key,'',obj[key],units.get(key,'')])
        pose=obj.get('pose',{})
        for key,unit in [('position','m'),('euler_xyz','degrees'),('quaternion','')]:
            if key in pose and numeric(pose[key]):facts.append([name+'.initial_'+key,'',pose[key],unit])
        for key in ['initial_velocity','initial_angular_velocity']:
            v=obj.get('motion',{}).get(key)
            if numeric(v):facts.append([name+'.'+key,'',v,'m/s' if key=='initial_velocity' else 'rad/s'])
    return facts
def declared_item_facts(item):
    """Only declared initial fields are read, never free-form source captions."""
    facts=list(item.get('generation_parameter_facts',[]))
    if not facts and item.get('generation_prompt'):
        raise ValueError('structured_english_prompt_upgrade_required: attach generation_parameter_facts from the exact English video/release catalog; free-form captions are not a complete parameter source')
    if not facts:
        g=item.get('gravity',item.get('requested_gravity_mps2'))
        if numeric(g):facts.append(['gravity','',g,'m/s^2'])
        facts+=object_facts(item.get('initial_objects',item.get('scene',{}).get('objects',{})))
        facts+=object_facts({'target_object':item['object']}) if isinstance(item.get('object'),dict) else []
    if not facts:raise ValueError('missing_declared_generation_physical_inputs')
    return facts

def from_item(item):
    if 'known_conditions' in item:
        c=item['known_conditions'];variant=item.get('prompt_variant',1)
        if variant not in (1,2,3):raise ValueError('invalid_prompt_variant')
        if c['source_video_sha256']!=item.get('sha256'):
            raise ValueError('condition_prompt_source_video_mismatch')
        text=validate_text(c['prompt_variants_en'][variant-1])
        if sha(text)!=c['prompt_variant_sha256'][variant-1]:
            raise ValueError('condition_prompt_hash_mismatch')
        return text
    if 'generation_prompt_variants_en' in item:
        return bound_variant(item)
    if item.get('external_control_inputs') or item.get('external_control_disclosure'):
        raise ValueError('control_aware_versioned_prompt_required')
    return render_facts(declared_item_facts(item),variant=item.get('prompt_variant',1),required_keys=item.get('generation_required_parameter_keys',()))

def parameter_facts_sha(facts):
    return sha(json.dumps(facts,ensure_ascii=True,sort_keys=True,separators=(',',':')))

def bound_variant(item):
    """Use the released control-aware text; refuse changed numeric input facts."""
    facts=item.get('generation_parameter_facts')
    if not facts or parameter_facts_sha(facts)!=item.get('generation_parameter_facts_sha256'):
        raise ValueError('versioned_prompt_parameter_binding_mismatch')
    texts=item['generation_prompt_variants_en'];hashes=item.get('generation_prompt_variant_sha256',[])
    if len(texts)!=3 or len(hashes)!=3:raise ValueError('three_bound_prompt_variants_required')
    for text,digest in zip(texts,hashes):
        if sha(validate_text(text))!=digest:raise ValueError('versioned_prompt_text_binding_mismatch')
    variant=item.get('prompt_variant',1)
    if variant not in (1,2,3):raise ValueError('invalid_prompt_variant')
    return texts[variant-1]
def sha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()

def from_gravity_task(task, member, known):
    """Rebuild from the declared conditioning-frame inputs, not source captions."""
    if 'generation_prompt_variants_en' in task:return bound_variant(task)
    if task.get('generation_parameter_facts'):
        return render_facts(task['generation_parameter_facts'],variant=task.get('prompt_variant',1))
    raise ValueError('english_prompt_task_upgrade_required: use gravity100_en_v1/tasks.jsonl; old captions are not safe generation inputs')

def from_config(config):
    """Project a simulation config onto declared geometry, materials and controls.

    In particular, state frames, event QA, annotations, source labels and all
    reference/search metadata are outside this projection.
    """
    cfg=config.get('physics',{}).get('source_config',config)
    actual=cfg.get('actual_physical_parameters',{})
    facts=[]
    g=actual.get('gravity_mps2',cfg.get('scene_overrides',{}).get('gravity',cfg.get('gravity')))
    if numeric(g):facts.append(['gravity_vector' if isinstance(g,list) else 'gravity','',g,'m/s^2'])
    objects=cfg.get('dynamic_objects',cfg.get('objects',[]))
    if actual.get('bodies'):
        # Merge measured overrides without dropping static support geometry.
        original={o['name']:dict(o) for o in objects} if isinstance(objects,list) else dict(objects)
        for body in actual['bodies']:
            name=body['name'];original[name]={**original.get(name,{}),**{k:v for k,v in body.items() if v is not None}}
        objects=original
    facts+=object_facts(objects)
    allow=re.compile(r'initial|mass|friction|restitution|damping|force|torque|impulse|angle|position|margin|offset|distance|gap|speed|velocity|overlap|stiffness|compression|rest_length|radius|width|length|duration|gravity')
    deny=re.compile(r'expected|outcome|boundary|threshold|theta|branch|contact_first|contact_records|displacement|maximum_motion|end_state|final_state|audit|label|search|repair|source|reference')
    def unit(key,value):
        # Physical type and dimensional suffixes precede incidental words in a name.
        # A gap ratio is not a length; a high-gravity pad size is still a length.
        tail=key.rsplit('.',1)[-1]
        if isinstance(value,bool):return ''
        if 'timeline_target_s.' in key:return 's'
        if 'frame_range' in tail or tail in ['frame_start','frame_end']:return 'frame index'
        if tail.endswith('_frames'):return 'frames'
        if tail.endswith('_count') or 'normalized' in tail or 'quaternion' in tail or re.search(r'(?:^|_)ratio(?:_|$)',tail):return ''
        if 'friction' in tail or 'restitution' in tail:return ''
        if 'momentum' in tail and 'kg_mps' in tail:return 'kg*m/s'
        if 'angular_velocity' in tail:return 'rad/s'
        if tail.endswith(('linear_damping','angular_damping')):return '1/s'
        if tail.endswith('_m') or '_m_before_' in tail or tail.endswith('_m_fixed') or tail=='drink_initial_center_x':return 'm'
        if tail in ['gravity','gravity_vector','gravity_strength'] or tail.startswith('gravity_'):return 'm/s^2'
        # Temporal suffixes take precedence over the mechanism name: a force
        # duration is measured in seconds, an impulse duration is not N*s.
        if 'duration' in key or key.endswith(('_start_s','_end_s')):return 's'
        if 'mps2' in key or 'acceleration' in key:return 'm/s^2'
        if 'nm_per_rad' in key:return 'N*m/rad'
        if 'nms_per_rad' in key:return 'N*m*s/rad'
        if 'kg_m2' in key:return 'kg*m^2'
        if 'rad_s' in key:return 'rad/s'
        if key.endswith('_rad'):return 'rad'
        if 'stiffness' in key:return 'N/m'
        if 'damping_ns' in key:return 'N*s/m'
        if 'force' in key:return 'N'
        if 'torque' in key:return 'N*m'
        if 'impulse' in key:return 'N*s'
        if 'mass' in key:return 'kg'
        if 'speed' in key or 'velocity' in key:return 'm/s'
        if 'deg' in key or 'angle' in key:return 'degrees'
        if 'duration' in key:return 's'
        if 'per_second' in key:return '1/s'
        if any(k in key for k in ['position','margin','offset','distance','gap','overlap','rest_length','radius','width','length','compression']):return 'm'
        return ''
    def physical_tree(obj,prefix):
        if not isinstance(obj,dict):return
        for k,v in obj.items():
            if deny.search(k.lower()):continue
            key=prefix+'.'+k
            if isinstance(v,dict):physical_tree(v,key)
            elif numeric(v) and allow.search(k.lower()):facts.append([key,'',v,unit(key.lower(),v)])
    for key in ['t13_parameters','t14s_parameters','t12_parameters','declared_physical_inputs','spring','actuation']:
        physical_tree(cfg.get(key,{}),key)
    # Prescribed spring and hinge mechanisms are inputs, not observed contacts.
    mechanism_fields={'anchor_world':'m','axis_world':'','rest_length_m':'m',
        'stiffness_n_per_m':'N/m','damping_ns_per_m':'N*s/m','max_force_n':'N',
        'frame_start':'frame index','frame_end':'frame index','target_offset_m':'m',
        'bidirectional':'','detach_on_release':'','hinge_position_world':'m',
        'inertia_kg_m2':'kg*m^2','rest_angle_rad':'rad','stiffness_nm_per_rad':'N*m/rad',
        'damping_nms_per_rad':'N*m*s/rad','max_contact_torque_nm':'N*m',
        'max_speed_rad_s':'rad/s','lower_angle_rad':'rad','upper_angle_rad':'rad',
        'return_anti_chatter_speed_rad_s':'rad/s'}
    for section in ['spring_actuators','joint_spring_actuators','contact_driven_hinges']:
        for i,mechanism in enumerate(cfg.get(section,[])):
            prefix=section+'.'+str(i+1)+'.'+str(mechanism.get('target','body'))
            for key,u in mechanism_fields.items():
                if numeric(mechanism.get(key)):facts.append([prefix+'.'+key,'',mechanism[key],u])
    physical_tree(cfg.get('experiment',{}).get('parameter',{}),'prescribed_parameters')
    forces=actual.get('external_forces',cfg.get('runtime_forces',[]))
    for i,f in enumerate(forces):
        name=str(f.get('target',f'object_{i+1}'))+'.prescribed_force_'+str(i+1)
        for k,u in [('force_world','N'),('force_local','N'),('frame_start','frame index'),('frame_end','frame index'),('start_s','s'),('end_s','s'),('duration_s','s')]:
            if numeric(f.get(k)):facts.append([name+'.'+k,'',f[k],u])
    if not facts:raise ValueError('no_declared_physical_parameters_in_config')
    return facts
