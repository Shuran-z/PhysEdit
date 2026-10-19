"""Full-denominator generation summary; never load hardcoded historical runs."""
import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def read_rows(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def summarise(preds, wanted):
    """One output per registered sample_id (including seeds of the same item)."""
    errors, failures = [], []
    statuses = Counter()
    observed, planned = 0, 0
    for row in wanted:
        p = preds.get(row['sample_id'], {'status': 'missing_prediction', 'reason': 'missing_prediction'})
        status = p.get('status', 'invalid_prediction')
        g, target = p.get('gravity'), row.get('gravity_truth')
        if status == 'ok' and not (type(g) in (float, int) and math.isfinite(g) and g > 0 and
                type(target) in (float, int) and math.isfinite(target) and target > 0):
            status = 'invalid_numeric_prediction'
        if row.get('input_failure'):
            status = 'input_failure'
        statuses[status] += 1
        planned += p.get('planned_frames', 0)
        observed += p.get('frames', 0)
        if status == 'ok':
            errors.append(abs(g / target - 1) * 100)
        else:
            failures.append(dict(sample_id=row['sample_id'], item_id=row.get('item_id'), status=status,
                                 reason=row.get('input_failure') or p.get('reason') or p.get('observation_reason') or status,
                                 observation_reasons=p.get('missing_observation_reasons', {})))
    n, good = len(wanted), len(errors)
    return dict(registered=n, scored=good, failed=n-good, status_counts=dict(statuses),
                coverage_percent=100*good/n if n else None, failure_rate_percent=100*(n-good)/n if n else None,
                mean_error_percent=sum(errors)/good if good else None,
                max_error_percent=max(errors) if good else None,
                median_error_percent=sorted(errors)[good//2] if good % 2 else
                    (sum(sorted(errors)[good//2-1:good//2+1])/2 if good else None),
                within20=sum(e <= 20 for e in errors), planned_frames=planned, observed_frames=observed,
                failures=failures, error_interpretation='deviation_from_requested_gravity_not_generated_physical_truth')


def report(rows, predictions, items):
    ids = [r['sample_id'] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate registered sample IDs')
    if len({p['id'] for p in predictions}) != len(predictions):
        raise ValueError('Duplicate prediction IDs')
    if set(p['id'] for p in predictions) - set(ids):
        raise ValueError('Prediction outside registered denominator')
    by_id = {p['id']: p for p in predictions}
    result = summarise(by_id, rows)
    from physedit.parameter_response import summarize as response_summary
    result['parameter_response'] = response_summary(rows, by_id, items)
    result['groups'] = {}
    for field in ('split', 'event', 'camera_id', 'gravity_truth'):
        groups = defaultdict(list)
        for r in rows:
            value = r.get(field, items.get(r.get('item_id'), {}).get(field, 'unspecified'))
            groups[str(value)].append(r)
        result['groups'][field] = {k: summarise(by_id, v) for k, v in groups.items()}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('items', 'rows', 'predictions', 'out'):
        parser.add_argument('--'+field, required=True)
    args = parser.parse_args(argv)
    output = Path(args.out)
    if output.exists():
        raise ValueError('Existing summary retained; no overwrite')
    result = report(read_rows(args.rows), read_rows(args.predictions), {it['id']: it for it in read_rows(args.items)})
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'groups'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
