"""Closed dimensional typing, bounded numeric display and source-proven deduplication."""
import functools,hashlib,json,math,re
from fractions import Fraction
from physedit.compact_prompt import label
from physedit.natural_short_prompt import name as actor_name
from scripts.repair_and_verify_all_prompts import pieces,fact_patterns,match_fact,merge_friction,primary_clause,supplemental_clause,numeric_value
from scripts.build_current_prompt_publication import covered_by_controller
from scripts import full_prompt_config_audit as audit
VERSION='semantic-units-display-dedup-v2-20261102'
SIG=8
RELATIVE_DISPLAY_BOUND=5e-8
NUMBER=re.compile(r'(?<![\w.])[-+]?\d+(?:\.\d+)?(?:/\d+|[eE][-+]?\d+)?')

def expected_unit(key,value):
    k=key.lower();tail=k.rsplit('.',1)[-1]
    if isinstance(value,bool):return ''
    if 'timeline_target_s.' in k:return 's'
    if 'frame_range' in k or tail in ['frame_start','frame_end']:return 'frame index'
    if tail.endswith('_frames'):return 'frames'
    if tail.endswith('_count') or 'quaternion' in k or 'normalized' in k or re.search(r'(?:^|_)ratio(?:_|$)',tail):return ''
    if 'friction' in k or 'restitution' in k:return ''
    if 'momentum' in k and 'kg_mps' in k:return 'kg*m/s'
    if 'angular_velocity' in k:return 'rad/s'
    if tail in ['gravity','gravity_vector','gravity_strength'] or tail.startswith('gravity_'):return 'm/s^2'
    if 'stiffness' in k:return 'N/m'
    if 'damping_ns_per_m' in k:return 'N*s/m'
    if tail.endswith(('linear_damping','angular_damping')):return '1/s'
    if 'impulse' in k and tail.endswith(('_ns','_magnitude_ns')):return 'N*s'
    if tail.endswith('_s'):return 's'
    if 'force' in tail and (tail.endswith(('_n','_newton')) or tail in ['force_peak','force_world','force_local']):return 'N'
    if 'mass' in tail:return 'kg'
    if 'velocity' in tail or 'speed' in tail:return 'm/s'
    if 'euler' in tail or 'angle' in tail or tail.endswith('_deg'):return 'deg'
    if tail.endswith('_m') or '_m_before_' in tail or tail.endswith('_m_fixed'):return 'm'
    if tail in ['size','radius','rolling_radius','height','initial_position','initial_xy','initial_x','initial_y','initial_z','center_distance','commanded_travel','book_gap','book_can_gap','can_box_gap','box_cup_gap','cup_edge_margin','release_lateral_offset','lateral_offset','surface_gap','overlap_parameter','drink_initial_center_x','drink_edge_distance']:return 'm'
    raise ValueError('untyped physical fact '+key)

def canonical_old_unit(unit):
    return {'m/s²':'m/s^2','°':'deg','degrees':'deg','dimensionless':'','unitless':''}.get(unit,unit)

def compact_number(token):
    if '/' not in token and '.' not in token and 'e' not in token.lower():return token
    value=float(Fraction(token)) if '/' in token else float(token)
    assert math.isfinite(value)
    text=format(value,f'.{SIG}g')
    if float(text)==0:text='0'
    if '/' in token and len(token)<len(text):return token
    # Long almost-exact decimals become their short values; precise originals remain in metadata.
    assert abs(float(text)-value)<=abs(value)*RELATIVE_DISPLAY_BOUND+1e-300,(token,text)
    return text

def format_numbers(text,changes=None):
    def sub(m):
        before=m[0];after=compact_number(before)
        if changes is not None and before!=after:
            a=float(Fraction(before)) if '/' in before else float(before);b=float(after)
            changes.append({'before':before,'after':after,'absolute_error':abs(a-b),'relative_error':abs(a-b)/abs(a) if a else 0})
        return after
    return NUMBER.sub(sub,text)

