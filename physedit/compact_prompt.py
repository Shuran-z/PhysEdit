"""One shared short English prompt for all models; full facts stay in metadata.

SentencePiece vocabularies are pinned under prompt_tokenizers. Counts include
EOS. Selection removes complete optional facts, never a substring of the prompt.
No future-state, outcome, filename or branch text is read.
"""
import functools
import hashlib
import json
import re
from pathlib import Path

VERSION='core100-aligned-compact-three-prompts'
TOKEN_BUDGET=120  # including EOS, with eight tokens spare against LTX's 128
MODEL_BUDGETS={'ltx':120,'cogvideox':218,'wan':504}
LABEL_VERSION='compact-labels-v2'

@functools.lru_cache(maxsize=1)
def tokenizers():
    import sentencepiece as sp
    root=Path(__file__).with_name('prompt_tokenizers')
    return {name:sp.SentencePieceProcessor(model_proto=(root/file).read_bytes())
            for name,file in [('t5','t5.model'),('umt5','umt5.model')]}

@functools.lru_cache(maxsize=32768)
def counts(text):
    t=tokenizers();a=len(t['t5'].encode(text,out_type=int))+1;b=len(t['umt5'].encode(text,out_type=int))+1
    return {'ltx':a,'cogvideox':a,'wan':b}

def label(key):
    s=str(key).lower()
    s=re.sub(r'\bt\d+s?(?:v\d+)?_', '',s)
    s=re.sub(r'^(?:prescribed_parameters|declared_physical_inputs|t\d+s?_parameters)\.', '',s)
    s=re.sub(r'^(spring_actuators|joint_spring_actuators|contact_driven_hinges)\.\d+\.', 'spring.',s)
    replacements={
      'initial_angular_velocity':'initial angular velocity','initial_velocity':'initial velocity',
      'initial_speed_toward_laptop':'initial speed toward laptop',
      'initial_speed_mps':'initial speed','initial_speed':'initial speed',
      'initial_yaw_deg':'initial yaw','center_distance':'center distance',
      'material_friction':'friction','friction_coefficient':'friction',
      'coefficient':'','collision_slab':'surface','tabletop_collision':'table',
      'sliding_book':'book','impulsed_book':'book','driver_book':'book',
      'upper_edge_can':'upper can','lower_edge_phone':'lower phone',
      'closed_laptop':'laptop','floor_phone':'phone','chain_':'',
      'commanded_extraction':'support extraction','commanded_travel':'prescribed travel',
      'force_world':'world force','force_local':'local force','prescribed_force_':'force ',
      'max_force_n':'max force','stiffness_n_per_m':'stiffness','damping_ns_per_m':'damping',
      'release_position_along_ramp_m':'ramp release position','frame_start':'start frame','frame_end':'end frame',
      'gravity_vector_mps2':'gravity','gravity_vector':'gravity','gravity_mps2':'gravity',
    }
    for a,b in replacements.items():s=s.replace(a,b)
    s=re.sub(r'_(?:mps|kg|deg|m|n|s|fixed)$','',s)
    s=s.replace('_',' ').replace('.',' ')
    return ' '.join(s.split())

def priority(key):
    k=key.lower()
    if 'gravity' in k:return 0
    # Actual body states/controls outrank duplicated historical declarations.
    if any(t in k for t in ['force_world','force_local','max_force_n']):return 5
    if 'initial_velocity' in k or 'initial_speed' in k:return 6 if not k.startswith('prescribed_parameters.') else 14
    if any(t in k for t in ['frame_start','frame_end','start_s','end_s','duration_s']):return 8
    if any(t in k for t in ['commanded','extraction','force_peak','support_pull_force']):return 9
    if any(t in k for t in ['edge_distance','edge_gap','gap_width','throat_width','overlap_length','lateral_offset','eccentricity','initial_yaw','ramp_angle','support_angle','contact_position_normalized','book_can_gap','can_box_gap','box_cup_gap','cup_edge_margin','release_position_along_ramp']):return 10
    if 'prescribed_parameters.' in k and any(t in k for t in ['gap','angle','position','offset','margin','speed','velocity']):return 16
    if any(t in k for t in ['spring','stiffness','damping_ns']):return 18
    if any(t in k for t in ['static_friction','dynamic_friction','surface_friction','folder_surface','tray_friction']):return 20
    if k.endswith('.mass') or 'mass_kg' in k:return 30
    if 'friction' in k:return 32
    if any(t in k for t in ['center_distance','initial_angle','initial_x','initial_y','initial_z']):return 25
    if 'restitution' in k:return 40
    # Detailed poses, dimensions and solver/support controls remain in metadata.
    return 90

def number(v):
    if isinstance(v,bool):return 'true' if v else 'false'
    if isinstance(v,(list,tuple)):return '['+','.join(number(x) for x in v)+']'
    # Strip only an exact integer's redundant .0. No approximate rounding.
    if isinstance(v,float) and v.is_integer():return str(int(v))
    return json.dumps(v,allow_nan=False,separators=(',',':'))

