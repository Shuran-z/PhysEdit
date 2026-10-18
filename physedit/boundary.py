"""Independent boundary task: inversion eligibility NEVER gates generation.

python -m physedit.boundary run --spec SPEC --run-dir NEW [--execute]
python -m physedit.boundary score --run-dir RUN --annotations EVENTS --out NEW

Reference labels live in a separate answer key and are never exported to runners.
Events require independently supplied, video-hash-bound observations; no automatic
conversion of Qwen plausibility or reference labels into generated event labels.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_rows(path):
    rows = [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]
    ids = [r['sample_id'] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate sample_id: ' + str(path))
    return rows


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def write_rows(path, rows):
    with Path(path).open('x', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def mean(values):
    return sum(values) / len(values) if values else None


def validate(spec):
    """Validate the whole roster; scientific applicability stays per metric."""
    rows, keys = read_rows(spec['inputs']), read_rows(spec['answers'])
    lookup = {r['sample_id']: r for r in keys}
    if set(lookup) != {r['sample_id'] for r in rows}:
        raise ValueError('inputs and answer key must contain identical IDs')
    if not rows:
        raise ValueError('empty registration')
    model = spec['model']
    if not isinstance(model, str) or not model:
        raise ValueError('model must be registered')
    for row in rows:
        sid = row['sample_id']
        if not sid or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in sid):
            raise ValueError('unsafe sample ID')
        key = lookup[sid]
        for name in ('source_group_id', 'scene_id', 'family_id', 'point_id', 'theta', 'target_event', 'events', 'inversion'):
            if name not in key:
                raise ValueError('missing answer registration: ' + name)
        if not key['events'] or any(type(v) is not int or v not in (0, 1) for v in key['events'].values()):
            raise ValueError('reference event labels must be binary integers')
        if key['target_event'] not in key['events']:
            raise ValueError('target event absent')
        if type(key['theta']) not in (int,float) or not math.isfinite(key['theta']):
            raise ValueError('invalid physical parameter')
        if key['inversion']['status'] not in ('eligible', 'not_applicable', 'pending_reference_validation'):
            raise ValueError('invalid inversion status')
        if not key['inversion'].get('reason'):
            raise ValueError('inversion applicability requires reason')
        if type(row['seed']) is not int or type(row['num_frames']) is not int or row['num_frames'] < 2:
            raise ValueError('invalid frame count or seed')
        fps = row['fps']
        if not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
            raise ValueError('invalid clock')
        if not row.get('prompt') or not row.get('condition_image'):
            raise ValueError('missing inference input')
        if row['evaluation_duration_s'] > (row['num_frames'] - 1) / fps + 1e-6:
            raise ValueError('native clock does not cover registered event horizon')
        if row['evaluation_duration_s'] <= 0:
            raise ValueError('invalid horizon')
        # Unknown boundary is permitted, never replaced with a made-up midpoint.
        distance(key)
    for field in ('generation_command',):
        command = spec.get(field)
        if command is not None and (not isinstance(command, list) or not command or
                                    any(not isinstance(x, str) for x in command)):
            raise ValueError(field + ' must be an argv list')
    pair_seeds=defaultdict(lambda:defaultdict(set))
    pair_modes={}
    pair_labels=defaultdict(dict)
    point_seeds=defaultdict(set)
    for row in rows:
        key=lookup[row['sample_id']]
        group=(key['scene_id'],key['source_group_id'],key['family_id'])
        point=group+(key['point_id'],)
        if row['seed'] in point_seeds[point]:
            raise ValueError('duplicate seed for a registered point')
        point_seeds[point].add(row['seed'])
        for pair in key.get('pair_ids',[]):
            pair_key=group+(pair,)
            mode=key.get('pairing_mode','independent')
            if mode not in ('independent','coupled_seed'):
                raise ValueError('pairing_mode must be independent or coupled_seed')
            if pair_key in pair_modes and pair_modes[pair_key]!=mode:
                raise ValueError('both endpoints of a pair must use the same pairing_mode')
            pair_modes[pair_key]=mode
            pair_seeds[pair_key][key['point_id']].add(row['seed'])
            label=key['events'][key['target_event']]
            previous=pair_labels[pair_key].setdefault(key['point_id'],label)
            if previous!=label:
                raise ValueError('paired point has inconsistent reference target labels')
    for pair_key,members in pair_seeds.items():
        if len(members)!=2:
            raise ValueError('pair must register both points before generation')
        left,right=members.values()
        if pair_modes[pair_key] == 'independent' and left & right:
            raise ValueError('independent pairs require disjoint seed streams')
        if pair_modes[pair_key] == 'coupled_seed' and left != right:
            raise ValueError('coupled_seed pairs require identical seed sets at both endpoints')
        labels=list(pair_labels[pair_key].values())
        if len(labels)!=2 or labels[0]==labels[1]:
            raise ValueError('cross-boundary pair must have opposite reference outcomes')
    return rows, keys


def distance(key):
    boundary = key.get('boundary')
    if not boundary or boundary.get('status') != 'verified':
        return dict(status='unavailable', bin=None)
    theta, span = float(key['theta']), float(boundary['normalization_span'])
    if not math.isfinite(theta) or not math.isfinite(span) or span <= 0 or not boundary.get('source'):
        raise ValueError('invalid boundary provenance/scale')
    if 'theta_star' in boundary:
        a = b = float(boundary['theta_star'])
    else:
        a, b = map(float, boundary['bracket'])
    if not math.isfinite(a) or not math.isfinite(b) or a > b:
        raise ValueError('invalid reference interval')
    low = max(a - theta, theta - b, 0) / span
    high = max(abs(theta - a), abs(theta - b)) / span
    def bucket(x):
        return 'at_boundary' if x == 0 else 'near' if x <= .05 else 'mid' if x <= .15 else 'far'
    label = bucket(low) if bucket(low) == bucket(high) else None
    return dict(status='resolved' if label else 'ambiguous', bin=label,
                normalized_absolute_interval=[low, high], signed_interval=[theta-b, theta-a])


def plan(spec):
    rows, keys = validate(spec)
    return dict(schema='boundary_v1', model=spec['model'], registered=len(rows),
                target_counts=dict(Counter(str(k['events'][k['target_event']]) for k in keys)),
                inversion_status_counts=dict(Counter(k['inversion']['status'] for k in keys)),
                generation_not_gated_by_inversion=True,
                generation_candidates=len(rows), inputs_sha256=digest(spec['inputs']),
                answers_sha256=digest(spec['answers']), executed=False)


def media(path, row):
    """Decode every frame and enforce the registered native clock, no stretching."""
    if not Path(path).is_file():
        raise ValueError('missing_video')
    import cv2
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError('missing_or_undecodable_video')
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or abs(fps - row['output_fps']) > .02:
            raise ValueError('fps_mismatch')
        count, times = 0, []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame.shape[:2] != (row['source_height'], row['source_width']):
                raise ValueError('size_mismatch')
            times.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000)
            count += 1
        if count != row['num_frames']:
            raise ValueError('frame_count_mismatch')
        if any(not math.isfinite(t) or abs(t - i / fps) > .002 + .02 / fps for i, t in enumerate(times)):
            raise ValueError('unverified_native_timestamps')
        return dict(status='ok', video=str(path), video_sha256=digest(path), frames=count, fps=fps)
    finally:
        cap.release()


def run(spec, root):
    receipt = plan(spec)
    inputs, keys = validate(spec)
    if not spec.get('generation_command'):
        raise ValueError('execution requires a generation_command; no implicit model download')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    write_json(root/'registered.json', dict(**receipt, spec=spec,
               controller_sha256=digest(__file__), python_version=sys.version))
    write_rows(root/'inputs.jsonl', inputs)
    write_rows(root/'answers.jsonl', keys)
    write_json(root/'snapshot_hashes.json', {name:digest(root/name) for name in ('inputs.jsonl','answers.jsonl','registered.json')})
    export, prepared = [], []
    for source in inputs:
        sid = source['sample_id']
        state = dict(sample_id=sid, status='ready')
        try:
            image = Path(source['condition_image']).resolve()
            if digest(image) != source['condition_sha256']:
                raise ValueError('condition_image_hash_mismatch')
            prompt_dir = root/'prompts'/sid
            prompt_dir.mkdir(parents=True)
            prompt = prompt_dir/'prompt.txt'
            prompt.write_text(source['prompt'], encoding='utf-8')
            negative = prompt_dir/'negative_prompt.txt'
            negative.write_text(source.get('negative_prompt', ''), encoding='utf-8')
            # Allowlist: labels, distance, reference outcomes and eligibility NEVER leave this module.
            row = dict(sample_id=sid, condition_image=str(image), prompt_file=str(prompt),
                       negative_prompt_file=str(negative), seed=source['seed'],
                       num_frames=source['num_frames'], output_fps=source['fps'],
                       source_width=source['source_width'], source_height=source['source_height'],
                       width=source.get('width', source['source_width']),
                       height=source.get('height', source['source_height']),
                       out_dir=str(root/'generated'/sid))
            export.append(row)
            state['condition_sha256'] = source['condition_sha256']
            state['prompt_sha256'] = digest(prompt)
        except (OSError, ValueError) as error:
            state.update(status='input_failure', reason=str(error))
        prepared.append(state)
    write_rows(root/'generation_rows.jsonl', export)
    write_rows(root/'preparation.jsonl', prepared)
    code, failure = None, None
    if export:
        try:
            cmd = [x.format(manifest=str(root/'generation_rows.jsonl'), run_dir=str(root))
                   for x in spec['generation_command']]
            with (root/'generation.log').open('x', encoding='utf-8') as log:
                code = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                      timeout=spec.get('timeout_seconds', 3600), check=False).returncode
        except (OSError, subprocess.TimeoutExpired, KeyError) as error:
            failure = str(error)
    by_id = {r['sample_id']: r for r in export}
    observed = []
    for state in prepared:
        sid = state['sample_id']
        if sid in by_id:
            row = by_id[sid]
            try:
                state = dict(sample_id=sid, **media(Path(row['out_dir'])/'resized.mp4', row))
            except (OSError, ValueError, ImportError) as error:
                state = dict(sample_id=sid, status='generation_failure', reason=str(error))
        observed.append(state)
    write_rows(root/'observed_rows.jsonl', observed)
    write_json(root/'generation_receipt.json', dict(registered=len(inputs), exported=len(export),
               statuses=dict(Counter(r['status'] for r in observed)), returncode=code,
               command_failure=failure, scientific_evaluation_complete=False))
    # An editable template with unknown outcomes, never initialized from reference labels.
    templates = []
    key_by = {k['sample_id']: k for k in keys}
    for state in observed:
        k = key_by[state['sample_id']]
        templates.append(dict(sample_id=state['sample_id'], video_sha256=state.get('video_sha256'),
                              method='unannotated', events={e: None for e in k['events']},
                              event_times_s={}, evidence=''))
    write_rows(root/'event_annotation_template.jsonl', templates)
    return dict(registered=len(inputs), generation_ok=sum(r['status']=='ok' for r in observed),
                generation_not_gated_by_inversion=True)


def _index_optional(path, known):
    values = read_rows(path) if path else []
    if any(v['sample_id'] not in known for v in values):
        raise ValueError('unregistered result ID')
    return {v['sample_id']: v for v in values}


def score(root, annotations=None, gravity=None, screening=None):
    from .boundary_screening import gate
    root = Path(root)
    keys = read_rows(root/'answers.jsonl')
    inputs = read_rows(root/'inputs.jsonl')
    known = {k['sample_id'] for k in keys}
    if known != {i['sample_id'] for i in inputs}:
        raise ValueError('registration identities changed')
    receipt = json.loads((root/'registered.json').read_text(encoding='utf-8'))
    hashes=json.loads((root/'snapshot_hashes.json').read_text(encoding='utf-8'))
    if any(digest(root/name)!=value for name,value in hashes.items()):
        raise ValueError('registered snapshots changed')
    observations = _index_optional(root/'observed_rows.jsonl', known)
    annotations = _index_optional(annotations, known)
    gravity = _index_optional(gravity, known)
    screening_enabled = screening is not None
    screening = _index_optional(screening, known)
    horizon = {i['sample_id']: i['evaluation_duration_s'] for i in inputs}
    seeds = {i['sample_id']: i['seed'] for i in inputs}
    scored, groups = [], defaultdict(list)
    for key in keys:
        sid = key['sample_id']
        observed = observations.get(sid, {})
        annotation = annotations.get(sid, {})
        good = observed.get('status') == 'ok'
        if good:
            good = Path(observed['video']).is_file() and digest(observed['video']) == observed['video_sha256']
        bound = (good and annotation.get('video_sha256') == observed.get('video_sha256') and
                 annotation.get('method') not in (None, '', 'unannotated') and bool(annotation.get('evidence')))
        decision = gate(screening.get(sid), observed, key, screening_enabled)
        if not good:
            decision = dict(status='media_unavailable', blocked_events=list(key['events']),
                            block_inversion=True, reason='missing_failed_or_changed_media')
        events = dict(annotation.get('events', {})) if bound else {}
        for event in decision['blocked_events']:
            events.pop(event, None)
        if any(v is not None and (type(v) is not int or v not in (0,1)) for v in events.values()):
            raise ValueError('generated event must be 0/1/null')
        target = key['target_event']
        correct = int(events.get(target) == key['events'][target])
        bits = bound and all(events.get(e) == v for e, v in key['events'].items())
        first_error = next((e for e,v in key['events'].items() if events.get(e) in (0,1) and events.get(e)!=v), None)
        first_unknown = next((e for e in key['events'] if events.get(e) is None), None)
        times = annotation.get('event_times_s', {})
        order_ok = bool(bits)
        chain_assessable = bound and all(events.get(e) in (0, 1) for e in key['events'])
        for before, after in key.get('required_order', []):
            if events.get(before) == 1 and events.get(after) == 1:
                chain_assessable = chain_assessable and all(
                    type(times.get(e)) in (int, float) and 0 <= times[e] <= horizon[sid]
                    for e in (before, after))
            if key['events'][before] and key['events'][after]:
                a, b = times.get(before), times.get(after)
                if not (type(a) in (int,float) and type(b) in (int,float) and
                        0 <= a <= horizon[sid] and 0 <= b <= horizon[sid] and
                        a <= b + key.get('order_tolerance_s', 1/30)):
                    order_ok = False
        inv = key['inversion']
        g = gravity.get(sid, {})
        gstatus = inv['status'] if inv['status'] != 'eligible' else g.get('status', 'missing')
        if inv['status'] == 'eligible' and decision['block_inversion']:
            gstatus = 'screening_' + decision['status']
        gvalue, error = g.get('gravity'), None
        if inv['status'] == 'eligible' and gstatus == 'ok':
            if (not good or g.get('video_sha256') != observed.get('video_sha256') or
                type(gvalue) not in (float,int) or not math.isfinite(gvalue) or gvalue <= 0 or
                g.get('reference_registration_sha256') != inv.get('reference_registration_sha256') or
                not inv.get('reference_registration_sha256')):
                gstatus = 'invalid_or_unbound_prediction'
            else:
                error = abs(gvalue / key['gravity'] - 1)
        row = dict(sample_id=sid, reference_target=key['events'][target],
                   target_prediction=events.get(target), target_correct=correct,
                   target_assessable=events.get(target) in (0, 1),
                   chain_assessable=bool(chain_assessable),
                   event_assessable={e: events.get(e) in (0, 1) for e in key['events']},
                   screening_status=decision['status'],
                   screening_reason=decision['reason'],
                   blocked_events=decision['blocked_events'],
                   block_inversion=decision['block_inversion'],
                   task_success=int(bool(bits and order_ok) and decision['status'] in ('pass', 'legacy_not_screened')),
                   event_bits_exact=int(bool(bits)), event_exact=int(bool(bits and order_ok)),
                   first_error_stage=first_error if first_error else ('order' if bits and not order_ok else None),
                   first_unassessable_stage=first_unknown,
                   generation_status=observed.get('status', 'missing'),
                   annotation_status='bound' if bound else 'missing_or_unbound',
                   annotation_method=annotation.get('method'),
                   annotation_evidence=annotation.get('evidence') if bound else None,
                   video_sha256=observed.get('video_sha256'), seed=seeds[sid],
                   distance=distance(key), inversion_status=gstatus, gravity_relative_deviation=error)
        scored.append(row)
        groups[(key['scene_id'], key['source_group_id'], key['family_id'])].append((key,row))
    families = []
    for (scene, source, family), entries in groups.items():
        point_rows = defaultdict(list)
        point_keys = {}
        for key,row in entries:
            point_rows[key['point_id']].append(row)
            previous=point_keys.setdefault(key['point_id'], key)
            if previous['theta'] != key['theta'] or previous['events'] != key['events']:
                raise ValueError('inconsistent point registration')
        points = {pid:mean([r['target_correct'] for r in rs]) for pid,rs in point_rows.items()}
        balanced = {}
        for bucket in ('all','near','mid','far'):
            sides = [[points[pid] for pid,k in point_keys.items()
                      if k['events'][k['target_event']]==y and
                      (bucket=='all' or distance(k)['bin']==bucket)] for y in (0,1)]
            balanced[bucket] = mean([mean(s) for s in sides]) if all(sides) else None
        pairs = {}
        for pid,k in point_keys.items():
            for pair_id in k.get('pair_ids', []):
                pairs.setdefault(pair_id, []).append(pid)
        independent_pair_scores, coupled_pair_scores = [], []
        for pair_id,members in pairs.items():
            if len(members) != 2:
                raise ValueError('pair must bind exactly two points')
            l,r = members
            if point_keys[l]['events'][point_keys[l]['target_event']] == point_keys[r]['events'][point_keys[r]['target_event']]:
                raise ValueError('cross-outcome pair has same reference label')
            mode=point_keys[l].get('pairing_mode','independent')
            if mode == 'independent':
                # Product estimates success for two independent draws; it is not a matched-seed response rate.
                independent_pair_scores.append(points[l]*points[r])
            elif mode == 'coupled_seed':
                by_seed={pid:{row['seed']:row['target_correct'] for row in point_rows[pid]}
                         for pid in (l,r)}
                common=set(by_seed[l]) & set(by_seed[r])
                if not common or set(by_seed[l]) != set(by_seed[r]):
                    raise ValueError('coupled_seed pair has unmatched seeds')
                coupled_pair_scores.append(mean([by_seed[l][seed]*by_seed[r][seed]
                                                 for seed in sorted(common)]))
        independent_score=mean(independent_pair_scores)
        families.append(dict(scene_id=scene, source_group_id=source, family_id=family,
                             points=points, balanced_accuracy=balanced,
                             independent_pair_success=independent_score,
                             independent_pair_accuracy=independent_score,  # backward-compatible alias
                             coupled_pair_accuracy=mean(coupled_pair_scores),
                             event_exact=mean([mean([r['event_exact'] for r in rs]) for rs in point_rows.values()])))
    def macro(getter):
        src = defaultdict(list)
        for f in families:
            v=getter(f)
            if v is not None:src[(f['scene_id'],f['source_group_id'])].append(v)
        scenes=defaultdict(list)
        for (scene,_), vals in src.items():scenes[scene].append(mean(vals))
        return mean([mean(v) for v in scenes.values()])
    eligible = sum(k['inversion']['status']=='eligible' for k in keys)
    errors = [r['gravity_relative_deviation'] for r in scored if r['gravity_relative_deviation'] is not None]
    target_valid = [r for r in scored if r['target_assessable']]
    chain_valid = [r for r in scored if r['chain_assessable']]
    per_event = {}
    for event in sorted({e for k in keys for e in k['events']}):
        members = [r for r in scored if event in r['event_assessable']]
        count = sum(r['event_assessable'][event] for r in members)
        per_event[event] = dict(registered=len(members), assessable=count, coverage=count/len(members))
    return dict(model=receipt['model'], registered=len(keys), scored_rows=len(scored),
                target_counts=dict(Counter(str(r['reference_target']) for r in scored)),
                balanced_accuracy=macro(lambda f:f['balanced_accuracy']['all']),
                near_accuracy=macro(lambda f:f['balanced_accuracy']['near']),
                near_covered_families=sum(f['balanced_accuracy']['near'] is not None for f in families),
                independent_pair_success=macro(lambda f:f['independent_pair_success']),
                independent_pair_accuracy=macro(lambda f:f['independent_pair_success']),  # backward-compatible alias
                coupled_pair_accuracy=macro(lambda f:f['coupled_pair_accuracy']),
                event_exact=macro(lambda f:f['event_exact']),
                first_error_counts=dict(Counter(r['first_error_stage'] for r in scored if r['first_error_stage'])),
                annotations_bound=sum(r['annotation_status']=='bound' for r in scored),
                target_assessable=sum(r['target_prediction'] is not None for r in scored),
                screening=dict(enabled=screening_enabled,
                    statuses=dict(Counter(r['screening_status'] for r in scored)),
                    confirmed_failure_count=sum(r['screening_status']=='confirmed_failure' for r in scored),
                    unresolved_count=sum(r['screening_status'] in ('missing','suspect','evaluator_failure') for r in scored)),
                task_success_rate=mean([r['task_success'] for r in scored]),
                event_measurement=dict(registered=len(keys), target_assessable=len(target_valid),
                    target_coverage=len(target_valid)/len(keys), chain_assessable=len(chain_valid),
                    chain_coverage=len(chain_valid)/len(keys),
                    target_success_rate=mean([r['target_correct'] for r in scored]),
                    conditional_target_accuracy=mean([r['target_correct'] for r in target_valid]),
                    conditional_event_exact=mean([r['event_exact'] for r in chain_valid]),
                    per_event=per_event, aggregation='sample_micro; primary balanced metrics retain group macro aggregation'),
                inversion=dict(registered=len(keys), eligible=eligible, fitted=len(errors),
                     registered_coverage=len(errors)/len(keys),
                     eligibility_rate=eligible/len(keys), eligible_fit_coverage=len(errors)/eligible if eligible else None,
                     relative_deviation_mean=mean(errors),
                     statuses=dict(Counter(r['inversion_status'] for r in scored))),
                families=families, rows=scored,
                interpretation='development pilot; unknown boundaries do not produce NearAcc; no automatic scientific certification')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command', required=True)
    run_parser=sub.add_parser('run')
    run_parser.add_argument('--spec', required=True)
    run_parser.add_argument('--run-dir', required=True)
    run_parser.add_argument('--execute', action='store_true')
    score_parser=sub.add_parser('score')
    score_parser.add_argument('--run-dir', required=True)
    score_parser.add_argument('--annotations')
    score_parser.add_argument('--gravity')
    score_parser.add_argument('--screening', help='Hash-bound screening.jsonl; missing rows remain pending, never dropped')
    score_parser.add_argument('--out', required=True)
    screen_parser=sub.add_parser('screen', help='Import VLM triage before event/inversion work')
    screen_parser.add_argument('--run-dir', required=True)
    screen_parser.add_argument('--judgements', required=True)
    screen_parser.add_argument('--reviews')
    screen_parser.add_argument('--out-dir', required=True)
    args=parser.parse_args(argv)
    if args.command=='run':
        spec=json.loads(Path(args.spec).read_text(encoding='utf-8'))
        result=run(spec,args.run_dir) if args.execute else plan(spec)
    elif args.command=='screen':
        from .boundary_screening import prepare
        result=prepare(args.run_dir,args.judgements,args.reviews,args.out_dir)
    else:
        result=score(args.run_dir,args.annotations,args.gravity,args.screening)
        write_json(args.out,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','families')},ensure_ascii=False,allow_nan=False))
    return int(args.command=='run' and args.execute and result.get('generation_ok',0)<result['registered'])


if __name__=='__main__':
    sys.exit(main())
