import json
import pytest
from scripts import bind_t03_current_parameters as binder


@pytest.mark.parametrize('split_middle_solver',[False,True])
def test_recovered_state_identity_normalization_and_solver_separation(tmp_path,monkeypatch,split_middle_solver):
    monkeypatch.setattr(binder,'ROOT',tmp_path)
    monkeypatch.setattr(binder,'context',lambda experiment,family:'declared-context')
    headers=[];reports=[];states=[];roster=[]
    for i,theta in enumerate([1.,1.5,2.]):
        sid=str(i);parameter={'book_initial_speed_mps':theta}
        e=dict(parameter=parameter,causal_parameter_group='A',seed=i,parameter_region='theta_star' if i==1 else 'scan')
        headers.append(dict(sample_id=sid,status='published_parameter_header_read',experiment=e,revision='release',repo_id='repo',published_path=sid,published_identity={},publication_recovery={}))
        reports.append(dict(sample_id=sid,revision='release',path=sid,sha256='report-'+sid,data=dict(required_physics_parameters={},first_contact_frame={'book_can':None if i==0 else 100},observed_outcome='contact')))
        states.append(dict(sample_id=sid,revision='release',reference_state_sha256='state-'+sid,solver_contract_sha256='different' if split_middle_solver and i==1 else 'same',published_path=sid,experiment=e))
        roster.append(dict(sample_id=sid,release_prefix='prefix',video_paths={}))
    inputs={'t03_current_parameter_headers_20261019.json':headers,'t03_current_original_event_reports.json':reports,
            't03_completed_state_contracts_20261020.json':states,'t03_current_selection_20261019.json':[dict(files=[dict(path='catalog/t03_880_selection.jsonl',text='\n'.join(json.dumps(r) for r in roster))])]}
    for name,data in inputs.items():(tmp_path/name).write_text(json.dumps(data),encoding='utf-8')
    binder.main()
    output=tmp_path/'original_value_distance_ledger'
    parameters=[json.loads(line) for line in (output/'t03_published_parameters.jsonl').read_text().splitlines()]
    rows=[json.loads(line) for line in (output/'t03_supplemental_sample_distances.jsonl').read_text().splitlines()]
    assert len(parameters)==3
    assert [r['reference_state_sha256'] for r in parameters]==['state-0','state-1','state-2']
    assert len(rows)==(2 if split_middle_solver else 3)
    assert all(r['normalization_span']==1 for r in rows)
    assert all(r['normalized_distance_lower']<=r['normalized_distance_upper'] for r in rows)
    assert {r['original_boundary_interval'][1] for r in rows}==({2.} if split_middle_solver else {1.5})
