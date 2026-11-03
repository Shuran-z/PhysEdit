import copy
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

from physedit import boundary
from physedit.native_boundary import model_contract,coverage
from physedit.runners import boundary_registered as bridge
from physedit.runners.media_contract import seal_completion,validate_video
def prepared():
    from physedit.core100_critical import ROOT,load
    pointer=ROOT/'catalog/prepared_core100_critical_protocol_v4.json'
    value=json.loads(pointer.read_text())
    return load((pointer.parent/value['registry']).resolve(),value['registry_sha256'])


def fixture_spec(root,horizon=1.):
    image=root/'condition.png';assert cv2.imwrite(str(image),np.full((64,80,3),80,np.uint8))
    inputs=[];answers=[]
    for i in range(2):
        sid='p'+str(i);n=4*int(np.ceil(horizon*24/4))+1
        inputs.append(dict(sample_id=sid,clip_id='T15_C0'+str(i+1),condition_image=str(image),condition_sha256=boundary.digest(image),
            prompt='Fixed camera. Initial speed 1 m/s.',seed=i,num_frames=n,fps=24.,evaluation_duration_s=horizon,source_width=80,source_height=64))
        answers.append(dict(sample_id=sid,scene_id='T15',source_group_id='fixture',family_id='speed',point_id=sid,
            theta=i,target_event='fall',events={'fall':i},gravity=9.81,pair_ids=['fixture_pair'],
            inversion=dict(status='not_applicable',reason='Synthetic software fixture, not physics validation.')))
    ip=root/'inputs.jsonl';ap=root/'answers.jsonl';boundary.write_rows(ip,inputs);boundary.write_rows(ap,answers)
    source=root/'source_spec.json';boundary.write_json(source,dict(model='FIXTURE_ONLY',inputs=str(ip),answers=str(ap)))
    return source


def test_h3_native_clock_rejects_14_long_windows_without_modifying_physical_inputs(tmp_path):
    data,path=prepared();from physedit.core100_critical import prepare,sha
    plan=tmp_path/'input';prepare(plan,'PREFLIGHT_ONLY',fps=24.,seeds=(0,1,2),registry_path=path,expected_sha256=sha(path))
    original=(plan/'inputs.jsonl').read_bytes();result=bridge.configure(plan/'spec.json',tmp_path/'h3',model='minimax_h3',model_dir='LOCAL_WEIGHTS_NOT_LOADED')
    cap=result['native_generation'];assert cap['registered']==300 and cap['compatible']==258 and cap['unsupported_count']==42
    assert cap['native_horizon_s']==5.125 and not cap['execution_supported']
    expected={'T02_C01','T02_C02',*[f'T05_C{i:02}'for i in range(1,6)],'T17_C04','T17_C05',*[f'T19_C{i:02}'for i in range(1,6)]}
    assert {r['clip_id']for r in cap['unsupported']}==expected
    configured=json.loads((tmp_path/'h3/spec.json').read_text());native=boundary.read_rows(configured['inputs']);old=boundary.read_rows(plan/'inputs.jsonl')
    assert all({k:v for k,v in a.items()if k!='num_frames'}=={k:v for k,v in b.items()if k!='num_frames'}for a,b in zip(old,native))
    assert original==(plan/'inputs.jsonl').read_bytes()
    with pytest.raises(ValueError,match='before_generation: 42'):boundary.run(configured,tmp_path/'should_not_start')
    assert not(tmp_path/'should_not_start').exists()


def test_registered_long_native_model_covers_all100_windows(tmp_path):
    _,path=prepared();from physedit.core100_critical import prepare,sha
    plan=tmp_path/'input';prepare(plan,'PREFLIGHT_ONLY',fps=24.,seeds=(0,1,2),registry_path=path,expected_sha256=sha(path))
    result=bridge.configure(plan/'spec.json',tmp_path/'cosmos3',model='cosmos3_nano',model_dir='LOCAL_WEIGHTS_NOT_LOADED')
    assert result['native_generation']['execution_supported']and result['native_generation']['compatible']==300
    spec=json.loads((tmp_path/'cosmos3/spec.json').read_text());assert {r['num_frames']for r in boundary.read_rows(spec['inputs'])}=={189}


