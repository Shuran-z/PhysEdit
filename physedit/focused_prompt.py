"""Three complementary input views; never read event outcomes or reference labels."""
import copy, hashlib, re
from .compact_prompt import counts, label, number
from .prompt_contract import validate_text

VERSION='english-three-focus-declared-inputs-v7-20261023'
FOCI=['scene_and_initial_conditions','prescribed_intervention_timeline','physical_conditions']
LIMITS={'ltx':128,'cogvideox':226,'wan':512}

def category(key):
    k=key.lower()
    if any(x in k for x in ['gravity','friction','mass','restitution','damping','stiffness']):return 'physical'
    if any(x in k for x in ['force','impulse','commanded','control_','duration','start_time','end_time','frame','extraction','withdrawal','prescribed travel','release_time','dynamics_start']):return 'control'
    return 'initial'

def clause(f,short=False):
    k,v,u=f; name=label(k)
    name=name.replace('material friction','friction').replace('frozen tabletop surface','tabletop')
    if short:
        name=name.replace('initial velocity','initial v').replace('initial speed','initial speed').replace('contact position normalized','normalized contact position')
        name=name.replace('support pull force magnitude','support pull force').replace('support pull force duration','support pull duration').replace('force peak','peak force')
        name=name.replace('prescribed parameters ','').replace('background material friction','background friction')
    u=str(u).replace('m/s²','m/s^2').replace('degrees','deg').replace('°','deg')
    if u in ['dimensionless','frame index']:u=''
    if name=='gravity' and isinstance(v,(list,tuple)) and len(v)==3 and v[:2]==[0,0]:v=abs(v[2])
    return name.capitalize()+' '+number(v)+((' '+u)if u else '')+'.'

def build_focused(row, *, four=False):
    raw=row['prompt_generation_facts'] if four else row['parameter_facts']
    facts=[[f[0],f[2],f[3]]for f in raw]if four else raw
    selected=row['selected_parameter_keys']; index={f[0]:f for f in facts}
    if not set(selected)<=set(index):raise ValueError('missing_selected_input')
    selected=list(dict.fromkeys(selected))
    disclosure=row.get('external_control_disclosure',{}).get('disclosure','')
    disclosure=disclosure.replace('Visible spring actuation supplies the prescribed mechanical force.','Visible spring force.').replace('A spring actuator supplies the specified mechanical force.','Spring actuation supplies force.')
    # Native-release v5 tasks explicitly bind start and release in their leads.
    if row.get('control_release_evidence'):
        text=row['prompt_variants_en'][0]
        m=re.search(r'(An off-screen actuator .*? releases it at [\d.]+ s\.)',text)
        if not m:raise ValueError('native_release_disclosure_missing')
        disclosure=m.group(1)
    represented=[]
    if row.get('control_release_evidence'):
        represented=[k for k in selected if any(x in k for x in ['commanded_start_time','control_release_time','external_control_before_release'])]
    def render(short):
        groups={g:[]for g in ['initial','control','physical']}
        for k in selected:
            if k not in represented:groups[category(k)].append(clause(index[k],short))
        initial=' '.join(groups['initial']); control=' '.join(groups['control']); physical=' '.join(groups['physical'])
        # Different organization of the same declared inputs: layout first,
        # intervention plan first, and material/environment conditions first.
        def join(*xs):return ' '.join(x for x in xs if x)
        return [
          join('Fixed camera. Setup:',initial,disclosure,control,'Properties:',physical),
          join('Fixed camera. Control plan:'if disclosure or control else 'Fixed camera. Initial motion:',disclosure,control,'Initial conditions:'if initial else '',initial,physical),
          join('Fixed camera. Physics:',physical,'Setup:'if initial else '',initial,disclosure,control),
        ]
    texts=render(False)
    if any(counts(t)[k]>LIMITS[k]for t in texts for k in LIMITS):texts=render(True)
    ns=[counts(t)for t in texts]
    if any(n[k]>LIMITS[k]for n in ns for k in LIMITS):raise ValueError('focus_budget_exceeded:'+str(ns))
    for t in texts:validate_text(t)
    return {'prompt_policy':VERSION,'prompt_en':texts[0],'prompt_variants_en':texts,
      'prompt_sha256':hashlib.sha256(texts[0].encode()).hexdigest(),
      'prompt_variant_sha256':[hashlib.sha256(t.encode()).hexdigest()for t in texts],
      'prompt_variant_token_counts':ns,'prompt_token_counts':ns[0],
      'prompt_variant_focus':FOCI,'focus_parameter_groups':{g:[k for k in selected if category(k)==g]for g in ['initial','control','physical']},
      'selected_keys_expressed_in_control_disclosure':represented,
      'previous_prompt_variant_sha256':row['prompt_variant_sha256'],'token_budget':128}
