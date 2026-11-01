"""Evidence-based scene integrity screening; machine candidates require review."""
import math

POLICY = 'scene-integrity-v2'
CHECKS = ('foreign_objects', 'scene_replacement', 'identity_loss', 'geometry_corruption')
FAILURES = {
    'foreign_objects': 'new_object_intrusion',
    'scene_replacement': 'scene_replacement',
    'identity_loss': 'identity_loss',
    'geometry_corruption': 'severe_corruption',
}

PROMPT = '''Screen visual scene integrity, not physical correctness. The FIRST image is the immutable scene anchor. Inspect the WHOLE image, including background, not only the named target. Track initial actors by appearance and spatial continuity. A new object of the same category is not automatically the original actor.
First briefly inventory the objects, people/characters (if any), furniture and setting visible in sample 0. Then check FOUR independent defects:
foreign_objects: unrelated entities absent from the initial scene appear later, including human heads, bodies, hands, cartoon characters, faces, extra devices or unrelated objects. Flag these even if the original target remains intact. Do not dismiss a giant head or cartoon character as harmless background activity. Ordinary previously occluded furniture revealed by camera movement is not automatically a new entity; use uncertain if continuity cannot be established.
scene_replacement: the setting/layout or scene contents are replaced or turn into another scene. Camera pan/zoom, lighting changes or legitimate motion alone do not prove replacement.
identity_loss: an original physical actor disappears through fusion, disintegration, semantic transformation, duplication/substitution or replacement that prevents tracking its original identity. Rotation, ordinary occlusion and leaving the field of view alone are not identity loss.
geometry_corruption: severe nonrigid collapse or melting destroys interpretable objects/support. Clearly observable wrong physics, a stationary object, floating or wrong event outcomes alone are NOT garbage; leave these for event/physics evaluation.
For EACH defect choose label present, absent, or uncertain, provide evidence_indices (integer sample indices, not native frame IDs or seconds), and a short concrete reason. For present cite at least TWO distinct POST-INITIAL samples showing the defect. Do NOT put sample 0 in present evidence: sample 0 is the implicit comparison anchor, not evidence of a later intrusion. Mention the initial-scene contrast in the reason. For absent cite sample 0 AND the last supplied sample after checking intermediate images. If a defect is only seen once, use uncertain. The contradictions list is ONLY for mutually incompatible interpretations of the SAME image or contradictions between your own labels and reasons. An object appearing/disappearing between different times is defect evidence, NOT a contradiction: use contradictions=[] when that temporal change is clear. Do not output confidence, a numeric quality score, or an overall pass verdict: the program derives routing from the four observations. Ensure each label agrees with its reason; never write absent while describing an intrusion or replacement.
Return JSON ONLY with top-level key quality. quality contains initial_inventory (short string), contradictions (list), and checks (object). checks must contain foreign_objects, scene_replacement, identity_loss, geometry_corruption; each value contains label, evidence_indices, reason. Choose one label, not a list of alternatives. Only cite supplied samples; do not invent unseen frames or expected future events.'''


def normalize_quality(payload, times):
    """Map discrete supplied-image evidence to timestamps; never infer missing labels."""
    if not isinstance(payload, dict):
        raise ValueError('quality must be an object')
    if len(times) < 2 or any(type(t) not in (int, float) or not math.isfinite(t) for t in times):
        raise ValueError('invalid supplied sample clock')
    checks = payload.get('checks')
    if not isinstance(checks, dict) or set(checks) != set(CHECKS):
        raise ValueError('all four scene checks required')
    if not isinstance(payload.get('initial_inventory'), str) or not payload['initial_inventory'].strip():
        raise ValueError('initial scene inventory required')
    contradictions = payload.get('contradictions')
    if not isinstance(contradictions, list) or any(not isinstance(x, str) for x in contradictions):
        raise ValueError('contradictions must be a list of strings')
    result = dict(policy_version=POLICY, policy_revision='20261021-r2', initial_inventory=payload['initial_inventory'],
                  contradictions=list(contradictions), checks={})
    for name in CHECKS:
        record = checks[name]
        if not isinstance(record, dict) or record.get('label') not in ('present', 'absent', 'uncertain'):
            raise ValueError('invalid scene check label: ' + name)
        indices = record.get('evidence_indices')
        if not isinstance(indices, list) or any(type(i) is not int or not 0 <= i < len(times) for i in indices):
            raise ValueError('evidence index not supplied: ' + name)
        if not isinstance(record.get('reason'), str) or not record['reason'].strip():
            raise ValueError('visual reason required: ' + name)
        result['checks'][name] = dict(label=record['label'], evidence_indices=indices,
            evidence_times_s=[times[i] for i in indices], reason=record['reason'])
    route = scene_quality_route(result, max(times))
    defects = [name for name, record in result['checks'].items() if record['label'] == 'present']
    result.update(status='unmeasurable' if route == 'auto_rejected' else 'measurable' if route == 'pass' else 'uncertain',
        failure=FAILURES[defects[0]] if defects else 'none' if route == 'pass' else 'uncertain',
        reason='; '.join(name + ': ' + result['checks'][name]['reason'] for name in (defects or CHECKS)),
        evidence_times_s=sorted({t for name in (defects or CHECKS) for t in result['checks'][name]['evidence_times_s']}))
    return result


def scene_quality_route(quality, horizon):
    """No self-confidence threshold: require visible independent temporal evidence."""
    if quality.get('policy_version') != POLICY or quality.get('contradictions') != []:
        return 'review'
    checks = quality.get('checks')
    if not isinstance(checks, dict) or set(checks) != set(CHECKS):
        return 'review'
    supported_defect = False
    all_absent = True
    for name in CHECKS:
        record = checks[name]
        if not isinstance(record, dict):return 'review'
        label = record.get('label');indices = record.get('evidence_indices');times = record.get('evidence_times_s')
        if label not in ('present','absent','uncertain') or not isinstance(indices,list) or not isinstance(times,list):return 'review'
        if len(indices)!=len(times) or any(type(i) is not int or i<0 for i in indices):return 'review'
        if any(type(t) not in (int,float) or not math.isfinite(t) or not 0<=t<=horizon for t in times):return 'review'
        if not isinstance(record.get('reason'),str) or not record['reason'].strip():return 'review'
        supported = len(set(indices)) >= 2 and len(set(times)) >= 2
        if label == 'present' and supported and all(i>0 for i in indices):supported_defect = True
        if label != 'absent' or not supported or 0 not in times or not any(abs(t-horizon)<=1e-6 for t in times):all_absent = False
    if supported_defect:return 'auto_rejected'
    return 'pass' if all_absent else 'review'
