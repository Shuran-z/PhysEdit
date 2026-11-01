"""Review admission must reject incomplete media and keep source truth private."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import types

import pytest


SOURCE=Path(__file__).resolve().parents[1]/'review/cvpr_experiments_20261031/auxiliary_review/run_review.py'


def test_registered_metric_is_kept_distinct_from_uncalibrated_visual_proxy():
    tree=ast.parse(SOURCE.read_text(encoding='utf8'))
    node=next(n for n in tree.body if isinstance(n,ast.Assign)and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='EVENTS')
    events=ast.literal_eval(node.value)
    catalogue=json.loads((SOURCE.parents[3]/'annotation_site/resources/event_contracts.json').read_text(encoding='utf8'))
    original=catalogue['clips']['T05_C03']['events']['gate_passage']
    assert set(events)=={'gate_passage','visible_full_clearance'}
    assert events['gate_passage']['metric_rule']==original['metric_rule']
    assert events['gate_passage']['calibration_required'] is True
    assert events['gate_passage']['calibration_supplied'] is False
    assert 'Return uncertain' in events['gate_passage']['definition']
    assert 'never substitute' in events['visible_full_clearance']['role']


def fixture(tmp_path,monkeypatch):
    # Exercise the real manifest builder; codec validation remains a live-run gate.
    tree=ast.parse(SOURCE.read_text(encoding='utf8'))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in {'sha','save','prepare'}]
    ns={'Path':Path,'json':json,'hashlib':hashlib,'R':tmp_path/'review','PARENT':tmp_path,
        'GROUPS':['controlled_friction_sweep','controlled_friction_geometry'],
        'ARMS':['original_base','lora_step1000'],'TARGET':'original phone','EVENTS':{'gate_passage':'observable full clearance'}}
    ns['R'].mkdir()
    class Container:
        streams=types.SimpleNamespace(video=[types.SimpleNamespace(average_rate=16)])
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def decode(self,**kwargs):return iter(range(129))
    monkeypatch.setitem(sys.modules,'av',types.SimpleNamespace(open=lambda p:Container()))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),ns)
    for group in ns['GROUPS']:
        root=tmp_path/group;root.mkdir();inputs=[]
        for i in range(18):
            inputs.append(dict(id='case'+str(i),prompt_sha256='prompt'+str(i),condition_sha256='image',seed=0,
                               friction_coefficient=999,reference_answer='SECRET_TRUTH'))
        p=root/'inputs.jsonl';p.write_text(''.join(json.dumps(r)+'\n'for r in inputs))
        (root/'PLAN.json').write_text(json.dumps({'inputs_sha256':ns['sha'](p)}))
        for arm in ns['ARMS']:
            folder=root/arm;folder.mkdir();records=[]
            for row in inputs:
                video=folder/(row['id']+'.mp4');video.write_bytes((arm+row['id']).encode())
                records.append(dict(id=row['id'],arm=arm,status='completed',file=video.name,video_sha256=ns['sha'](video),
                                    prompt_sha256=row['prompt_sha256'],condition_sha256='image',seed=0))
            (folder/'results.jsonl').write_text(''.join(json.dumps(r)+'\n'for r in records))
    return ns


def test_seventy_two_observation_jobs_have_no_answers_or_arm_metadata(tmp_path,monkeypatch):
    ns=fixture(tmp_path,monkeypatch);ns['prepare']()
    for stage,window in [('quality',8),('events',5)]:
        rows=list(map(json.loads,(ns['R']/(stage+'_jobs.jsonl')).read_text().splitlines()))
        assert len(rows)==72 and len({r['sample_id']for r in rows})==72
        for row in rows:
            assert set(row)=={'sample_id','video','video_sha256','target','window_s'}|({'events'}if stage=='events'else set())
            assert row['window_s']==window
            assert 'SECRET_TRUTH'not in json.dumps(row)
            assert 'original_base'not in row['sample_id'] and 'lora_step1000'not in row['sample_id']


def test_changed_video_is_rejected_before_model_launch(tmp_path,monkeypatch):
    ns=fixture(tmp_path,monkeypatch)
    (tmp_path/ns['GROUPS'][0]/ns['ARMS'][0]/'case0.mp4').write_bytes(b'changed')
    with pytest.raises(AssertionError):ns['prepare']()


def test_missing_registered_generation_is_not_silently_omitted(tmp_path,monkeypatch):
    ns=fixture(tmp_path,monkeypatch)
    p=tmp_path/ns['GROUPS'][0]/ns['ARMS'][0]/'results.jsonl'
    p.write_text('\n'.join(p.read_text().splitlines()[:-1])+'\n')
    with pytest.raises(AssertionError):ns['prepare']()
