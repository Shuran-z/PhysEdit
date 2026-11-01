"""Non-destructive Core100 join; never infer admission from a sample-name match."""
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'review/core100_binding_20261028'
RES = ROOT/'annotation_site/resources'
inputs = {}


def read(path):
    inputs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    OUT.mkdir(exist_ok=True)
    points = read(RES/'core100_admission.json')['points']
    protocol = read(RES/'core100_contact_protocol_20261027.json')['clips']
    admission = read(RES/'reference_window_admission.json')
    admitted = {r['clip_id']:r for r in admission['references']}
    windows = read(RES/'core100_physical_windows_20261027.json')['cases']
    clocks = {r['clip_id']:r for r in read(ROOT/'review/reference_admission_20261024/clock100_metadata_audit.json')}
    readiness = {r['clip_id']:r for r in read(ROOT/'docs/critical_boundary/CORE100_READINESS_20261027.json')['cases']}
    contacts = read(RES/'core100_contact_boundaries_20261027.json')['records']
    contacts += read(RES/'core100_t13_contact_boundaries_20261027.json')['records']
    p = ROOT/'review/sg88_boundary_20261028/verified_numeric_search_snapshot.jsonl'
    inputs[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    supplements = [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s]
    t01 = read(OUT/'T01_C05_window_probe_audit.json')
    t13_audits = {r['clip_id']:r for r in read(OUT/'T13_window_independent_audit.json')['cases']}
    t13_solver_trials = {r['clip_id']:r for r in read(OUT/'T13_global_solver_source_audit.json')['cases']}
    t13_support_trials = {r['clip_id']:r for r in read(OUT/'T13_support_only_source_audit.json')['cases']}
    rows = []
    for point in sorted(points,key=lambda p:p['clip_id']):
        clip = point['clip_id']; definition = protocol[clip]; clock = clocks[clip]
        horizon = admitted[clip]['horizon_s'] if clip in admitted else windows[clip]['required_horizon_s'] if clip in windows else 5.
        matches = [r for r in supplements if r['sample_id'] == point['source_sample_id']]
        candidates = []
        for match in matches:
            state_match = clock.get('state_sha256') == match['source_state_sha256']
            candidates.append(dict(host=match['host'],job_id=match['job_id'],family_id=match['family_id'],
                result_sha256=match['result_sha256'],source_state_matches=state_match,
                numerical_verified=match['integrity_verified'] and match['event_recomputation_verified'],
                status='source_identity_candidate_window_pending' if state_match else 'source_identity_not_proven',
                formal_admission=False))
        local = [r for r in contacts if r['clip_id']==clip]
        contact_audit = t13_audits.get(clip)
        solver_trial = t13_solver_trials.get(clip)
        if contact_audit:
            assert local and all(r['result_sha256']==contact_audit['result_sha256'] for r in local)
        window_result = None
        if clip == 'T01_C05':
            assert len(matches)==1 and candidates[0]['source_state_matches']
            assert matches[0]['result_sha256']==t01['source_result_sha256']
            assert t01['sample_id']==point['source_sample_id'] and horizon==t01['horizon_s']
            assert clock['condition_frame_index']==t01['condition_frame_index']
            assert clock['physical_frame_period_s']==t01['physical_frame_period_s']
            domain=matches[0]['normalization_domain'];span=domain[1]-domain[0];assert span>0
            intervals=t01['observed_window_transitions'];theta=t01['source_theta']
            assert len(intervals)==1
            a,b=intervals[0]['bracket'];distance=[max(a-theta,theta-b,0)/span,max(abs(theta-a),abs(theta-b))/span]
            window_result=dict(target_event=t01['target_event'],horizon_s=horizon,bracket=[a,b],
                normalized_distance_interval=distance,near_eligible_by_distance=distance[1]<=.05,
                native_contact_peak_m=max(r['native_contact_peak_m'] for r in t01['probes'] if r['native_contact_peak_m'] is not None),
                source_version_rgb_binding='not_yet_certified',formal_admission=False)
        steps=[]
        if clip.startswith('T19'):steps.append('Await author-approved replacement reference; old reference remains retired')
        elif clip in admitted:steps.append('Retain admitted reference; verify generated media and annotation window without altering labels')
        elif window_result:steps.append('Verify reference video/config binding and physics quality; no additional bisection required for this observed interval')
        elif contact_audit:steps.append('Original support overlap independently reproduced. Global timeconst repair lowers contact depths but fails frozen-source trajectory/event compatibility. Do not admit or replace original boundaries; test support-only correction separately. Existing media and labels remain unchanged.')
        elif local:steps.append('Audit existing same-window probe states and reference binding before launching duplicate simulations')
        elif candidates:steps.append('Relabel existing verified states in exact Core100 window; refine only if window-specific bracket is insufficient')
        else:steps.append('Recover exact source/context and inspect original boundary ledgers; prepare same-event same-window search only for confirmed gaps')
        metric_requirements={
            'Balanced Target Accuracy':['same-version window-specific reference label','matching frozen-v6 generated input and media','final measurable/event annotation binding','registered class-balanced denominator'],
            'NearAcc':['all target-accuracy requirements','same-event fixed-context normalized boundary','near status certified at protocol threshold; non-near cases not forced into near'],
            'Independent PairAcc':['all target-accuracy requirements','opposite reference labels and controlled-context pair','registered output-pair sampling; no cross-product sample inflation'],
            'EventExact':['same-window truth for all frozen formal event IDs','matching per-event generated observations','auxiliary anomaly observations excluded from score unless separately versioned']}
        rows.append(dict(clip_id=clip,sample_id=point['source_sample_id'],reference=point['reference'],
            protocol_version=definition['version'],formal_event_ids=definition.get('formal_score_event_ids',[]),
            condition_frame_index=clock.get('condition_frame_index'),horizon_s=horizon,
            physical_frame_period_s=clock.get('physical_frame_period_s'),clock_evidence_complete=clock.get('clock_evidence_complete'),
            supplement_candidates=candidates,existing_window_records=len(local),window_reanalysis=window_result,
            same_window_independent_audit=(dict(event_hash_window_verified=True,
                checked_probes=len(contact_audit['probes']),native_depth_over_1mm_probes=sum(p['above_1mm']>0 for p in contact_audit['probes']),
                report='T13_window_independent_audit.json',formal_admission=False) if contact_audit else None),
            corrected_solver_source_trial=solver_trial,
            support_only_source_trial=t13_support_trials.get(clip),
            existing_reference_admitted=clip in admitted,required_next_steps=steps,
            prior_readiness_blockers=readiness[clip]['missing'],metric_requirements=metric_requirements,
            new_formal_admission=False))
    assert len(rows)==100 and len({r['clip_id'] for r in rows})==100
    for path,digest in inputs.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    summary=dict(cases=100,supplement_searches=len(supplements),exact_sample_match_cases=sum(bool(r['supplement_candidates']) for r in rows),
        same_window_reanalysed_cases=sum(r['window_reanalysis'] is not None for r in rows),
        existing_same_window_candidate_cases=sum(r['existing_window_records']>0 for r in rows),
        preserved_reference_admissions=len(admitted),preserved_pairs=len(admission['pairs']),new_formal_admissions=0)
    out=dict(schema='core100-supplement-binding-v1',summary=summary,evidence_sha256=inputs,cases=rows,
        policy='Read-only inputs. Existing media, annotations, prompts, frozen members and scoring protocols unchanged. Missing evidence is not an automatic simulation requirement. No scene-name or fuzzy-ID join.')
    (OUT/'binding.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary))


if __name__=='__main__':main()
