"""Read-only gravity-response statistics from explicitly registered control groups.

No scene grouping is inferred from paths, and no predictions are refitted.
Registration binds supplied evidence; it does not certify the underlying science.
"""
import hashlib
import json
import math
from pathlib import Path


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def ranks(values):
    ordered = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        for index in ordered[start:end]:
            result[index] = (start + end - 1) / 2
        start = end
    return result


def correlation(x, y):
    dx = [v - sum(x) / len(x) for v in x]
    dy = [v - sum(y) / len(y) for v in y]
    norm = math.sqrt(sum(v*v for v in dx) * sum(v*v for v in dy))
    return sum(a*b for a, b in zip(dx, dy)) / norm if norm else None


def registration(item, items):
    reference = item.get('parameter_response_registration')
    if not reference:
        raise ValueError('missing_registered_control_group')
    if not isinstance(reference, dict):
        raise ValueError('invalid_control_group_reference')
    if not Path(reference['path']).is_absolute():
        raise ValueError('control_group_path_must_be_absolute')
    raw = Path(reference['path']).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != reference['sha256']:
        raise ValueError('control_group_evidence_sha_mismatch')
    evidence = json.loads(raw)
    if not isinstance(evidence, dict):
        raise ValueError('invalid_control_group_registration')
    if (not isinstance(evidence.get('group_id'), str) or not evidence['group_id']
            or evidence.get('varying_parameter') != 'gravity'
            or not isinstance(evidence.get('fixed_controls'), dict) or not evidence['fixed_controls']):
        raise ValueError('invalid_control_group_registration')
    if 'gravity' in evidence['fixed_controls']:
        raise ValueError('varying_parameter_cannot_be_a_fixed_control')
    members = evidence.get('members', [])
    if (not isinstance(members, list) or len(members) < 2 or any(not isinstance(m, dict) for m in members)
            or len({m['item_id'] for m in members}) != len(members)
            or item['id'] not in {m['item_id'] for m in members}):
        raise ValueError('invalid_control_group_members')
    cohort = []
    for member in members:
        current = items.get(member['item_id'])
        if current is None or not positive(member.get('gravity')) or current.get('gravity') != member['gravity']:
            raise ValueError('control_group_member_or_gravity_mismatch')
        if current.get('parameter_response_registration') != reference:
            raise ValueError('control_group_member_registration_mismatch')
        cohort.append(current)
    for key in ('event', 'camera_id', 'object_name', 'split'):
        if any(not current.get(key) for current in cohort) or len({current[key] for current in cohort}) != 1:
            raise ValueError('control_group_' + key + '_mismatch')
    if len({m['gravity'] for m in members}) < 2:
        raise ValueError('no_registered_parameter_contrast')
    return evidence, digest