def render_value(v):
    if isinstance(v,(list,tuple)):return '['+','.join(render_value(x) for x in v)+']'
    if isinstance(v,bool):return str(v).lower()
    return compact_number(str(v))

def unit_suffix(unit):
    return '' if unit in ['', 'frame index'] else ' '+unit

PROPERTIES=[('initial angular velocity','initial_angular_velocity'),('initial velocity','initial_velocity'),('initial speed mps','initial_speed'),('initial speed','initial_speed'),('mass kg','mass'),('mass','mass'),('material friction','friction'),('friction','friction'),('restitution','restitution')]
def semantic_fact(key,value,ctx):
    """Resolve only actor aliases whose named property agrees with an actual body."""
    if key in ['gravity','gravity_vector'] or key.endswith('gravity_magnitude_mps2'):
        v=abs(value[2]) if isinstance(value,list) and value[:2]==[0,0] else value
        return ('world','gravity',json.dumps(v)),['world.gravity']
    title=label(key).lower()
    for suffix,prop in PROPERTIES:
        if title.endswith(' '+suffix):
            subject=title[:-len(suffix)].strip();break
    else:return None,[]
    parent=key.rsplit('.',1)[0] if '.' in key else None;candidates=[]
    for who,o in ctx[1].items():
        aliases={label(who).lower(),actor_name(who).lower()}
        direct=parent==who
        named=any(a==subject or a.endswith(' '+subject) for a in aliases)
        if not (direct or named):continue
        target=o.get('motion',{}).get(prop) if prop.startswith('initial_') else o.get(prop)
        if prop=='initial_speed':
            velocity=o.get('motion',{}).get('initial_velocity');target=audit.norm(velocity) if velocity is not None else None
        if target is not None and audit.equal(value,target):candidates.append(who)
    if len(candidates)!=1:return None,[]
    who=candidates[0];return (who,prop,json.dumps(value,separators=(',',':'))),[who+'.'+prop]

def controller_coverage(key,value,ctx,used):
    if covered_by_controller(key,value,ctx,used):return 'existing_source_controller_binding'
    semantic,identities=semantic_fact(key,value,ctx)
    if semantic:
        who,prop,_=semantic
        if prop in ['initial_velocity','initial_speed'] and who+'.initial_velocity' in used:return 'same_actor_source_velocity'
        if prop=='initial_angular_velocity' and who+'.initial_angular_velocity' in used:return 'same_actor_source_angular_velocity'
    if key.endswith(('.control_tilt_start_deg','.control_tilt_end_deg')):
        who=key.rsplit('.',1)[0];m=ctx[1].get(who,{}).get('motion',{});field='start_angle_deg' if 'start_deg' in key else 'end_angle_deg'
        if who+'.motion' in used and audit.equal(value,m.get(field)):return 'same_actor_scripted_tilt_endpoint'
    if key.endswith('.force_peak'):
        who=key.rsplit('.',1)[0];forces=ctx[2].get('external_forces',ctx[0].get('runtime_forces',[]))
        fs=[f for f in forces if f.get('target')==who]
        if 'runtime_forces.'+who in used and fs and audit.equal(value,max(audit.norm(f['force_world']) for f in fs)):return 'same_actor_source_force_peak'
    if key.split('.')[-1]=='commanded_extraction_speed_mps':
        candidates=[who for who,o in ctx[1].items() if who.endswith('removable_support_bar') and who+'.initial_velocity' in used and audit.equal(value,audit.norm(o.get('motion',{}).get('initial_velocity',[])))]
        if len(candidates)==1:return 'support_bar_command_is_source_initial_speed'
    return None

