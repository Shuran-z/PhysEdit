"""Complete missing release prompts from bound inputs, without changing media or Core100."""
import collections
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from physedit.prompt_contract import from_config, validate_text, parameter_facts_sha
from physedit.focused_prompt import build_focused, LIMITS
from physedit.compact_prompt import counts, number

ROOT = REPO.parent / 'release_72000_active'
OUT = ROOT / 'prompt_completion_20261029'


def read(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def write(path, rows):
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row, ensure_ascii=False) + '\n')


def select(facts, required, disclosure, optional=()):
    """Fit all three full texts together; never truncate or drop required controls."""
    row = dict(parameter_facts=facts, selected_parameter_keys=list(required),
               prompt_variant_sha256=[], external_control_disclosure={'disclosure':disclosure})
    built = build_focused(row)
    for key in optional:
        if key in row['selected_parameter_keys']:continue
        trial = {**row, 'selected_parameter_keys':row['selected_parameter_keys']+[key]}
        try:update = build_focused(trial)
        except ValueError as exc:
            if not str(exc).startswith('focus_budget_exceeded:'):raise
        else:row, built = trial, update
    return {**row, **built, 'prompt_language':'en', 'required_parameter_keys':list(required),
            'parameter_facts_sha256':parameter_facts_sha([[k,'',v,u] for k,v,u in facts]),
            'external_control_disclosure':{'disclosure':disclosure}}


