"""Version T11 visual events without changing any generation input or old score.

Four original speed-family references use the independently reread published
2.3/2.5 contrast. The global-family reference retains its reread candidate and
its unresolved native-contact diagnostic. No CPU64 interval is admitted here.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from physedit.core100_bindings import interval_distance
from physedit.core100_critical import load, primary, sha
from physedit.t11_visual_events import ACTORS, contract

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / 'benchmarks/t11_observable_events_candidate_v1_20261103'
OUT = ROOT / 'benchmarks/core100_critical_protocol_v3_20261103'
PARENT = ROOT / 'benchmarks/core100_critical_protocol_v2_20261102/registry_99526466ed6d.json'
PARENT_SHA = '99526466ed6d844842b760ed8af9717d6177d5b24f76f3b2b564b4d5903c84ca'
EVENT = ACTORS[0] + '_edge_fall_begins'
SPEED_CASES = ['T11_C01', 'T11_C02', 'T11_C04', 'T11_C05']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def migrate(base, references, contexts, reviews, global_endpoints):
    """Require fresh event, identity, window, RGB and fixed-context evidence."""
    data = copy.deepcopy(base)
    by_ref = {r['clip_id']: r for r in references['references']}
    by_review = {r['clip_id']: r for r in reviews['reviews']}
    by_context = {r['clip_id']: r for r in contexts['rows']}
    checks = {r['clip_id']: r for r in contexts['comparisons_to_C01']}
    if references['source_critical_registry_sha256'] != PARENT_SHA:
        raise ValueError('t11_reference_parent_changed')
    if contexts['source_registry_sha256'] != PARENT_SHA:
        raise ValueError('t11_context_parent_changed')
    if global_endpoints['source_registry_sha256'] != PARENT_SHA:
        raise ValueError('t11_global_parent_changed')
    contrast = references['new_event_original_published_contrast']
    if contrast['event'] != EVENT or contrast['endpoint_labels'] != [0, 1] or contrast['bracket'] != [2.3, 2.5]:
        raise ValueError('t11_new_event_contrast_not_attested')
    if reviews['negative_reference_full_window_review_pending']:
        raise ValueError('t11_negative_window_unreviewed')
    for cid in SPEED_CASES:
        check = checks[cid]
        if not all(check[k] for k in ['same_physical_context', 'same_condition_poses', 'same_frame_clock']):
            raise ValueError('t11_published_speed_context_changed')
        p = by_context[cid]['projection']
        if p['fixed_context_sha256'] != by_context['T11_C01']['projection']['fixed_context_sha256']:
            raise ValueError('t11_published_context_digest_changed')
        allowed = {'parameter_value', 'driver_force_before_first_contact_n',
                   'driver_force_after_second_contact_n', 'driver_force_after_second_contact_frames'}
        baseline = by_context['T11_C01']['projection']['experiment_parameter']
        changed = {k for k in set(baseline) | set(p['experiment_parameter'])
                   if baseline.get(k) != p['experiment_parameter'].get(k)}
        if changed - allowed:
            raise ValueError('t11_nonintervention_parameter_changed')
        forces = copy.deepcopy(p['original_runtime_forces'])
        expected = copy.deepcopy(by_context['T11_C01']['projection']['original_runtime_forces'])
        if len(forces) != 1 or forces[0]['force_world'] != [p['experiment_parameter']['driver_force_before_first_contact_n'], 0., 0.]:
            raise ValueError('t11_declared_control_not_executed')
        forces[0]['force_world'] = expected[0]['force_world']
        if forces != expected:
            raise ValueError('t11_control_schedule_changed')

    for row in data['cases']:
        if row['scene_id'] != 'T11':
            continue
        cid = row['clip_id']; ref = by_ref[cid]; visual = by_review[cid]
        measurement = ref['measurement']; label = measurement['events'][EVENT]['label']
        if ref['reference_video_sha256'] != row['reference_video_sha256']:
            raise ValueError('t11_reference_video_changed')
        if measurement['window_frames'] != [row['condition_frame_index'], row['end_frame_index']]:
            raise ValueError('t11_reference_window_changed')
        native = row['reference_native_state_binding']
        expected = native.get('stored_state_sha256', native['decoded_state_sha256'])
        if ref['native_stored_state_sha256'] != expected:
            raise ValueError('t11_reference_state_changed')
        if type(label) is not int or label not in [0, 1] or visual['label'] != label or visual['event'] != EVENT:
            raise ValueError('t11_new_event_reference_unresolved')
        prior = dict(reference_events=row['reference_events'], critical_units=row['critical_units'],
                     boundary_records=row['boundary_records'], judge_protocol=row['judge_protocol'])
        if cid in SPEED_CASES:
            if by_context[cid]['stored_state_sha256'] != ref['native_stored_state_sha256']:
                raise ValueError('t11_context_state_changed')
            axis = row['parameter']; theta = row['theta']; domain = row['normalization_domain']
            if axis != 'driver_initial_speed_command_mps' or domain != [1.8, 3.6]:
                raise ValueError('t11_original_axis_changed')
            if theta != by_context[cid]['projection']['experiment_parameter']['parameter_value']:
                raise ValueError('t11_original_parameter_changed')
            bracket = [2.3, 2.5]; endpoint_labels = [0, 1]; admitted = True
            row['fixed_context_sha256'] = by_context[cid]['projection']['fixed_context_sha256']
        else:
            # Recompute this new event at the old G-family endpoints. Do not
            # turn an unresolved native quality diagnostic into a clean flip.
            old = primary(row); axis = old['axis']; theta = old['theta']; domain = [0., 1.]
            bracket = global_endpoints['old_interval']; endpoint_labels = global_endpoints['new_endpoint_labels']
            if axis != 'original_G_global_path' or endpoint_labels != [0, 1]:
                raise ValueError('t11_original_global_event_not_reread')
            admitted = False
        span = domain[1] - domain[0]
        distance = interval_distance(theta, bracket, span)
        record = dict(event=EVENT, bracket=bracket, endpoint_labels=endpoint_labels,
                      distance=distance, exact_theta_star=None,
                      interval_kind='original_published_event_contrast' if admitted else 'original_gpu_global_event_reread_pending_contact_review')
        unit = dict(reference_id=hashlib.sha256(json.dumps([OUT.name, cid, axis, EVENT, bracket, row['horizon_s']]).encode()).hexdigest(),
                    clip_id=cid, axis=axis, theta=theta, event=EVENT, label=label, intervals=[bracket],
                    normalization_span=span, normalized_absolute_interval=distance['normalized_absolute_interval'],
                    bin=distance['bin'], numerical_evidence_status='bound_local_intervals',
                    rgb_distance_admitted=admitted, supplemental_axis=False,
                    rgb_blockers=[] if admitted else ['original_G_endpoint_contact_diagnostic_pending'],
                    exact_or_unique_physical_root_claimed=False)
        row.update(reference_events={EVENT: label}, reference_events_scope='Observable primary eraser edge-fall event; full chain remains separately registered.',
                   boundary_records=[record], critical_units=[unit], admitted_rgb_events=[EVENT],
                   rgb_reference_status='target_reference_admitted', rgb_pending_reason=None,
                   numerical_boundary_complete=True, original_family_boundary_complete=True,
                   full_EventExact_automatically_admitted=False,
                   distance_admission_pending_reason=None if admitted else '原G参数族已按新事件复读出两侧，但端点接触诊断尚待解释。')
        row.pop('conditional_axes', None)
        row['observable_event_revision'] = dict(version=OUT.name, prior=prior,
            semantics=EVENT, reference_witness=measurement['events'][EVENT], rgb_review=visual,
            independent_human_reference_gold=False,
            other_native_event_candidates=measurement['events'],
            inputs_prompts_and_old_labels_modified=False,
            interval_scope='Observed local interval; no exact, unique or globally monotonic physical threshold claimed.',
            cpu64_intervals_used=False)
        definition = copy.deepcopy(contract()['events'][EVENT])
        definition.update(applicable=True, minimum_evidence_times=2, role='observable_primary_event_v3',
                          formal_scoring_allowed=True, prompt_definition_source='Registered T11 observable-event revision; never inferred from generated outputs.')
        row['judge_protocol'] = dict(target='Track the original red/white eraser continuously from the condition frame. Identify its tabletop edge crossing, loss of support and subsequent downward motion.',
                                     events={EVENT: definition}, uncertainty_policy=contract()['uncertainty_policy'])
    data['version'] = OUT.name
    data['policy']['t11_event_revision'] = 'Observable edge-fall onset; frozen generation inputs unchanged; prior terminal-z labels remain in parent release.'
    summary = data['summary']
    summary['critical_rgb_distance_cases'] = sum(primary(c)['rgb_distance_admitted'] for c in data['cases'])
    summary['critical_rgb_distance_pending'] = [c['clip_id'] for c in data['cases'] if not primary(c)['rgb_distance_admitted']]
    summary['admitted_near_cases'] = sum(primary(c)['rgb_distance_admitted'] and primary(c)['bin'] == 'near' for c in data['cases'])
    summary['numerical_near_cases'] = sum(primary(c)['bin'] == 'near' for c in data['cases'])
    summary['reference_rgb_target_admitted'] = summary['primary_rgb_event_cases'] = sum(primary(c)['event'] in c['admitted_rgb_events'] for c in data['cases'])
    summary['reference_rgb_target_pending'] = summary['primary_rgb_event_pending'] = [c['clip_id'] for c in data['cases'] if primary(c)['event'] not in c['admitted_rgb_events']]
    by_case = {c['clip_id']: c for c in data['cases']}
    for mode in ['independent', 'coupled_seed']:
        summary[mode + '_admitted_pairs'] = sum(all(primary(by_case[c])['rgb_distance_admitted'] for c in p['clips']) for p in data['pairs'] if p['pairing_mode'] == mode)
    return data


def checked(pointer):
    receipt = read(CANDIDATE / pointer)
    path = CANDIDATE / receipt['path']
    if sha(path) != receipt['sha256']:
        raise ValueError('t11_evidence_changed:' + pointer)
    return read(path), path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    base, _ = load(PARENT, PARENT_SHA)
    refs, refs_path = checked('CURRENT.json')
    contexts, ctx_path = checked('PUBLISHED_SPEED_CONTEXTS.json')
    global_endpoints, global_path = checked('EXISTING_G_PATH_ENDPOINT_REREAD.json')
    review_path = CANDIDATE / 'RGB_REVIEW.json'
    reviews = read(review_path)
    evidence = [refs_path, ctx_path, global_path, review_path, Path(__file__), ROOT / 'physedit/t11_visual_events.py']
    for review in reviews['reviews']:
        if 'image_path' in review:
            p = ROOT / review['image_path']; assert sha(p) == review['image_sha256']; evidence.append(p)
        proof = review.get('evidence', {})
        if 'image_path' in proof:
            p = ROOT / proof['image_path']; assert sha(p) == proof['image_sha256']; evidence.append(p)
        for sheet in proof.get('sheets', []):
            p = ROOT / sheet['path']; assert sha(p) == sheet['sha256']; evidence.append(p)
    assert refs['event_definition_sha256'] == sha(ROOT / 'physedit/t11_visual_events.py')
    data = migrate(base, refs, contexts, reviews, global_endpoints)
    assert data['input_bindings'] == base['input_bindings'] and data['pairs'] == base['pairs']
    data['parent_registry'] = dict(path=PARENT.relative_to(ROOT).as_posix(), sha256=PARENT_SHA)
    data['event_revision_source_hashes'] = {}
    (OUT / 'sources').mkdir(parents=True, exist_ok=True)
    for source in evidence:
        digest = sha(source); target = OUT / 'sources' / (digest + source.suffix)
        if target.exists(): assert sha(target) == digest
        else: target.write_bytes(source.read_bytes())
        name = target.relative_to(ROOT).as_posix()
        data['source_hashes'][name] = digest
        data['event_revision_source_hashes'][source.relative_to(ROOT).as_posix()] = digest
    raw = json.dumps(data, ensure_ascii=False, indent=2).encode(); digest = hashlib.sha256(raw).hexdigest()
    path = OUT / ('registry_' + digest[:12] + '.json'); path.write_bytes(raw)
    load(path, digest)
    lines = ['# Core100临界点评测当前接入', '',
             f"已接入 {data['summary']['critical_rgb_distance_cases']}/100；Near参考 {data['summary']['admitted_near_cases']} 条。", '',
             '|场景|已接入|待完成|', '|---|---:|---:|']
    for i in range(1, 21):
        own = [c for c in data['cases'] if c['scene_id'] == f'T{i:02}']
        n = sum(primary(c)['rgb_distance_admitted'] for c in own)
        lines.append(f'|T{i:02}|{n}|{5-n}|')
    lines += ['', '## 未完成项', '']
    for c in data['cases']:
        if not primary(c)['rgb_distance_admitted']:
            lines.append('- ' + c['clip_id'] + '：' + str(c.get('distance_admission_pending_reason') or c.get('rgb_pending_reason') or primary(c)['rgb_blockers']))
    lines += ['', 'T11速度族采用原发布的2.3/2.5区间；保留区间宽度，不以中点分Near。C03原G族的新事件区间尚待接触诊断核验。旧注册、输入和成绩保留。']
    (OUT / 'STATUS.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
    if args.activate:
        pointer = ROOT / 'catalog/active_core100_critical_protocol.json'
        current = read(pointer)
        if current['registry_sha256'] not in [PARENT_SHA, digest]:
            raise ValueError('critical_pointer_changed_concurrently')
        (OUT / 'PARENT_POINTER.json').write_text(json.dumps(dict(version=base['version'], registry='../' + PARENT.relative_to(ROOT).as_posix(), registry_sha256=PARENT_SHA), indent=2))
        pointer.write_text(json.dumps(dict(version=data['version'], roster_release=data['roster_release'], registry='../' + path.relative_to(ROOT).as_posix(), registry_sha256=digest,
            scope='Versioned T11 observable-event revision; all generation inputs and previous runs preserved.'), indent=2))
    print(json.dumps(dict(path=str(path), sha256=digest, active=args.activate, summary=data['summary']), ensure_ascii=False))


if __name__ == '__main__':
    main()