def summarize(rows, predictions, items):
    groups, ungrouped = {}, []
    for row in rows:
        try:
            evidence, digest = registration(items.get(row.get('item_id'), {}), items)
            if row.get('model_name') is None or type(row.get('seed')) is not int:
                raise ValueError('missing_registered_model_or_seed')
            key = (evidence['group_id'], digest, row.get('model_name'), row.get('seed'))
            group = groups.setdefault(key, dict(
                group_id=evidence['group_id'], evidence_sha256=digest,
                model=row.get('model_name'), seed=row.get('seed'), registration=evidence, rows=[]))
            group['rows'].append(row)
        except (KeyError, TypeError, ValueError, OSError) as error:
            ungrouped.append(dict(sample_id=row['sample_id'], reason=str(error)))
    results = []
    for group in groups.values():
        wanted = {m['item_id'] for m in group['registration']['members']}
        actual = [r['item_id'] for r in group['rows']]
        points, failures = [], []
        for row in group['rows']:
            prediction = predictions.get(row['sample_id'], {})
            value, target = prediction.get('gravity'), row.get('gravity_truth')
            valid = not row.get('input_failure') and prediction.get('status') == 'ok' and positive(value) and positive(target)
            points.append(dict(sample_id=row['sample_id'], item_id=row['item_id'], requested_gravity=target,
                               estimated_gravity=value if positive(value) else None,
                               status=prediction.get('status', 'missing_prediction'), usable=bool(valid)))
            if not valid:
                failures.append(dict(sample_id=row['sample_id'], reason=row.get('input_failure') or
                                     prediction.get('reason') or prediction.get('status') or 'missing_prediction'))
        record = {k: v for k, v in group.items() if k not in ('rows', 'registration')}
        record.update(points=points, registered_members=len(wanted), observed_members=len(actual), failures=failures,
                      status='insufficient_evidence', scientific_group_accuracy_certified=False,
                      response_slope=None, endpoint_response=None, ordering_consistency=None, spearman_rho=None)
        if set(actual) != wanted or len(actual) != len(wanted):
            record['reason'] = 'incomplete_or_duplicate_registered_control_group'
        elif failures:
            record['reason'] = 'one_or_more_registered_members_unscored'
        elif any(items[p['item_id']]['gravity'] != p['requested_gravity'] for p in points):
            record['reason'] = 'row_target_mismatch'
        else:
            points.sort(key=lambda p: p['requested_gravity'])
            x = [p['requested_gravity'] for p in points]
            y = [p['estimated_gravity'] for p in points]
            mean_x, mean_y = sum(x)/len(x), sum(y)/len(y)
            slope = sum((a-mean_x)*(b-mean_y) for a, b in zip(x, y)) / sum((a-mean_x)**2 for a in x)
            comparisons = [(a, b) for a in range(len(x)) for b in range(a+1, len(x)) if x[a] != x[b]]
            correct = sum(y[b] > y[a] for a, b in comparisons)
            ties = sum(y[b] == y[a] for a, b in comparisons)
            rho = correlation(ranks(x), ranks(y)) if len(set(x)) >= 3 else None
            # Average endpoint estimates if the registration includes repeated target levels.
            low = sum(v for t, v in zip(x, y) if t == x[0]) / x.count(x[0])
            high = sum(v for t, v in zip(x, y) if t == x[-1]) / x.count(x[-1])
            record.update(status='ok', response_slope=slope, endpoint_response=high-low,
                          ordering_consistency=correct/len(comparisons), ordering_pairs=len(comparisons),
                          tied_response_pairs=ties, spearman_rho=rho,
                          spearman_reason=None if rho is not None else
                              ('fewer_than_three_parameter_levels' if len(set(x)) < 3 else 'constant_estimated_response'))
        results.append(record)
    good = [r for r in results if r['status'] == 'ok']
    output = dict(protocol='phyediting_registered_gravity_response_v1', registered_samples=len(rows),
                  grouped_samples=sum(len(g['rows']) for g in groups.values()), ungrouped=ungrouped,
                  registered_groups=len(results), scored_groups=len(good), groups=results,
                  group_coverage_percent=100*len(good)/len(results) if results else None,
                  aggregation='equal_weight_control_groups_within_model_and_seed',
                  all_members_required=True, low_gravity_filter=False)
    for name in ('response_slope', 'ordering_consistency', 'spearman_rho'):
        values = [r[name] for r in good if r[name] is not None]
        output[name] = dict(mean=sum(values)/len(values) if values else None, scored_groups=len(values))
    output['by_model'] = {}
    for model in {r['model'] for r in results}:
        selected = [r for r in results if r['model'] == model]
        model_result = dict(registered_groups=len(selected), scored_groups=sum(r['status'] == 'ok' for r in selected))
        for name in ('response_slope', 'ordering_consistency', 'spearman_rho'):
            values = [r[name] for r in selected if r['status'] == 'ok' and r[name] is not None]
            model_result[name] = dict(mean=sum(values)/len(values) if values else None, scored_groups=len(values))
        output['by_model'][model] = model_result
    return output
