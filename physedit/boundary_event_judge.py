"""Derive diagnostic event gates from observations, never redundant VLM scores.

This adapter does not establish visual truth or replace human adjudication.
"""
STATES = {'supported', 'detached_descending', 'edge_contact_uncertain', 'unobservable'}
VISIBILITY = {'visible', 'partially_visible', 'not_visible', 'uncertain'}


def normalize_observation(observation, n_images):
    if type(n_images) is not int or n_images < 2:
        raise ValueError('at least two images required')
    state = observation.get('support_state')
    visible = observation.get('target_at_end')
    if state not in STATES or visible not in VISIBILITY:
        raise ValueError('invalid observation enum')
    if not isinstance(observation.get('reason'), str) or not observation['reason'].strip():
        raise ValueError('reason required')
    fields = ('evidence_image_indices', 'detachment_evidence_indices', 'descent_evidence_indices')
    indices = {}
    for name in fields:
        values = observation.get(name, [])
        if not isinstance(values, list) or any(type(i) is not int or not 0 <= i < n_images for i in values):
            raise ValueError('invalid '+name)
        indices[name] = sorted(set(values))
    warnings = []
    fall = None
    if len(indices['evidence_image_indices']) < 2:
        warnings.append('insufficient_temporal_evidence')
    elif state == 'supported' and visible in {'visible', 'partially_visible'}:
        fall = 0
    elif state == 'detached_descending':
        if indices['detachment_evidence_indices'] and len(indices['descent_evidence_indices']) >= 2:
            fall = 1
        else:
            warnings.append('missing_detachment_or_descent_evidence')
    gate = 'usable' if fall is not None else 'review'
    for name, expected in (('fall', fall), ('event_gate', gate)):
        if name in observation and observation[name] != expected:
            warnings.append('ignored_conflicting_model_'+name)
    return {'fall': fall, 'event_gate': gate, 'support_state': state,
            'target_at_end': visible, 'warnings': warnings,
            'normalization_version': 'observation-v1',
            'truth_status': 'unverified_model_observation'}


def normalize_screened_observation(observation, image_frame_ids):
    """Scene-integrity rejection and event routing; same-time views are not pairs."""
    n=len(image_frame_ids)
    integrity=observation.get('integrity')
    if integrity not in {'intact','definite_corruption','uncertain'}:
        raise ValueError('invalid integrity')
    evidence=observation.get('corruption_evidence_indices',[])
    if not isinstance(evidence,list) or any(type(i) is not int or not 0<=i<n for i in evidence):
        raise ValueError('invalid corruption evidence')
    result=normalize_observation(observation,n)
    result['integrity']=integrity
    if integrity=='definite_corruption':
        enough=len({image_frame_ids[i] for i in evidence})>=2
        result.update(fall=None,event_gate='reject' if enough else 'review')
        if not enough:result['warnings'].append('insufficient_corruption_temporal_evidence')
    elif integrity=='uncertain':
        result.update(fall=None,event_gate='review')
    elif result['event_gate']=='usable':
        general=observation.get('evidence_image_indices',[])
        descent=observation.get('descent_evidence_indices',[])
        if len({image_frame_ids[i] for i in general})<2 or (result['fall']==1 and len({image_frame_ids[i] for i in descent})<2):
            result.update(fall=None,event_gate='review')
            result['warnings'].append('same_time_views_not_temporal_evidence')
    result['normalization_version']='screened-observation-v1'
    return result