def classify_clause(clause,row,raw,c,ctx,pats):
    match=match_fact(clause,pats)
    if match:
        key,parsed,exact,prefix,suffix=match;assert audit.equal(parsed,exact),(key,parsed,exact)
        return dict(kind='fact',key=key,parsed=parsed,exact=exact,prefix=prefix,suffix=suffix)
    if merge_friction(clause,row['parameter_facts']):return dict(kind='merged_friction')
    if primary_clause(clause,row,raw):return dict(kind='primary')
    if supplemental_clause(clause,row,c,ctx):return dict(kind='supplemental')
    if NUMBER.search(clause):raise ValueError('unclassified numeric clause '+clause)
    return dict(kind='lead')

def repair_variant(text,row,raw,c,ctx,source,old_patterns):
    controls=source['source_control_clauses'];used=set(source.get('control_keys',[]));masked=text
    for i,control in sorted(enumerate(controls),key=lambda x:-len(x[1])):
        assert control in masked,control
        masked=masked.replace(control,f'@@CONTROL_{i}@@.')
    facts={f[0]:f for f in row['parameter_facts']};out=[];proof=[];changes=[];removed=[];seen={};controller_atoms=set()
    memo=source.setdefault('_semantic_clause_cache',{});coverage_memo=source.setdefault('_coverage_cache',{});semantic_memo=source.setdefault('_semantic_identity_cache',{})
    for control in controls:controller_atoms.update(pieces(format_numbers(control)))
    for clause in pieces(masked):
        m=re.fullmatch(r'@@CONTROL_(\d+)@@\.',clause)
        if m:
            value=format_numbers(controls[int(m[1])],changes)
            for atom in pieces(value):
                # Context-dependent fragments remain attached to their preceding controller.
                identity=('controller',atom)
                if identity in seen:
                    removed.append(dict(kind='exact_controller_atom_duplicate',before=atom,covered_by=seen[identity]));continue
                seen[identity]=len(out);out.append(atom);proof.append(dict(kind='controller',source_index=int(m[1]),output=atom))
            continue
        if clause not in memo:memo[clause]=classify_clause(clause,row,raw,c,ctx,old_patterns)
        info=memo[clause];kind=info['kind'];new=clause;semantic=None
        if kind=='fact':
            key=info['key'];f=facts[key]
            if key not in coverage_memo:coverage_memo[key]=controller_coverage(key,f[-2],ctx,used)
            covered=coverage_memo[key]
            if covered:
                removed.append(dict(kind='fact_covered_by_controller',key=key,before=clause,reason=covered));continue
            unit=expected_unit(key,f[-2]);old_suffix=info['suffix']
            # The parser has already isolated label/value/unit. Never perform an arbitrary unit substring edit.
            old_unit=canonical_old_unit(f[-1]);old_text_unit=unit_suffix(old_unit)
            assert old_suffix.endswith(old_text_unit+'.') if old_text_unit else old_suffix=='.'
            suffix=unit_suffix(unit)+'.'
            new=info['prefix']+render_value(info['parsed'])+suffix
            format_numbers(clause,changes)
            if key not in semantic_memo:semantic_memo[key]=semantic_fact(key,f[-2],ctx)[0]
            semantic=semantic_memo[key]
        else:new=format_numbers(clause,changes)
        identity=('fact_semantic',semantic) if semantic else ('literal',new.lower())
        if identity in seen:
            removed.append(dict(kind='same_actor_property_duplicate' if semantic else 'exact_clause_duplicate',key=info.get('key'),before=clause,covered_by=seen[identity]));continue
        if new in controller_atoms:
            removed.append(dict(kind='literal_covered_by_controller',before=clause));continue
        seen[identity]=len(out);out.append(new);proof.append(dict(kind=kind,key=info.get('key'),before=clause,output=new))
    result=' '.join(out)
    assert len(out)==len(set(out)),'exact duplicate sentence survives'
    assert format_numbers(result)==result,'noncanonical number survives'
    for control in controls:
        for atom in pieces(format_numbers(control)):assert atom in out,('controller atom lost',atom)
    return result,dict(clauses=proof,removed=removed,numeric_changes=changes)
