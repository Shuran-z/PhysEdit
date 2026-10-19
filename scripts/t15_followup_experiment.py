"""Prepare a matched-gap T15 experiment and reference-label negative controls.

Controls below are synthetic predictions on real reference labels, NOT generated
video results. No exact critical value is inferred from the sparse triplet.
"""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from physedit.boundary import digest, write_json, write_rows, validate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'review/t15_followup_20261014'
REMOTE = '/home/wangzijun_p25/liyuhan/t15_boundary_pipeline_20261014'


def main():
    OUT.mkdir(exist_ok=False)
    audit_path = ROOT / 'review/t15_boundary_pilot_20261014/reference_audit.json'
    audit = json.loads(audit_path.read_text())
    rows = audit['rows']
    group = next(g for g in audit['canonical_A_groups'] if g['gravity'] == 'g03_earth')
    assert group['single_speed_contract']
    points = group['points']
    gaps = [points[i+1]['speed'] - points[i]['speed'] for i in range(2)]
    assert abs(gaps[0] - gaps[1]) < 1e-9
    assert [p['events'][2] for p in points] == [0, 0, 1]
    write_json(OUT / 'preregistration.json', dict(
        reference_audit_sha256=digest(audit_path), context=group,
        comparison={'same_side':['A0','A1'], 'cross_side':['A1','A2'],
                    'parameter_gap_mps':gaps[0]},
        model='LTX-Video-2B-0.9.5-I2V', seeds={'A0':39000,'A1':39100,'A2':39200},
        reuse='A1 reused only after exact input and output identity checks; not a new independent trial',
        scope='one context, one seed per point; descriptive pilot, no statistical efficacy claim',
        boundary_status='unavailable; no fabricated midpoint or NearAcc',
        inversion='negative examples retained; fall example requires frozen eligibility validation',
        horizon_s=6, new_reference_rendering=False))

    # Two-row runner remains bounded. A1 is an identity-checked reuse and A0 is new.
    prior = ROOT / 'review/t15_boundary_pipeline_20261014/registration_v2'
    inp = [json.loads(s) for s in (prior/'inputs.jsonl').read_text().splitlines()]
    ans = [json.loads(s) for s in (prior/'answers.jsonl').read_text().splitlines()]
    x0, x1 = copy.deepcopy(inp[0]), copy.deepcopy(inp[0])
    k0, k1 = copy.deepcopy(ans[0]), copy.deepcopy(ans[0])
    ref = next(r for r in rows if r['sample_id'] == points[0]['sample_id'])
    x0.update(sample_id='t15_earth_A0_s0', seed=39000,
              prompt=x0['prompt'].replace('2.016 m/s', '1.728 m/s'))
    assert x0['prompt'] != x1['prompt']
    k0.update(sample_id=x0['sample_id'], point_id='A0', theta=1.728,
              reference_sample_id=ref['sample_id'], reference_config_sha256=ref['config_sha256'],
              reference_state_sha256=ref['state_sha256'], reference_output=ref['output'],
              reference_event_frames=ref['event_frames'],
              events=dict(zip(k0['events'], ref['events'])))
    k0['pair_ids'] = []; k1['pair_ids'] = []
    write_rows(OUT/'inputs_same_side.jsonl', [x0,x1])
    write_rows(OUT/'answers_same_side.jsonl', [k0,k1])
    validate(dict(model='LTX-Video-2B-0.9.5-I2V',
                  inputs=str(OUT/'inputs_same_side.jsonl'), answers=str(OUT/'answers_same_side.jsonl')))
    spec = json.loads((ROOT/'review/t15_boundary_pipeline_20261014/spec_v6.json').read_text())
    spec.update(inputs=REMOTE+'/followup/inputs_same_side.jsonl',
                answers=REMOTE+'/followup/answers_same_side.jsonl')
    write_json(OUT/'spec_same_side.json', spec)

    def evaluate(name, prediction):
        correct = [int(prediction(r)[2] == r['events'][2]) for r in rows]
        sides = [[c for r,c in zip(rows,correct) if r['events'][2] == y] for y in (0,1)]
        exact = [int(prediction(r) == r['events']) for r in rows]
        # Bits only: these controls do not supply time observations.
        return dict(name=name, n=len(rows), raw_fall_accuracy=sum(correct)/len(rows),
                    balanced_fall_accuracy=sum(sum(s)/len(s) for s in sides)/2,
                    event_bits_exact=sum(exact)/len(exact),
                    event_exact_with_order=None,
                    interpretation='synthetic label control, not generated-video performance')
    controls = [evaluate('reference_label_oracle', lambda r:r['events']),
                evaluate('constant_no_fall_prefix', lambda r:[1,0,0,0,0]),
                evaluate('constant_full_chain', lambda r:[1,1,1,1,1]),
                evaluate('correct_fall_but_wrong_upstream_contact',
                         lambda r:[1-r['events'][0],*r['events'][1:]])]
    write_json(OUT/'reference_label_controls.json', dict(
        source_sha256=digest(audit_path), controls=controls,
        constant_predictor_cross_pair_accuracy=0,
        warning='Mathematical sensitivity check only. Does not demonstrate model failure prevalence, distance effects, or inversion complementarity.'))
    print(json.dumps({'out':str(OUT),'controls':controls}, indent=2))


if __name__ == '__main__':
    main()
