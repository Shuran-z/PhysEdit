"""Score velocity or estimate sliding friction without modifying gravity/SAM.

    python scripts/phyediting_motion_parameters.py velocity ITEMS PREDICTIONS OUT
    python scripts/phyediting_motion_parameters.py friction REGISTERED_INPUTS OUT
    python scripts/phyediting_motion_parameters.py kinematic-velocity REGISTERED_INPUTS OUT
    python scripts/phyediting_motion_parameters.py coverage-velocity REGISTERED_INPUTS OUT
    python scripts/phyediting_motion_parameters.py can-pixel-velocity REGISTERED_INPUTS OUT
    python scripts/phyediting_motion_parameters.py book-pixel-velocity REGISTERED_INPUTS OUT

Velocity ITEMS are the existing benchmark items; PREDICTIONS are frozen outputs.
Friction inputs contain measured pixel boxes and independent scene declarations.
Ground-truth targets are used after fitting, never inside the estimator.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from physedit.motion_parameters import fit_sliding_friction, scalar_error, summarize_errors, velocity_error


def rows(path):
    return list(map(json.loads, Path(path).read_text().splitlines()))


def evaluate_velocity(items, predictions):
    ids = [r['id'] for r in items]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate_registered_item')
    pred_ids = [r['id'] for r in predictions]
    if len(set(pred_ids)) != len(pred_ids) or set(pred_ids)-set(ids):
        raise ValueError('duplicate_or_unregistered_prediction')
    index = {r['id']:r.get('prediction', r) for r in predictions}
    result = []
    for item in items:
        r = dict(id=item['id'], event=item.get('event'), status='input_failure')
        try:
            if item['id'] not in index:
                raise ValueError('missing_prediction')
            r.update(velocity_error(index[item['id']], item['motion']['v0'],
                                    item['motion'].get('gravity_dir', [0, 0, -1])), status='ok')
        except (KeyError, TypeError, ValueError) as error:
            r['reason'] = str(error)
        result.append(r)
    return dict(records=result, speed=summarize_errors(result),
                vector=summarize_errors(result, key='vector_relative_error_pct'),
                groups={event:summarize_errors([r for r in result if r['event'] == event])
                        for event in sorted({r['event'] for r in result if r['event'] is not None})},
                gravity_refitted=False, target_reference='declared_fit_window_initial_state')


def evaluate_friction(records):
    ids = [r['id'] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate_registered_item')
    out = []
    for r in records:
        prediction = fit_sliding_friction(r['measurement'])
        row = dict(id=r['id'], **prediction)
        target = r.get('target_effective_friction')
        if target is not None and prediction.get('friction') is not None:
            row.update(scalar_error(prediction['friction'], target))
        if row['status'] == 'ok' and target is None:
            row.update(status='review_required', reason='missing_effective_friction_target')
        # Optional material declaration is a separate diagnostic, never accuracy certification.
        if r.get('declared_material_friction') is not None and prediction.get('friction') is not None:
            row['material_declaration_diagnostic'] = scalar_error(prediction['friction'], r['declared_material_friction'])
        out.append(row)
    point = sum(r['status'] == 'ok' for r in out)
    bound = sum(r['status'] == 'unidentifiable' and r.get('friction') is None
                and r.get('static_friction_bound', {}).get('point_estimate') is False for r in out)
    return dict(records=out, summary=summarize_errors(out), gravity_refitted=False,
                information_coverage=dict(registered=len(out), kinetic_point_estimates=point,
                    static_bounds=bound, unresolved=len(out)-point-bound,
                    point_or_bound_rate=(point+bound)/len(out) if out else None,
                    static_bounds_are_not_kinetic_estimates=True))


def evaluate_kinematic_velocity(records, complete_coverage=False, can_pixels=False, book_pixels=False):
    from physedit.velocity_kinematics import RegisteredPlanes, fit_registered_velocity, fit_coverage_velocity
    if can_pixels and book_pixels:
        raise ValueError('choose_one_registered_pixel_model')
    pixel_mode=can_pixels or book_pixels
    if pixel_mode:
        from physedit.velocity_pixels import RegisteredVelocityPixels, fit_pixel_velocity
    if book_pixels:
        from physedit.book_velocity_pixels import fit_book_pixel_velocity
    estimator = fit_coverage_velocity if complete_coverage else fit_registered_velocity
    ids = [r['id'] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate_registered_item')
    loaders, pixel_loaders, out = {}, {}, []
    for record in records:
        row = dict(id=record['id'], status='input_failure')
        try:
            reference = record['plane_registration']
            key = (reference['path'], reference['sha256'])
            if key not in loaders:
                loaders[key] = RegisteredPlanes(*key)
            sample = record['sample']
            if sample['id'] != record['id']:
                raise ValueError('input_sample_id_mismatch')
            if pixel_mode:
                pixel_reference = record['pixel_registration']
                pixel_key = (pixel_reference['path'], pixel_reference['sha256'])
                if pixel_key not in pixel_loaders:
                    pixel_loaders[pixel_key] = RegisteredVelocityPixels(*pixel_key)
                pixel_estimator=fit_book_pixel_velocity if book_pixels else fit_pixel_velocity
                prediction = pixel_estimator(sample, record['saved_gravity_prediction'],
                                             loaders[key], pixel_loaders[pixel_key])
            else:
                prediction = estimator(sample, record['saved_gravity_prediction'], loaders[key])
            row.update(prediction=prediction, status=prediction['status'], event=record.get('event'))
            if prediction['status'] == 'ok':
                import numpy as np
                truth = np.asarray(record['target_v0'], float)
                if truth.shape != (3,) or not np.isfinite(truth).all():
                    raise ValueError('invalid_velocity_target')
                speed = float(np.linalg.norm(truth))
                estimate = np.asarray(prediction['velocity_vector_mps'])
                row.update(scalar_error(np.linalg.norm(estimate), speed),
                           estimate_vector_mps=estimate.tolist(), target_vector_mps=truth.tolist(),
                           vector_absolute_error_mps=float(np.linalg.norm(estimate-truth)),
                           vector_relative_error_pct=100*float(np.linalg.norm(estimate-truth))/speed if speed > 0 else None)
            else:
                row['reason'] = prediction.get('reason', prediction['status'])
        except (KeyError, TypeError, ValueError, OSError) as error:
            row.update(status='input_failure', reason=str(error))
        out.append(row)
    result = dict(records=out, speed=summarize_errors(out), vector=summarize_errors(out, 'vector_relative_error_pct'),
                additional_source_information='registered_source_motion_plane',
                frozen_gravity_result_changed=False, scientific_independence_certified=False)
    if complete_coverage or pixel_mode:
        branches = {r.get('prediction', {}).get('source_model_branch', 'unresolved') for r in out}
        result.update(method_groups={branch:summarize_errors([r for r in out
            if r.get('prediction', {}).get('source_model_branch', 'unresolved') == branch]) for branch in sorted(branches)},
            dispatch_rule='registered source applicability, never target error',
            point_estimate_coverage_is_not_precision_certification=True)
    if pixel_mode:
        info='registered_visible_book_geometry_and_frozen_single_view_pixels' if book_pixels else 'registered_can_geometry_and_frozen_single_view_pixels'
        result.update(additional_source_information=info,
                      original_predictions_replaced=False, new_sam_inference=False,
                      noneligible_objects_are_retained=True)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='mode', required=True)
    vel = sub.add_parser('velocity')
    for key in ('items', 'predictions', 'output'): vel.add_argument(key, type=Path)
    fric = sub.add_parser('friction')
    for key in ('inputs', 'output'): fric.add_argument(key, type=Path)
    kin = sub.add_parser('kinematic-velocity')
    for key in ('inputs', 'output'): kin.add_argument(key, type=Path)
    coverage = sub.add_parser('coverage-velocity')
    for key in ('inputs', 'output'): coverage.add_argument(key, type=Path)
    pixel = sub.add_parser('can-pixel-velocity')
    for key in ('inputs', 'output'): pixel.add_argument(key, type=Path)
    book = sub.add_parser('book-pixel-velocity')
    for key in ('inputs', 'output'): book.add_argument(key, type=Path)
    args = ap.parse_args()
    if args.mode == 'velocity':
        output = evaluate_velocity(rows(args.items), rows(args.predictions))
    elif args.mode == 'friction':
        output = evaluate_friction(rows(args.inputs))
    else:
        output = evaluate_kinematic_velocity(rows(args.inputs), complete_coverage=args.mode == 'coverage-velocity',
                                             can_pixels=args.mode == 'can-pixel-velocity',
                                             book_pixels=args.mode == 'book-pixel-velocity')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k not in ('records', 'groups')}, allow_nan=False))


if __name__ == '__main__': main()
