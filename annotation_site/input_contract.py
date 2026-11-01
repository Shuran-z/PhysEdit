"""Formal input identity: released text, selected seed and required image proof."""
import hashlib
from pathlib import Path


def matches_frozen_input(payload, policy):
    if policy.get('schema')=='core100-actual-generation-inputs-v1':
        rule=policy['tasks'].get(payload['clip_id'])
        if not rule:return False
        prompt=payload.get('source',{}).get('generation_metadata',{}).get('prompt')
        variant=payload.get('prompt_variant')
        if variant not in (1,2,3) or not isinstance(prompt,str):return False
        if hashlib.sha256(prompt.encode()).hexdigest()!=rule['prompt_variant_sha256'][variant-1]:return False
        tid=payload.get('source_annotation_task_id',payload.get('id'))
        return any(b['task_id']==tid and b['video_sha256']==payload.get('video_sha256')
                   and b['seed']==payload.get('seed') and b['prompt_variant']==variant
                   for b in rule['registered_outputs'])
    version=payload.get('reference_release_version')
    if version:
        from physedit.core100_release import load
        root,manifest,conditions,_=load(Path(__file__).parent/'resources/active_reference_release.json')
        if version!=manifest['version']:return False
        case=next((c for c in manifest['replacements'] if c['clip_id']==payload['clip_id']),None)
        if not case:return False
        condition=next(c for c in conditions['tasks'] if c['clip_id']==payload['clip_id'])
        prompt=payload.get('source',{}).get('generation_metadata',{}).get('prompt')
        variant=payload.get('prompt_variant')
        if variant not in (1,2,3) or not isinstance(prompt,str):return False
        return (hashlib.sha256(prompt.encode()).hexdigest()==condition['prompt_variant_sha256'][variant-1]
                and payload.get('condition_sha256')==case['condition_sha256']
                and payload.get('reference_video_sha256')==case['video_sha256'])
    rule=policy['tasks'][payload['clip_id']]
    prompt=payload.get('source',{}).get('generation_metadata',{}).get('prompt')
    if not isinstance(prompt,str):return False
    if hashlib.sha256(prompt.encode()).hexdigest()!=rule['prompt_variant_sha256'][int(payload['prompt_variant'])-1]:return False
    if 'required_seed' in policy and payload['seed']!=policy['required_seed']:return False
    expected=rule.get('required_condition_provenance')
    if expected:
        proof=payload.get('source',{}).get('condition_provenance',{})
        if any(proof.get(k)!=v for k,v in expected.items()):return False
    return True