def genesis_inputs(config):
    facts = [[k,v,u] for k,_,v,u in from_config(config)]
    exp = config['experiment'];scene=exp['scene_family_id']
    gravity=abs(config['scene_overrides']['gravity'][2]);fps=config['render']['fps']
    hold=config['render']['pre_static_frames']
    facts.append(['gravity_strength',gravity,'m/s^2'])
    assert fps==30 and hold==24
    if scene=='T18':
        controlled=[o for o in config['dynamic_objects'] if o.get('motion',{}).get('type')=='scripted_keyframes']
        assert len(controlled)==1
        body=controlled[0];keys=body['motion']['keyframes'];a,b=exp['extraction_motion_frames']
        start=next(k for k in keys if k['frame']==a);end=next(k for k in keys if k['frame']==b)
        travel=exp['extraction_travel_m'];direction=exp['extraction_direction']
        assert math.isclose(abs(end['position'][0]-start['position'][0]),travel,abs_tol=1e-12)
        assert (end['position'][0]<start['position'][0])==(direction=='left')
        assert body['fixed'] is True and a==30 and b==90
        assert all(k['position']==end['position'] and k['euler_xyz']==end['euler_xyz'] for k in keys if k['frame']>=b)
        yaw=end['euler_xyz'][2]-start['euler_xyz'][2]
        disclosure=(f"Book {exp['extraction_position_one_based']} of {exp['book_count']} stays kinematic. "
                    f"Off-screen quintic withdrawal {direction} {number(travel)} m, yaw {number(yaw)} deg, "
                    f"active frames {a}-{b}; then held. {hold} static frames; {fps} fps.")
        facts += [['book_interface_friction',exp['dynamic_friction'],''],
                  ['overlap_parameter',exp['overlap_length_m'],'m']]
        # Both physical axes are retained in every view; complete geometry stays in facts.
        required=['gravity_strength','book_interface_friction','overlap_parameter']
        result=select(facts,required,disclosure)
        result['external_control_inputs']={'actor':body['name'],'motion':body['motion'],
            'kinematic_throughout':True,'native_frame_clock':'active_simulation_frames',
            'pre_static_frames':hold,'render_fps':fps}
    else:
        assert scene=='T19' and not config.get('runtime_forces')
        objs=config['dynamic_objects'];n=len(objs);angle=exp['chain_angle_deg']
        axis=[math.cos(math.radians(angle)),math.sin(math.radians(angle))]
        speed=exp['striker_initial_speed_mps'];drift=exp['target_drift_max_mps'];topo=exp['collision_topology']
        signed=[]
        for i,obj in enumerate(objs):
            if i==0 and topo!='linear_right_to_left':v=speed
            elif i==n-1 and topo in ['linear_right_to_left','dual_converging']:v=-speed
            elif topo in ['linear_left_to_right','diagonal_chain']:v=drift*(n-1-i)/max(n-1,1)
            elif topo=='linear_right_to_left':v=-drift*i/max(n-1,1)
            else:
                mid=(n-1)/2
                v=1.20*(mid-i)/max(mid,1.0)
            actual=obj['motion']['initial_velocity']
            expected=[axis[0]*v,axis[1]*v,0.0]
            assert all(math.isclose(a,b,rel_tol=1e-14,abs_tol=1e-14) for a,b in zip(actual,expected)),(obj['name'],actual,expected)
            signed.append(v)
        facts += [['axis_initial_velocities',signed,'m/s'],['axis_angle',angle,'deg'],
                  ['impact_eccentricity',exp['impact_eccentricity_m'],'m'],
                  ['target_mass_ratio',exp['mass_ratio'],''],['body_restitution',exp['restitution'],''],
                  ['body_masses',[o['mass'] for o in objs],'kg'],
                  ['inter_object_gap',exp['initial_inter_object_gap_m'],'m']]
        parameter={'impact_eccentricity':'impact_eccentricity','mass_ratio':'target_mass_ratio','restitution':'body_restitution'}[exp['parameter']['parameter_name']]
        disclosure=f"Body order follows the axis. Initial motion starts after {hold} static frames at {fps} fps; no continuous drive."
        restitution_patch=exp['parameter']['parameter_name']=='restitution'
        if restitution_patch:
            disclosure=(f"Axis body order. Start after {hold} static frames, {fps} fps. "
                        'First adjacent contacts receive analytic restitution impulses.')
        result=select(facts,['gravity_strength','axis_initial_velocities','axis_angle',parameter],disclosure,
                      ['inter_object_gap','body_restitution','target_mass_ratio','body_masses'])
        result['initial_velocity_representation']={'type':'signed_speed_along_declared_axis',
            'ordered_actor_ids':[o['name'] for o in objs],'axis_angle_deg':angle,
            'exact_world_velocities':[o['motion']['initial_velocity'] for o in objs],
            'reconstruction_verified':True,'absolute_verification_tolerance':1e-14}
        result['external_control_inputs']={'runtime_forces':[],'prescribed_paths':[],
            'pre_static_frames':hold,'render_fps':fps,'initial_velocity_applied_after_static_hold':True}
        if restitution_patch:
            result['external_control_inputs']['analytic_contact_impulse']={
                'actor_pairs':exp['required_contact_pairs'],'coefficient':exp['parameter']['parameter_value'],
                'implementation':'one_time_per_pair_on_first_detected_contact_with_positive_normal_closing_speed',
                'source_evidence':'renderer_source_evidence/render_sample.py',
                'source_evidence_scope':'current_renderer_snapshot_not_historical_binary_attestation'}
    return result


def t14s_inputs(source):
    inp=source['declared_inputs'];m=source['matrix']
    force=inp['spring_force_n'];k=max(.52,force*1.02/.55);d=.03*math.sqrt(k/.52)
    assert inp['spring_stiffness_n_per_m']==k and inp['spring_damping_ns_per_m']==d
    facts=[['gravity_strength',inp['gravity_mps2'],'m/s^2'],['spring_force_cap',force,'N'],
           ['spring_stiffness',k,'N/m'],['spring_damping',d,'N*s/m'],
           ['marker_mass',.018,'kg'],['marker_yaw',6.0,'deg'],['eraser_mass',.012,'kg'],
           ['ball_mass',.012,'kg'],['gate_mass',.025,'kg']]
    disclosure=('Off-screen spring force drives the marker for 11.375 active frames after 24 static frames at 30 fps. '
                'All bodies initially rest; no prescribed path.')
    result=select(facts,['gravity_strength','spring_force_cap','spring_stiffness','spring_damping'],
                  disclosure,['marker_yaw','marker_mass','eraser_mass','ball_mass','gate_mass'])
    result['initial_objects']=source['initial_objects']
    result['external_control_inputs']={'type':'capped_compression_spring_plus_velocity_damping',
        'force_axis':[1,0,0],'target':'t14s_marker','active_frames':[0,11.375],
        'pre_static_frames':24,'render_fps':30,'spring_attachment_offset_x_m':-.09,
        'spring_anchor_x_m':-.59,'spring_rest_length_m':.65,'force_cap_n':force,
        'stiffness_n_per_m':k,'damping_ns_per_m':d,
        'other_linear_drag_coefficients':[.018,.035,0,0],
        'hinge_drive':{'stiffness':.003,'damping':.0008,'max_force':.14,'target_angle':0}}
    return result


