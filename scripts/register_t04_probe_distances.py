"""Bind the measured T04 local transition bracket; admission remains separate."""
import gzip,json
from pathlib import Path
from physedit.boundary import digest,distance
from scripts.audit_t04_completion_states import measure

ROOT=Path('review/scene_family_completion_20261018')

def main():
    samples=[(.105,'0105'),(.1225,'01225'),(.13125,'013125'),(.14,'014')]
    probes=[]
    for theta,token in samples:
        path=ROOT/f't04_probe_{token}_state.json.gz'
        data=json.loads(gzip.decompress(path.read_bytes()))
        if len(data['frames'])!=210:raise ValueError('incomplete probe')
        probes.append(dict(theta=theta,label=measure(data)['events']['stack_motion'],source=str(path.resolve()),sha256=digest(path)))
    if [r['label'] for r in probes]!=[1,1,0,0]:raise ValueError('expected measured transition not reproduced')
    proof=ROOT/'t04_backend_release_comparison.json'
    checks=json.loads(proof.read_text())
    if len(checks)!=2 or not all(r['event_labels_match'] for r in checks):raise ValueError('published endpoints not reproduced')
    source=ROOT/'t04_probe_bracket_evidence.json'
    source.write_text(json.dumps(dict(target_event='stack_motion',bracket=[.1225,.13125],labels=[1,0],probes=probes,endpoint_comparison=str(proof.resolve()),endpoint_comparison_sha256=digest(proof),limitations=['single run per new point; stochastic repeatability not established','local transition only; no global monotonicity claim','reference RGB audit pending']),indent=2),encoding='utf-8')
    states={r['sample_id']:r for r in json.loads((ROOT/'t04_measured_published_events.json').read_text())}
    result=[]
    for b in json.loads((ROOT/'t04_t05_profile_bindings.json').read_text()):
        if b['scene_id']!='T04' or b['source_group_id']!='T04__bg01_home_ase__g01_moon' or b['family_id']!='stack_sliding' or b['repeat']!=1:continue
        # 'verified' is used only to exercise the existing mathematical binning function.
        # The persisted admission state remains false; no verified boundary is exported.
        scale=b['normalization_basis']['normalization_span']
        numerical=distance(dict(theta=b['theta'],boundary=dict(status='verified',bracket=[.1225,.13125],normalization_span=scale,source=str(source.resolve()))))
        state=states[b['sample_id']]
        result.append(dict(sample_id=b['sample_id'],scene_id='T04',family_id=b['family_id'],theta=b['theta'],reference_label=state['events']['stack_motion'],reference_state_sha256=state['sha256'],fixed_context_sha256=state['fixed_context_sha256'],normalization_basis=b['normalization_basis'],computed_distance=numerical,bracket_evidence=str(source.resolve()),bracket_evidence_sha256=digest(source),formal_nearacc_eligible=False,status='computed_distance_repeatability_and_visual_admission_pending'))
    if len({r['fixed_context_sha256'] for r in result})!=1 or len(result)!=3:raise ValueError('published context alignment failed')
    (ROOT/'t04_probe_distance_registry.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps([dict(theta=r['theta'],label=r['reference_label'],distance=r['computed_distance']) for r in result]))

if __name__=='__main__':main()
