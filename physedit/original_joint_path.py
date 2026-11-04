"""Explicit coordinates on an ordered, released joint-parameter sweep.

Distances are along that path after per-input range normalization. They are
neither nearest distances in the full parameter space nor single-input effects.
"""
import bisect
import copy
import math


T11_KEYS = ('driver_initial_speed_mps', 'relay_case_gap_m', 'case_edge_margin_m',
            'relay_block_mass_kg', 'case_friction_coefficient')


def t11_case_friction_intervention(config, source_vector, value):
    """Vary the original G input alone; preserve its source and all forces."""
    if not math.isfinite(value) or not .01 <= value <= 5.:
        raise ValueError('case_friction_outside_material_domain')
    c=copy.deepcopy(config)
    p=c['experiment']['parameter']
    if p['parameter_value'] != source_vector:
        raise ValueError('case_friction_requires_the_original_joint_source')
    if value == source_vector['case_friction_coefficient']:
        return c
    case=next(o for o in c['dynamic_objects'] if o['name']=='t11_eyeglasses_case')
    case['friction']=value
    if isinstance(case.get('material_preset'),dict):case['material_preset']['friction']=value
    p['parameter_value']['case_friction_coefficient']=value
    p['case_friction_coefficient']=value
    return c


def make_joint_path(nodes):
    if len(nodes) < 2 or any(set(node) != set(T11_KEYS) for node in nodes):
        raise ValueError('joint_path_requires_original_five_input_vectors')
    if any(type(x) not in (int, float) or not math.isfinite(x)
           for node in nodes for x in node.values()):
        raise ValueError('joint_path_nonfinite_input')
    spans = {key:max(n[key] for n in nodes)-min(n[key] for n in nodes) for key in T11_KEYS}
    if any(value <= 0 for value in spans.values()):
        raise ValueError('joint_path_degenerate_input_range')
    cumulative = [0.]
    for left, right in zip(nodes, nodes[1:]):
        length = math.sqrt(sum(((right[key]-left[key])/spans[key])**2 for key in T11_KEYS))
        if length <= 0:
            raise ValueError('joint_path_duplicate_adjacent_vectors')
        cumulative.append(cumulative[-1]+length)
    return dict(nodes=copy.deepcopy(nodes), input_ranges={
        key:[min(n[key] for n in nodes),max(n[key] for n in nodes)] for key in T11_KEYS},
        coordinates=[s/cumulative[-1] for s in cumulative],
        unnormalized_length=cumulative[-1], normalization_domain=[0.,1.],
        distance_definition='arc length along the original ordered joint sweep, after per-input range normalization')


def vector_at(path, coordinate):
    if not math.isfinite(coordinate) or not 0 <= coordinate <= 1:
        raise ValueError('joint_path_coordinate_outside_original_path')
    positions=path['coordinates'];nodes=path['nodes']
    for position,node in zip(positions,nodes):
        if coordinate == position:
            return copy.deepcopy(node)
    i=bisect.bisect_right(positions,coordinate)-1
    fraction=(coordinate-positions[i])/(positions[i+1]-positions[i])
    return {key:nodes[i][key]+fraction*(nodes[i+1][key]-nodes[i][key]) for key in T11_KEYS}


def _mapped(vector):
    def lerp(value,low,high,a,b):
        return a+max(0.,min(1.,(value-low)/(high-low)))*(b-a)
    speed=vector['driver_initial_speed_mps']
    return dict(gap=lerp(vector['relay_case_gap_m'],.012,.085,.12,.27),
        margin=lerp(vector['case_edge_margin_m'],.025,.175,.008,.22),
        pre=lerp(speed,1.8,3.6,.18,.30),
        relay=.35+10.*max(0.,vector['relay_block_mass_kg']-.08),
        post=lerp(speed,1.8,3.6,0.,.60),
        delay=int(round(lerp(speed,1.8,3.6,0.,20.))))


def t11_joint_intervention(config, source_vector, target_vector):
    """Apply the released r010 joint recipe, preserving the frozen source."""
    c=copy.deepcopy(config);p=c['experiment']['parameter']
    if p['parameter_value'] != source_vector or set(target_vector) != set(T11_KEYS):
        raise ValueError('original_joint_source_or_target_mismatch')
    objects={o['name']:o for o in c['dynamic_objects']}
    mapped_source=_mapped(source_vector);mapped=_mapped(target_vector)
    if (not math.isclose(p['relay_case_gap_m'],mapped_source['gap'],abs_tol=1e-10) or
            not math.isclose(p['case_edge_margin_m'],mapped_source['margin'],abs_tol=1e-10) or
            objects['t11_relay_pencil_case']['mass'] != source_vector['relay_block_mass_kg'] or
            objects['t11_eyeglasses_case']['friction'] != source_vector['case_friction_coefficient']):
        raise ValueError('original_joint_recipe_does_not_match_source_physics')
    force=next(f for f in c['runtime_forces'] if f['target']=='t11_driver_eraser')
    for field,key in [('force_world','pre'),('force_world_after_first_contact','relay'),
                      ('force_world_relay_phase','relay'),('force_world_after_contact','post')]:
        if not math.isclose(force[field][0],mapped_source[key],abs_tol=1e-10):
            raise ValueError('original_joint_source_force_mismatch:'+field)
    if force['stop_after_contact_delay_frames'] != mapped_source['delay']:
        raise ValueError('original_joint_source_duration_mismatch')
    if target_vector == source_vector:
        return c
    shift=mapped['margin']-mapped_source['margin'];gap_shift=mapped['gap']-mapped_source['gap']
    for name in ('t11_driver_eraser','t11_relay_pencil_case'):
        objects[name]['pose']['position'][0]-=shift+gap_shift
    objects['t11_eyeglasses_case']['pose']['position'][0]-=shift
    for name,field,value in [('t11_relay_pencil_case','mass',target_vector['relay_block_mass_kg']),
                             ('t11_eyeglasses_case','friction',target_vector['case_friction_coefficient'])]:
        objects[name][field]=value
        if isinstance(objects[name].get('material_preset'),dict):
            objects[name]['material_preset'][field]=value
    for field,key in [('force_world','pre'),('force_world_after_first_contact','relay'),
                      ('force_world_relay_phase','relay'),('force_world_after_contact','post')]:
        force[field][0]=mapped[key]
    force['stop_after_contact_delay_frames']=mapped['delay']
    p.update(parameter_value=copy.deepcopy(target_vector),relay_case_gap_m=mapped['gap'],
        case_edge_margin_m=mapped['margin'],pencil_tin_mass_kg=target_vector['relay_block_mass_kg'],
        case_friction_coefficient=target_vector['case_friction_coefficient'],
        driver_force_before_first_contact_n=mapped['pre'],driver_force_between_contacts_n=mapped['relay'],
        driver_force_after_second_contact_n=mapped['post'],driver_force_after_second_contact_frames=mapped['delay'])
    return c
