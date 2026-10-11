"""Category-local validation of visible evidence; not semantic certification."""
import json
import math

PROTOCOL = 'visible_category_evidence_v3'
BASES = {
    'abnormal_deformation': ('nonrigid_shape_change',),
    'identity_change': ('object_replacement', 'unexplained_disappearance'),
    'interpenetration': ('impossible_overlap',),
    'camera_motion': ('static_scene_displacement',),
    'condition_inconsistency': ('initial_state_mismatch',),
}


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('judge_duplicate_json_key: ' + key)
        value[key] = item
    return value


def validate_response(raw, evidence):
    text = raw.strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if lines[-1].strip() != '```':
            raise ValueError('unterminated_json_fence')
        text = '\n'.join(lines[1:-1])
    value = json.loads(text, object_pairs_hook=_unique_object)
    if not isinstance(value, dict) or set(value) - set(BASES) - {'confidence', 'insufficient_evidence'}:
        raise ValueError('judge_schema_keys')
    confidence = value.get('confidence')
    if type(confidence) not in (float, int) or not math.isfinite(confidence) or not 0 <= confidence <= 1 or type(value.get('insufficient_evidence')) is not bool:
        raise ValueError('judge_confidence_or_evidence_schema')
    anchors = {f['frame_index'] for f in evidence['frames']}
    errors, judgement = {}, {}
    for name, positive in BASES.items():
        v = value.get(name)
        try:
            if not isinstance(v, dict) or set(v) != {'assessable', 'present', 'severity', 'evidence', 'basis', 'evidence_frames'}:
                raise ValueError('judge_category_schema_or_missing_evidence_fields')
            if type(v['assessable']) is not bool or type(v['present']) is not bool or type(v['severity']) is not int or v['severity'] not in range(4):
                raise ValueError('judge_category_types')
            if v['present'] != (v['severity'] > 0) or (not v['assessable'] and v['present']):
                raise ValueError('judge_category_inconsistent')
            if not isinstance(v['evidence'], str) or not v['evidence'].strip():
                raise ValueError('judge_missing_visual_reason')
            frames = v['evidence_frames']
            if not isinstance(frames, list) or any(type(f) is not int or f not in anchors for f in frames) or len(set(frames)) != len(frames):
                raise ValueError('judge_evidence_frames_not_registered')
            expected = positive if v['present'] else ('visible_consistency',) if v['assessable'] else ('not_observable',)
            if v['basis'] not in expected:
                raise ValueError('judge_basis_not_valid_for_category')
            if v['assessable']:
                if confidence == 0 or value['insufficient_evidence']:
                    raise ValueError('judge_overall_evidence_inconsistent')
                if name == 'condition_inconsistency':
                    if frames != [0]:
                        raise ValueError('judge_condition_requires_start_frame_only')
                elif len(frames) < 2:
                    raise ValueError('judge_temporal_category_requires_two_frames')
            judgement[name] = v
        except (ValueError, TypeError) as error:
            errors[name] = str(error)
            # This is an explicit invalid/unknown marker, never a model absence claim.
            judgement[name] = dict(assessable=False, present=False, severity=0, evidence='',
                                   basis='not_observable', evidence_frames=[])
    judgement.update(confidence=confidence,
                     insufficient_evidence=not any(judgement[k]['assessable'] for k in BASES))
    return dict(judgement=judgement, category_errors=errors, judgement_protocol=PROTOCOL,
                reported_insufficient_evidence=value['insufficient_evidence'],
                semantic_accuracy_validated=False)
