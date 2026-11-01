"""Versioned Core100 conditions and fail-closed parameter/time contracts."""
import hashlib,json,math
from pathlib import Path

def attach(rows,manifest):
    data=json.loads(Path(manifest).read_text(encoding='utf-8'))
    conditions=data['tasks']
    if len(conditions)!=100 or len({r['clip_id'] for r in conditions})!=100:
        raise ValueError('conditions_require_100_unique_members')
    index={r['clip_id']:r for r in conditions}
    if set(index)!={r['clip_id'] for r in rows}:
        raise ValueError('conditions_membership_changed')
    result=[]
    for row in rows:
        c=index[row['clip_id']]
        if c['source_video_sha256']!=row['sha256'] or c['sample_id']!=row['sample_id']:
            raise ValueError('conditions_video_identity_mismatch:'+row['clip_id'])
        variant=row.get('prompt_variant',1)
        if variant not in (1,2,3):raise ValueError('invalid_prompt_variant')
        texts=c['prompt_variants_en']
        if len(texts)!=3:raise ValueError('conditions_require_three_prompts')
        from .prompt_contract import validate_text
        text=validate_text(texts[variant-1])
        digest=hashlib.sha256(text.encode()).hexdigest()
        if digest!=c['prompt_variant_sha256'][variant-1]:
            raise ValueError('conditions_prompt_hash_mismatch')
        result.append({**row,'known_conditions':c,'conditions_version':data['version'],
                       'prompt_variant':variant,'generation_prompt':text,
                       'generation_parameter_facts':c['prompt_generation_facts'],
                       'prompt_language':'en','prompt_policy':c['prompt_policy'],
                       'prompt_sha256':digest,'generation_prompt_sha256':digest})
    return result

def reference_times(condition,frames):
    clock=condition['clock']
    if clock.get('status')!='verified':raise ValueError('unverified_reference_clock')
    if any(type(f)is not int or f<0 or f>=clock['frame_count'] for f in frames):
        raise ValueError('invalid_reference_frame')
    if any(f<clock['release_frame'] for f in frames):
        raise ValueError('held_prefix_is_not_dynamic_observation')
    if any(b<=a for a,b in zip(frames,frames[1:])):
        raise ValueError('non_increasing_observation_frames')
    return [(f-clock['release_frame'])*clock['physical_dt_s'] for f in frames]

def validate_reference_binding(condition, video_sha256, media_fps):
    """Reject mixing a versioned condition overlay with its parent's video."""
    reference=condition.get('reference',{})
    expected=reference.get('sha256') or reference.get('derivative_sha256') or condition['source_video_sha256']
    if video_sha256!=expected:
        raise ValueError('known_conditions_reference_sha256_mismatch')
    clock=condition.get('clock',{})
    wanted=reference.get('media_fps',clock.get('media_fps'))
    if wanted is not None and (not math.isfinite(media_fps) or abs(media_fps-wanted)>1e-6):
        raise ValueError('known_conditions_reference_media_clock_mismatch')
    return expected

def generated_times(condition,frames,fps,*,time_contract='realtime',legacy_rate_disclosed=False):
    if not math.isfinite(fps) or fps<=0:raise ValueError('invalid_generated_fps')
    if any(type(f)is not int or f<0 for f in frames):raise ValueError('invalid_generated_frame')
    if time_contract=='realtime':return [f/fps for f in frames]
    if time_contract!='legacy_media' or not legacy_rate_disclosed:
        raise ValueError('legacy_rate_requires_explicit_generation_condition')
    clock=condition['clock']
    if clock.get('status')!='verified':raise ValueError('unverified_reference_clock')
    rate=clock['physical_dt_s']*clock['media_fps']
    return [f/fps*rate for f in frames]

def effective_friction(pair):
    if pair.get('status')!='verified':raise ValueError('contact_friction_not_verified')
    values=[pair.get('material_a'),pair.get('material_b')]
    if any(type(v) not in (float,int) or not math.isfinite(v) or v<0 for v in values):
        raise ValueError('contact_material_missing')
    if pair.get('combine_rule')!='genesis_max_floor_0.01':
        raise ValueError('contact_combine_rule_unverified')
    return max(*values,0.01)

def require_parameter_truth(condition,parameter,*,pair=None):
    if condition.get('configuration_status')=='conflicting_historical_versions':
        raise ValueError('configuration_provenance_conflict')
    if parameter=='contact_friction':return effective_friction(pair or {})
    if parameter=='object_friction' and pair:
        effective_friction(pair)
        if pair['material_a']<max(pair['material_b'],0.01):
            raise ValueError('object_friction_masked_at_selected_contact')
    if parameter not in condition.get('verified_parameter_truth',{}):
        raise ValueError('parameter_truth_not_verified:'+parameter)
    return condition['verified_parameter_truth'][parameter]
