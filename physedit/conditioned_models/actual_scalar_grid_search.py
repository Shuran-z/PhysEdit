"""Registered conditional motion model and image objective."""
import numpy as np
from scipy.optimize import minimize_scalar

def optimize(initial_trials, cost, actual, *, tolerance):
    table = {float(v): np.asarray(p) for (v, p) in initial_trials}
    scores = {v: cost(p, False) for (v, p) in table.items()}
    values = sorted(table)
    (lo, hi) = (values[0], values[-1])
    added = []

    def evaluate(v):
        v = float(v)
        if v not in table:
            table[v] = actual(v)
            scores[v] = cost(table[v], False)
            added.append(v)
        return scores[v]
    bins = set()
    for value in sorted(scores, key=scores.get)[:3]:
        k = values.index(value)
        if k > 0:
            bins.add((values[k - 1], value))
        if k < len(values) - 1:
            bins.add((value, values[k + 1]))
    for (a, b) in sorted(bins):
        r = minimize_scalar(evaluate, bounds=(a, b), method='bounded', options=dict(maxiter=24, xatol=tolerance))
        evaluate(r.x)
    best = min(scores, key=scores.get)
    response = max(scores.values()) - scores[best]
    status = 'ok'
    reason = None
    if response < 1e-10:
        status = 'unidentifiable'
        reason = 'no image parameter response'
    elif min(best - lo, hi - best) < tolerance:
        status = 'at_bound'
        reason = 'registered search boundary'
    return dict(prediction=dict(estimate=None if status == 'unidentifiable' else best, status=status, reason=reason, objective=scores[best], uses_prior_fill=False, estimate_is_an_actual_forward_trial=True, new_actual_forward_trials=len(added), method='condition_aligned_single_camera_mask_actual_grid_search'), trials=[dict(value=v, cost=scores[v], predicted_poses=table[v].tolist()) for v in sorted(table)], new_actual_trial_values=added)