def sentence(key,value,unit):
    name=label(key);u=str(unit).replace('m/s²','m/s^2').replace('°','deg').replace('degrees','deg')
    if u in ['dimensionless','frame index']:u=''
    if name=='gravity' and isinstance(value,(list,tuple)) and len(value)==3 and value[0]==0 and value[1]==0:
        value=abs(value[2])  # vertical gravity strength, not a rounded parameter
    return name.capitalize()+' '+number(value)+((' '+u) if u else '')+'.'

def build(facts,*,required_keys=(),variant=1,lead_variants=None,model_budgets=None):
    from .prompt_contract import validate_text,numeric
    required_keys=set(required_keys)
    budgets=model_budgets or MODEL_BUDGETS
    if set(budgets)!=set(MODEL_BUDGETS):raise ValueError('all_model_token_budgets_required')
    source=[]
    for f in facts:
        if len(f)!=4 or not numeric(f[2]):raise ValueError('invalid_compact_physical_fact')
        key,_,value,unit=f;source.append((key,value,unit))
    if not source:raise ValueError('missing_compact_physical_inputs')
    # Initial-only quantities are explicitly selected. Event/search/audit fields
    # are not eligible even if introduced by a future metadata schema.
    deny=re.compile(r'expected|outcome|boundary|threshold|theta|branch|contact_first|contact_records|final_state|end_state|audit|label|search|repair|reference|before_first_contact|between_contacts|after_second_contact')
    candidates=[(i,k,v,u) for i,(k,v,u) in enumerate(source) if not deny.search(k.lower())]
    candidates.sort(key=lambda r:(0 if r[1] in required_keys else priority(r[1]),r[0]))
    leads=lead_variants or {1:'Continue the scene; fixed camera.',2:'Continue this scene with a fixed camera.',3:'Fixed camera; continue the physical motion.'}
    if set(leads)!={1,2,3}:raise ValueError('three_control_leads_required')
    for lead in leads.values():validate_text(lead)
    text=leads[variant];selected=[];seen=set();parts=[]
    for i,key,value,unit in candidates:
        if priority(key)>=90 and key not in required_keys:continue
        if ('initial_velocity' in key or 'initial_angular_velocity' in key) and isinstance(value,(list,tuple)) and not any(value) and key not in required_keys:
            continue  # Rest is visible in the initial frame; exact zeros stay in metadata.
        content=sentence(key,value,unit)
        # Deduplicate the same declared quantity/value, not distinct objects.
        signature=(label(key),json.dumps(value),unit)
        if signature in seen or content in seen:continue
        # A prescribed legacy scalar must not override actual body velocity.
        if key.startswith('prescribed_parameters.') and any(x in key for x in ['initial_speed','initial_velocity','gravity']):
            if any(priority(k)<=6 and ('initial_velocity' in k or 'initial_speed' in k) for _,k,_,_ in selected):continue
        trial=text+' '+content
        trials=[lead+' '+' '.join(parts+[content]) for lead in leads.values()]
        if any(n>budgets[model] for candidate in trials for model,n in counts(candidate).items()):
            if key in required_keys:raise ValueError('required_intervention_exceeds_compact_budget:'+key)
            continue
        text=trial;parts.append(content);selected.append((i,key,value,unit));seen.add(signature);seen.add(content)
    if required_keys-set(k for _,k,_,_ in selected):raise ValueError('missing_required_intervention')
    if not selected:raise ValueError('no_physical_input_fits_compact_budget')
    validate_text(text)
    result={'prompt_en':text,'prompt_language':'en','prompt_policy':VERSION,
            'prompt_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'prompt_token_counts':counts(text),'token_budget':budgets['ltx'],
            'selected_parameter_keys':[k for _,k,_,_ in selected],
            'omitted_parameter_keys':[k for i,(k,_,_) in enumerate(source) if i not in {x[0] for x in selected}],
            'full_parameters_location':'parameter_facts; metadata only, not a model input'}
    # Default generation follows Core100's compact three-lead format. Never
    # silently route a compact request through the superseded v7 renderer.
    return result

def build_variants(facts,*,required_keys=(),lead_variants=None,model_budgets=None):
    variants=[build(facts,required_keys=required_keys,variant=i,lead_variants=lead_variants,model_budgets=model_budgets) for i in (1,2,3)]
    assert all(v['selected_parameter_keys']==variants[0]['selected_parameter_keys'] for v in variants)
    return {**variants[0], 'default_variant':1,
            'prompt_variants_en':[v['prompt_en'] for v in variants],
            'prompt_variant_token_counts':[v['prompt_token_counts'] for v in variants],
            'prompt_variant_sha256':[v['prompt_sha256'] for v in variants]}
