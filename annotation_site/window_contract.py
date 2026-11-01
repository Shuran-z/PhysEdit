"""Observation cutoffs are independent of prompt and native video duration."""
import math


def window_binding(payload, cases):
    rule=cases.get(payload['clip_id'])
    if payload.get('reference_release_version'):
        from pathlib import Path
        from physedit.core100_release import load
        _,manifest,conditions,_=load(Path(__file__).parent/'resources/active_reference_release.json')
        if payload['reference_release_version']!=manifest['version']:
            raise ValueError('reference_release_version_not_registered')
        case=next((c for c in manifest['replacements'] if c['clip_id']==payload['clip_id']),None)
        if not case:raise ValueError('reference_release_case_not_registered')
        condition=next(c for c in conditions['tasks'] if c['clip_id']==payload['clip_id'])
        rule=dict(required_horizon_s=(condition['clock']['frame_count']-1)/condition['clock']['media_fps'])
    if rule is None:return None
    horizon=rule['required_horizon_s'];fps=payload['fps'];frames=payload['frames']
    covers=payload['duration_s']+1e-6>=horizon
    endpoint=min(frames-1,math.floor(horizon*fps+1e-9))
    return dict(required_horizon_s=horizon,native_covers=covers,
                annotation_window_matches=abs(payload['window_s']-horizon)<1e-6,
                generated_endpoint_frame=endpoint,generated_endpoint_time_s=endpoint/fps,
                endpoint_discretization_s=horizon-endpoint/fps,
                status='insufficient_native_horizon' if not covers else
                       'annotation_window_recheck_required' if abs(payload['window_s']-horizon)>=1e-6 else
                       'registered_window_matches',
                reference_event_admission='separate_from_clock_and_source_state_verification')
