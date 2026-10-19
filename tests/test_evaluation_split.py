"""Test fixed-list integrity with synthetic records, without dataset videos."""
import copy
import json
from pathlib import Path

import pytest

from physedit import evaluation_split as split


def fixture(tmp_path, monkeypatch):
    policy = copy.deepcopy(split.release())
    core, reserve = [], []
    for event in range(1,21):
        for rank in range(1,10):
            row = dict(clip_id=f'T{event:02}_{rank}', anonymous_id=f'clip_{event}_{rank}',
                       event=f'T{event:02}', sample_id=f'sample_{event}_{rank}',
                       source_class=('Isaac_directory_source_physics_unconfirmed' if (event,rank)==(6,4)
                                     else 'Genesis_source_candidate'),
                       sha256='a'*64, scientific_admission='pending_per_task_and_source_audit',
                       training_group_exclusion_applied=False, previous_v2_split='train',
                       limitations='retain pending conditions', parameters={'gravity_mps2':1.62},
                       membership='fixed_core100_v1' if rank<6 else 'reserve',
                       benchmark_pool={'test_id':'ID_candidate_pending_group_holdout',
                                       'test_ood_1':'OOD-1', 'test_ood_2':'OOD-2'}[split.split_for(f'T{event:02}',policy)])
            (core if rank<6 else reserve).append(row)
    (tmp_path/'PROTOCOL.md').write_text('Synthetic protocol\n')
    write(tmp_path/'core100.jsonl',core);write(tmp_path/'reserve80.jsonl',reserve)
    freeze=dict(version=policy['version'],core_total=100,
                core_membership_sha256=policy['core_membership_sha256'],training_split_modified=False,
                files=[dict(path=name,sha256=split.digest(tmp_path/name),bytes=(tmp_path/name).stat().st_size)
                       for name in ('PROTOCOL.md','core100.jsonl','reserve80.jsonl')])
    (tmp_path/'FREEZE.json').write_text(json.dumps(freeze))
    policy['files']={name:split.digest(tmp_path/name) for name in policy['files']}
    monkeypatch.setattr(split,'release',lambda:policy)
    return core, reserve, policy


def write(path, rows):
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))


def rebind(tmp_path, policy):
    freeze=json.loads((tmp_path/'FREEZE.json').read_text())
    for entry in freeze['files']:
        p=tmp_path/entry['path'];entry.update(sha256=split.digest(p),bytes=p.stat().st_size)
    (tmp_path/'FREEZE.json').write_text(json.dumps(freeze))
    policy['files']={name:split.digest(tmp_path/name) for name in policy['files']}


def test_all_core_records_retained_and_no_reserve_substitution(tmp_path,monkeypatch):
    core,reserve,_=fixture(tmp_path,monkeypatch)
    assigned,spare,report=split.load(tmp_path)
    assert len(assigned)==100 and len(spare)==len(reserve)
    assert all(row['split']=='reserve' for row in spare)
    for before,after in zip(core,assigned):
        assert {k:v for k,v in after.items() if k!='split'}=={
            k:v for k,v in before.items() if k not in ('previous_v2_split','benchmark_pool')}
    assert all('previous_v2_split' not in r and 'benchmark_pool' not in r for r in assigned+spare)
    assert 'previous_v2_split' not in report
    assert report['training_policy']['excluded_events']==['T03','T20','T11','T19']
    assert report['split_counts']=={'test_id':80,'test_ood_1':10,'test_ood_2':10}
    assert report['membership_frozen'] is True and report['formal_test_ready'] is False
    assert report['source_classes']['Isaac_directory_source_physics_unconfirmed']==1
    assert report['scientific_admission']=={'pending_per_task_and_source_audit':100}


@pytest.mark.parametrize('name',['FREEZE.json','PROTOCOL.md','core100.jsonl','reserve80.jsonl'])
def test_changed_published_bytes_rejected(tmp_path,monkeypatch,name):
    fixture(tmp_path,monkeypatch);(tmp_path/name).write_text('changed')
    with pytest.raises(ValueError,match='sha256_mismatch'):
        split.materialize(tmp_path,tmp_path/'output')
    assert not (tmp_path/'output').exists()


@pytest.mark.parametrize('change,error',[
    ('omit','count_mismatch'),('duplicate','duplicate_anonymous_id'),
    ('pool','pool_or_membership'),('training','training_status_drift'),
    ('event','event_coverage'),
])
def test_semantic_integrity_independent_of_file_hashes(tmp_path,monkeypatch,change,error):
    core,_,policy=fixture(tmp_path,monkeypatch)
    if change=='omit':core.pop()
    if change=='duplicate':core[1]['anonymous_id']=core[0]['anonymous_id']
    if change=='pool':core[0]['benchmark_pool']='OOD-1'
    if change=='training':core[0]['training_group_exclusion_applied']=True
    if change=='event':core[0]['event']='T20'
    write(tmp_path/'core100.jsonl',core);rebind(tmp_path,policy)
    with pytest.raises(ValueError,match=error):split.load(tmp_path)


def test_materialization_keeps_sources_and_refuses_overwrite(tmp_path,monkeypatch):
    fixture(tmp_path,monkeypatch)
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    result=split.materialize(tmp_path,tmp_path/'output')
    assert result['registered']==100 and len(result['output_files_sha256'])==5
    assert all((tmp_path/name).read_bytes()==raw for name,raw in before.items())
    outputs=[json.loads(line) for p in (tmp_path/'output').glob('*.jsonl')
             for line in p.read_text().splitlines()]
    assert len(outputs)==280
    assert all('previous_v2_split' not in row and 'benchmark_pool' not in row for row in outputs)
    assert all(row['split']=='reserve' for row in [json.loads(line) for line in
        (tmp_path/'output/reserve80.jsonl').read_text().splitlines()])
    with pytest.raises(FileExistsError):split.materialize(tmp_path,tmp_path/'output')


def test_release_descriptor_matches_joint_event_protocol():
    protocol=split.release()
    plan=json.loads((Path(__file__).parents[1]/'docs/joint_split_v3/plan.json').read_text())
    assert protocol['test_ood_1']==plan['test_ood_1']
    assert protocol['test_ood_2']==plan['test_ood_2']
    assert protocol['revision']==plan['evaluation_sets']['fixed_core100']['revision']
    assert protocol['core_total']==100 and protocol['reserve_total']==80


def test_current_training_policy_keeps_all_ood_events_out():
    protocol=split.release()
    policy=protocol['training_policy']
    held_out=set(protocol['test_ood_1']+protocol['test_ood_2'])
    assert set(policy['excluded_events'])==held_out
    assert set(policy['training_events'])=={f'T{n:02}' for n in range(1,21)}-held_out
    assert policy['excluded_memberships']==['fixed_core100_v1','reserve']
    assert policy['exclude_all_verified_source_relatives'] is True
    assert policy['separate_validation_split'] is False
    plan=json.loads((Path(__file__).parents[1]/'docs/joint_split_v3/plan.json').read_text())
    assert plan['active_partition']=='fixed_core100'
    assert plan['evaluation_sets']['fixed_core100']['training_policy']==policy