def test_native_media_bridge_preserves_bytes_clock_and_input_bindings(tmp_path,monkeypatch):
    source=fixture_spec(tmp_path);bridge.configure(source,tmp_path/'configured',model='minimax_h3',model_dir='FIXTURE_NOT_LOADED')
    spec=json.loads((tmp_path/'configured/spec.json').read_text());spec['generation_command']=[sys.executable,'-c','pass']
    # Boundary stages real prompts/conditions. A synthetic native producer
    # supplies actual playable media; no model, fake timestamps or VLM runs.
    def no_media(*a,**kw):raise ValueError('fixture staging only')
    with monkeypatch.context()as m:
        m.setattr(boundary,'media',no_media);boundary.run(spec,tmp_path/'run')
    manifest=tmp_path/'run/generation_rows.jsonl'
    from physedit.runners import registered_oneclick
    called=[]
    def producer(reg,manifest,root):
        for r in boundary.read_rows(manifest):
            called.append(r)
            assert r['num_frames']==124 and r['output_fps']==24
            assert not set(r)&{'events','boundary','theta','reference_events','gravity'}
            for name in ['generated_video','generated_video_resized_to_source']:
                p=Path(r[name]);writer=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'mp4v'),24,(80,64));assert writer.isOpened()
                for i in range(124):writer.write(np.full((64,80,3),i+20,np.uint8))
                writer.release()
            seal_completion(r,settings={'synthetic_native_producer':True})
        return 0
    monkeypatch.setattr(registered_oneclick,'run',producer)
    registration=tmp_path/'configured/native_registration.json'
    assert bridge.run_bridge(registration,boundary.digest(registration),manifest,tmp_path/'run/native_model_driver')==0
    for outer,inner in zip(boundary.read_rows(manifest),called):
        out=Path(outer['out_dir'])/'resized.mp4';native=Path(inner['generated_video_resized_to_source'])
        assert out.read_bytes()==native.read_bytes()
        proof=validate_video(out,fps=24,frames=124,width=80,height=64);assert proof['full_decode']
        receipt=json.loads((Path(outer['out_dir'])/'native_window_completion.json').read_text())
        assert receipt['interpolation_or_clock_changes']is False
        assert receipt['native_input_sha256']['condition_image']==boundary.digest(outer['condition_image'])


def test_unsupported_or_tampered_registration_never_loads_a_model(tmp_path,monkeypatch):
    reg=dict(model='minimax_h3',model_dir='NOT_LOADED',frames=124,fps=24,generation_runtime={})
    path=tmp_path/'reg.json';boundary.write_json(path,reg);manifest=tmp_path/'rows.jsonl'
    boundary.write_rows(manifest,[dict(sample_id='too_long',num_frames=165,output_fps=24,out_dir=str(tmp_path/'generated/too_long'))])
    with pytest.raises(ValueError,match='before_generation'):bridge.run_bridge(path,boundary.digest(path),manifest,tmp_path/'driver')
    assert not(tmp_path/'driver').exists()
    with pytest.raises(ValueError,match='registration_changed'):bridge.run_bridge(path,'0'*64,manifest,tmp_path/'bad')


def test_existing_native_attempt_is_retained_without_restart(tmp_path):
    reg=dict(model='minimax_h3',model_dir='NOT_LOADED',frames=124,fps=24,generation_runtime={})
    path=tmp_path/'reg.json';boundary.write_json(path,reg);dest=tmp_path/'generated/p0';(dest/'native').mkdir(parents=True)
    manifest=tmp_path/'rows.jsonl';boundary.write_rows(manifest,[dict(sample_id='p0',num_frames=124,output_fps=24,out_dir=str(dest))])
    with pytest.raises(ValueError,match='no_restart'):bridge.run_bridge(path,boundary.digest(path),manifest,tmp_path/'driver')


def test_native_profile_cannot_be_extended_by_editing_a_count():
    reg=copy.deepcopy(model_contract('minimax_h3'));reg['native_frames']=175
    with pytest.raises(ValueError,match='native_model_contract_changed'):coverage(reg,[])