def main():
    OUT.mkdir(exist_ok=True)
    sources={r['sample']:r for r in read(ROOT/'supplement_source_configs.jsonl.gz')}
    t14s={r['sample_id']:r for r in read(ROOT/'t14s_actual_inputs_20261029.jsonl.gz')}
    bindings={r['video_id']:r for r in read(ROOT/'supplement_prompt_input_bindings.jsonl.gz')}
    cache={};patches=[];errors=[];stats=collections.Counter()
    source_manifest=ROOT/'publication_20261029/videos.jsonl.gz'
    with gzip.open(source_manifest,'rt',encoding='utf-8') as f:
        for line in f:
            row=json.loads(line)
            if row.get('prompt_variants_en'):continue
            sid=row['native_sample_id']
            try:
                if sid not in cache:
                    if row['scene']=='T14S':
                        src=t14s[sid];built=t14s_inputs(src)
                        evidence={k:src[k] for k in ['trajectory_sha256','renderer_source_path','renderer_source_sha256']}
                    else:
                        src=sources[sid];built=genesis_inputs(src['config'])
                        evidence={k:src[k] for k in ['source_path','source_sha256']}
                    cache[sid]={**built,'source_input_evidence':evidence}
                update={**cache[sid],'video_id':row['video_id'],'native_sample_id':sid,
                    'scene':row['scene'],'engine':row['engine'],'camera':row['camera'],
                    'video_sha256':row['sha256'],'prompt_binding_status':'BOUND_ACTUAL_INPUTS_THREE_FOCUS',
                    'prompt_completion_version':'72000-prompt-completion-v1-20261029'}
                if row['video_id'] in bindings:
                    b=bindings[row['video_id']]
                    assert b['video_sha256']==row['sha256']
                    update['render_source_binding']={k:b[k] for k in ['runtime_config_binding','source_link_status','actual_timing']}
                for text,c,h in zip(update['prompt_variants_en'],update['prompt_variant_token_counts'],update['prompt_variant_sha256']):
                    validate_text(text);assert counts(text)==c and hashlib.sha256(text.encode()).hexdigest()==h
                    assert all(c[k]<=LIMITS[k] for k in LIMITS)
                patches.append(update);stats[row['scene']]+=1
            except Exception as exc:
                errors.append({'sample_id':sid,'video_id':row['video_id'],'error':str(exc)})
    write(OUT/'prompt_patch.jsonl.gz',patches)
    (OUT/'errors.json').write_text(json.dumps(errors,indent=2),encoding='utf-8')
    summary={'completed_videos':len(patches),'groups':len(cache),'per_scene':dict(stats),'errors':len(errors),
             'variant_count':3*len(patches),'source_manifest_sha256':hashlib.sha256(source_manifest.read_bytes()).hexdigest(),
             'patch_sha256':hashlib.sha256((OUT/'prompt_patch.jsonl.gz').read_bytes()).hexdigest(),
             'core100_changed':False,'existing_prompts_changed':False}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({**summary,'error_examples':errors[:3]}))


if __name__=='__main__':main()
