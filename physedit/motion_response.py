"""Speed/friction control statistics from explicit, SHA-bound groups."""
import copy
import json
import math
from pathlib import Path

import numpy as np

from .inversion_inputs import item_digest
from .parameter_response import ranks, correlation
from .runners.media_contract import sha256


def load(config):
    if not config.get('response_manifest'):
        return []
    path = Path(config['response_manifest']).expanduser().resolve()
    if sha256(path) != config['response_manifest_sha256']:
        raise ValueError('motion_response_manifest_sha256_mismatch')
    groups = json.loads(path.read_text())
    if (not isinstance(groups, list) or any(not isinstance(g, dict) or not isinstance(g.get('group_id'), str) or not g['group_id']
                   or not isinstance(g.get('members'), list)
                   or any(not isinstance(m, dict) or not isinstance(m.get('item_id'), str) for m in g['members']) for g in groups)
            or len({g['group_id'] for g in groups}) != len(groups)):
        raise ValueError('invalid_motion_response_groups')
    return groups


def signature(item, kind, friction):
    motion = copy.deepcopy(item['motion'])
    if kind == 'velocity':
        motion.pop('v0', None)
    result = {key: item.get(key) for key in ('event','camera_id','object_name','split','gravity','camera','object','window','fps','image_size')}
    if isinstance(result.get('window'), dict):
        result['window'] = {k: result['window'].get(k) for k in ('start_frame','max_frames')}
    result['motion'] = motion
    if kind == 'friction':
        declaration = friction.get(item['id'])
        if declaration is None:
            raise ValueError('missing_response_friction_conditions')
        result['sliding_conditions'] = {k:v for k,v in declaration['conditions'].items() if k != 'evidence'}
        window = declaration.get('window', item['window'])
        result['sliding_window'] = {k:window.get(k) for k in ('start_frame','max_frames')}
    return json.dumps(result, sort_keys=True, allow_nan=False)


def summarize(media_rows, records, items, kind, config, friction):
    try:
        groups = load(config)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return dict(groups=[], registered_groups=None, scored_groups=0, registered_samples=len(media_rows),
                    ungrouped=[dict(sample_id=r['sample_id'],reason=str(error)) for r in media_rows],reason=str(error))
    by_sample = {r['sample_id']:r for r in records}
    results, grouped_ids = [], set()
    expected_kind = 'initial_speed' if kind == 'velocity' else 'effective_kinetic_friction'
    for group in groups:
        cohort = sorted({(r.get('model_name'), r.get('seed')) for r in media_rows
                         if r['item_id'] in {m.get('item_id') for m in group.get('members', [])}}, key=str)
        if not cohort:
            cohort = [(None, None)]  # Keep even a completely absent declared group.
        for model, seed in cohort:
            result = dict(group_id=group['group_id'], model=model, seed=seed, status='insufficient_evidence',
                          response_slope=None, ordering_consistency=None, spearman_rho=None,
                          members=group.get('members', []), failures=[])
            selected = [r for r in media_rows if r.get('model_name') == model and r.get('seed') == seed
                        and r['item_id'] in {m.get('item_id') for m in group.get('members', [])}]
            grouped_ids.update(r['sample_id'] for r in selected)
            try:
                members = group['members']
                if expected_kind in group.get('fixed_controls', {}):
                    raise ValueError('varying_motion_parameter_cannot_be_fixed')
                if (group.get('varying_parameter') != expected_kind or not group.get('fixed_controls')
                        or not isinstance(group['fixed_controls'], dict) or len(members) < 2
                        or len({m['item_id'] for m in members}) != len(members)):
                    raise ValueError('invalid_registered_motion_contrast')
                if {r['item_id'] for r in selected} != {m['item_id'] for m in members} or len(selected) != len(members):
                    raise ValueError('incomplete_registered_motion_group')
                if not model or type(seed) is not int:
                    raise ValueError('missing_response_model_or_seed')
                clocks = {json.dumps([r.get(k) for k in ('mode','output_fps','num_frames','gen_width','gen_height')]) for r in selected}
                if len(clocks) != 1:
                    raise ValueError('motion_response_generation_settings_differ')
                physical, directions, points = set(), [], []
                for member in members:
                    item = items[member['item_id']]
                    if member.get('item_sha256') != item_digest(item):
                        raise ValueError('motion_response_member_source_drift')
                    physical.add(signature(item, kind, friction))
                    row = next(r for r in selected if r['item_id'] == item['id'])
                    value = by_sample[row['sample_id']]
                    target = member.get('value')
                    if (type(target) not in (int,float) or not math.isfinite(target) or target < 0
                            or value.get('requested') != target):
                        raise ValueError('motion_response_target_mismatch')
                    if value['status'] != 'ok':
                        result['failures'].append(dict(sample_id=row['sample_id'],reason=value.get('reason') or value['status']))
                    points.append((target,value.get('estimate')))
                    if kind == 'velocity' and target > 0:
                        vector=np.asarray(value['target_vector_mps'],float)
                        directions.append(vector/np.linalg.norm(vector))
                if len(physical) != 1 or any(not np.allclose(d,directions[0],atol=1e-10,rtol=0) for d in directions):
                    raise ValueError('motion_response_fixed_conditions_differ')
                if result['failures']:
                    raise ValueError('one_or_more_motion_members_unscored')
                points.sort();x=[p[0] for p in points];y=[p[1] for p in points]
                if len(set(x)) < 2:
                    raise ValueError('missing_motion_parameter_contrast')
                if any(type(v) not in (int,float) or not math.isfinite(v) for v in y):
                    raise ValueError('invalid_motion_response_estimate')
                dx=np.asarray(x)-np.mean(x);dy=np.asarray(y)-np.mean(y)
                pairs=[(a,b) for a in range(len(x)) for b in range(a+1,len(x)) if x[a] != x[b]]
                result.update(status='ok',response_slope=float(dx@dy/(dx@dx)),
                    ordering_consistency=sum(y[b]>y[a] for a,b in pairs)/len(pairs),
                    tied_response_pairs=sum(y[b]==y[a] for a,b in pairs),
                    spearman_rho=correlation(ranks(x),ranks(y)) if len(set(x)) >= 3 else None)
            except (OSError,ValueError,KeyError,TypeError,StopIteration) as error:
                result['reason']=str(error)
            results.append(result)
    good=[r for r in results if r['status']=='ok']
    output=dict(groups=results,registered_groups=len(results),scored_groups=len(good),all_members_required=True,
                registered_samples=len(media_rows),grouped_samples=len(grouped_ids),
                ungrouped=[dict(sample_id=r['sample_id'],reason='missing_registered_motion_control_group')
                           for r in media_rows if r['sample_id'] not in grouped_ids])
    for key in ('response_slope','ordering_consistency','spearman_rho'):
        values=[r[key] for r in good if r[key] is not None]
        output[key]=dict(mean=sum(values)/len(values) if values else None,scored_groups=len(values))
    return output
