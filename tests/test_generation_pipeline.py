"""Real CPU media + artificial observations; no generative model or real fit."""
import copy
import hashlib
import json
import os
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from physedit import phyediting as pipeline
from physedit.runners import diffusers_i2v as runner, media_contract as media
from scripts import phyediting_gen as gen, sam31_frontend as frontend, phyediting_gen_summary as summary


def video(path, frames=45, fps=30):
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*('FFV1' if path.suffix == '.avi' else 'mp4v')), fps, (80,64))
    assert writer.isOpened()
    for i in range(frames):
        rgb = np.full((64,80,3), 190, np.uint8)
        rgb[20:35,20:35] = 20
        writer.write(rgb)
    writer.release()
    return path


def item(id='ok', **kw):
    result = dict(id=id, event='T08', gravity=9.81, fps=30, camera_id='cam01', image_size=[80,64],
                  trajectory='source_g03_fixture', video='source.avi', object_name='book', camera={}, object={},
                  motion={'v0':[1,0,0]}, window=dict(start_frame=25,max_frames=10), split='test_id', sensitivity_px=20.)
    return {**result, **kw}


def dump(path, rows):
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return path


def reference_evidence(tmp, items):
    # Artificial reference qualification for CPU integration tests only.
    catalog = dump(tmp/'reference_items.jsonl', items)
    predictions = dump(tmp/'reference_predictions.jsonl', [dict(id=i['id'], target=i['gravity'],
        prediction=dict(status='ok', scenario='projectile', gravity=i['gravity'],
                        frames=i['window']['max_frames'])) for i in items])
    return dict(benchmark_items=str(catalog), reference_predictions=str(predictions),
                benchmark_sha256=media.sha256(catalog), reference_predictions_sha256=media.sha256(predictions))


@pytest.fixture
def registered(tmp_path):
    video(tmp_path/'source.avi')
    items = [item(), item('missing', video='missing.avi'), item('unsupported',event='T01'),
             item('short',window=dict(start_frame=25,max_frames=2))]
    ip = dump(tmp_path/'items.jsonl',items)
    out = tmp_path/'input'
    gen.build(SimpleNamespace(items=ip, out=out, data_root=str(tmp_path),source_root=str(tmp_path),host_root=str(out),
                              min_window_frames=8,max_end_frame=170,per_gravity=None,seed=1,
                              applicability=reference_evidence(tmp_path,items)))
    rows = gen._json_rows(out/'template.jsonl')
    return ip, out, rows


def test_builder_preserves_failures_and_no_default_subsample(registered):
    ip, out, rows = registered
    assert len(rows) == 4 and len(set(r['sample_id'] for r in rows)) == 4
    assert rows[0]['input_failure'] is None
    assert [r['input_failure'] for r in rows[1:]] == ['missing_source_video', 'unsupported_registered_prompt_or_gravity',
                                                   'not_applicable_registered_window']
    assert len(gen._json_rows(out/'input_failures.jsonl')) == 3
    assert (out/'videos.txt').read_text().splitlines() == ['source.avi','missing.avi','source.avi','source.avi']


@pytest.mark.parametrize('mutation,reason', [
    ('fps','video_fps_mismatch'), ('short','video_frame_count_mismatch'), ('junk','video_decode_failure'),
    ('dimensions','video_dimensions_mismatch'), ('pts','video_timestamp_mismatch')])
def test_complete_media_contract_rejects_faults(tmp_path, monkeypatch, mutation,reason):
    path = video(tmp_path/'clip.avi',frames=5,fps=30)
    if mutation == 'junk': path.write_bytes(b'not an mp4 video')
    if mutation == 'pts':
        real = cv2.VideoCapture
        class Capture:
            def __init__(self,*a): self.cap=real(*a)
            def __getattr__(self,n): return getattr(self.cap,n)
            def get(self,k): return 0 if k == cv2.CAP_PROP_POS_MSEC else self.cap.get(k)
        monkeypatch.setattr(cv2,'VideoCapture',Capture)
    with pytest.raises(ValueError,match=reason):
        media.validate_video(path,fps=16 if mutation=='fps' else 30, frames=6 if mutation=='short' else 5,
                             width=81 if mutation=='dimensions' else 80,height=64)


def runner_row(tmp):
    row = dict(sample_id='case',out_dir=str(tmp/'case'),generated_video=str(tmp/'case/raw.mp4'),
               generated_video_resized_to_source=str(tmp/'case/resized.mp4'),source_video=str(tmp/'source.avi'),
               source_width=80,source_height=64,num_frames=5,output_fps=30)
    for k in ('condition_image','prompt_file','negative_prompt_file'):
        row[k]=str(tmp/(k+'.txt')); Path(row[k]).write_text(k)
    return row


def runner_args(tmp,row):
    return ['--generation-manifest',str(dump(tmp/'rows.jsonl',[row])), '--model-dir',str(tmp/'model'),
            '--pipeline','ltx_i2v','--skip-existing']


def test_corrupt_skip_refuses_model_and_keeps_bytes(tmp_path,monkeypatch):
    row=runner_row(tmp_path); Path(row['out_dir']).mkdir()
    path=Path(row['generated_video_resized_to_source']); path.write_bytes(b'not an mp4 video')
    monkeypatch.setattr(runner,'_load_pipeline',lambda *a: pytest.fail('must not load a model'))
    assert runner.main(runner_args(tmp_path,row)) == 1
    assert path.read_bytes() == b'not an mp4 video'
    assert gen._json_rows(tmp_path/'ltx_i2v_generation_status.jsonl')[-1]['status']=='failed'


def test_runner_atomic_completion_skip_and_source_drift(tmp_path,monkeypatch):
    row=runner_row(tmp_path)
    calls=[]
    monkeypatch.setattr(runner,'_load_pipeline',lambda *a: calls.append('fixture_model') or object())
    monkeypatch.setattr(runner,'_generate_one',lambda pipe,args,r,path,log: video(path,frames=5,fps=30))
    monkeypatch.setattr(runner,'_resize_to_source',lambda raw,source,path,**kw: video(path,frames=5,fps=30))
    args=runner_args(tmp_path,row)
    assert runner.main(args)==0 and calls==['fixture_model']
    assert media.verified_completion(row)['media']['full_decode']
    assert runner.main(args)==0 and calls==['fixture_model']
    Path(row['condition_image']).write_text('drift')
    assert runner.main(args)==1 and calls==['fixture_model']


def test_interrupted_claim_refuses_retry(tmp_path,monkeypatch):
    row=runner_row(tmp_path); Path(row['out_dir']).mkdir()
    (Path(row['out_dir'])/'generation.claim').write_text('interrupted')
    monkeypatch.setattr(runner,'_load_pipeline',lambda *a:pytest.fail('must not load'))
    assert runner.main(runner_args(tmp_path,row))==1


def test_frontend_rejects_wrong_actual_clock(tmp_path):
    path=video(tmp_path/'clip.avi',frames=5,fps=30)
    job=dict(id='case',video=str(path),video_sha256=media.sha256(path),frames=[1,2,3,4],prompt_frame=0,
             scene_boxes={'book':[20,20,35,35]},target_name='book',fps=16)
    assert frontend.validate_job(job)['input_failure']=='video_fps_mismatch'
    job['fps']=30;job['frames']=[1,2,3,5]
    assert frontend.validate_job(job)['input_failure']=='registered_frame_outside_video'


def bound_track(tmp,row):
    path=video(Path(row['generated_video_resized_to_source']),frames=row['num_frames'],fps=row['output_fps'])
    frames=[1,2,3,4]
    details=dict(id=row['sample_id'],video_sha256=media.sha256(path),frames=frames,statuses=['fixture']*4)
    receipt=dump(tmp/'measurements.jsonl',[details])
    return dict(id=row['sample_id'],fps=row['output_fps'],video=str(path),video_sha256=details['video_sha256'],
                frontend='sam31_single_view_frozen_v4',frontend_manifest_sha256=media.sha256(frontend.FROZEN/'manifest.json'),
                measurements_path=str(receipt),measurements_sha256=media.sha256(receipt),reasons=details['statuses'],
                tracks={'book':dict(frames=frames,xyxy=[[20,20,35,35]]*4)})


@pytest.mark.parametrize('change,reason', [({'frontend':'sam2_stale'},'frontend_version'),
    ({'fps':4},'track_manifest_fps'),({'video_sha256':'stale'},'track_video_sha256'),
    ({'frontend_manifest_sha256':'wrong'},'frontend_manifest'),({'measurements_sha256':'wrong'},'measurement_receipt')])
def test_provenance_refused_before_fitter(tmp_path,monkeypatch,change,reason):
    row=runner_row(tmp_path);t=bound_track(tmp_path,row);t.update(change)
    monkeypatch.setattr(gen,'safe_fit',lambda *a:pytest.fail('must not fit'))
    result=gen._score_fixed_window({**row,'condition_frame_index':23},item(),t)
    assert result['status']=='input_failure' and reason in result['reason']


def test_summary_original_denominator_and_repeated_seeds():
    rows=[dict(sample_id='seed1',item_id='i',gravity_truth=10,split='test_id'),
          dict(sample_id='seed2',item_id='i',gravity_truth=10,split='test_id'),
          dict(sample_id='missing',item_id='j',gravity_truth=10,split='test_ood1',input_failure='missing_source')]
    result=summary.report(rows,[dict(id='seed1',status='ok',gravity=11),dict(id='seed2',status='at_bound',gravity=10)],{})
    assert result['registered']==3 and result['scored']==1 and result['failed']==2
    assert result['coverage_percent']==pytest.approx(100/3) and result['failure_rate_percent']==pytest.approx(200/3)
    assert result['mean_error_percent']==pytest.approx(10) and len(result['failures'])==2
    assert result['groups']['split']['test_ood1']['failures'][0]['reason']=='missing_source'


@pytest.mark.parametrize('value', [True, False, 0, -9.81, float('nan'), float('inf')])
def test_invalid_numeric_results_cannot_count_as_coverage(value):
    result=summary.report([dict(sample_id='a',gravity_truth=9.81)],
                          [dict(id='a',status='ok',gravity=value)],{})
    assert result['scored']==0 and result['failed']==1 and result['coverage_percent']==0
    assert result['status_counts']=={'invalid_numeric_prediction':1}


@pytest.mark.parametrize('existing', [False, True])
def test_status_rejects_unregistered_run(tmp_path,existing):
    from physedit.__main__ import main
    root=tmp_path/'run'
    if existing:root.mkdir()
    with pytest.raises(SystemExit) as error:
        main(['status','phyediting','--run-dir',str(root)])
    assert error.value.code==2


def test_plan_cli_never_imports_models_or_creates_outputs(tmp_path,monkeypatch,capsys):
    spec=dict(items=str(dump(tmp_path/'items',[item()])),data_root=str(tmp_path),compact=str(tmp_path),model='ltx_i2v',
              model_dir='missing_model',frames=81,fps=16,sam3='missing_sam',checkpoint='missing_weight')
    sp=tmp_path/'spec.json';sp.write_text(json.dumps(spec))
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw:pytest.fail('must not execute'))
    from physedit.__main__ import main
    assert main(['run','phyediting','--spec',str(sp),'--run-dir',str(tmp_path/'run')])==0
    assert not (tmp_path/'run').exists() and 'torch' not in sys.modules
    assert json.loads(capsys.readouterr().out)['execution_requested'] is False


def test_cpu_one_click_missing_sources_complete_ledger(tmp_path,monkeypatch):
    # Explicit CPU synthetic control: every input is missing, so no model/fit.
    spec=dict(items=str(dump(tmp_path/'items',[item('a',video='absent'),item('b',event='T01')])),
              data_root=str(tmp_path),compact=str(tmp_path/'absent_compact'),model='ltx_i2v',model_dir='no_model',
              frames=81,fps=16,sam3='no_sam',checkpoint='no_weights')
    monkeypatch.setattr(gen,'safe_fit',lambda *a:pytest.fail('must not fit'))
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw:pytest.fail('must not generate'))
    result=pipeline.pipeline(spec,tmp_path/'run')
    assert result['registered']==2 and result['failed']==2 and result['coverage_percent']==0
    assert len(frontend.read_rows(tmp_path/'run/sam31/tracks_v4.jsonl'))==2
    assert (tmp_path/'run/completed.json').exists()
    with pytest.raises(FileExistsError):pipeline.pipeline(spec,tmp_path/'run')


def missing_source_spec(tmp_path):
    return dict(items=str(dump(tmp_path/'items',[item('a',video='absent')])),
                data_root=str(tmp_path),compact=str(tmp_path/'absent_compact'),model='ltx_i2v',
                model_dir='no_model',sam3='no_sam',checkpoint='no_weights',
                generation_runtime={'gpu_devices':'3'})


@pytest.mark.parametrize('inherited', [None, '8'])
def test_configured_gpu_applies_to_frontend_and_restores_parent(tmp_path,monkeypatch,inherited):
    spec=missing_source_spec(tmp_path)
    if inherited is None:monkeypatch.delenv('CUDA_VISIBLE_DEVICES',raising=False)
    else:monkeypatch.setenv('CUDA_VISIBLE_DEVICES',inherited)
    original=frontend.run
    captured=[]
    def observe(*args):
        captured.append(os.environ.get('CUDA_VISIBLE_DEVICES'))
        return original(*args)
    monkeypatch.setattr(frontend,'run',observe)
    result=pipeline.pipeline(spec,tmp_path/'run')
    assert captured==['3'] and result['failed']==1
    assert result['evaluation_metrics']==['gravtrace']
    assert json.loads((tmp_path/'run/completed.json').read_text())['evaluation_metrics']==['gravtrace']
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==inherited


def test_gpu_environment_restored_after_controller_failure(tmp_path,monkeypatch):
    spec=missing_source_spec(tmp_path)
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','8')
    def fail(*args):
        assert os.environ['CUDA_VISIBLE_DEVICES']=='3'
        raise RuntimeError('fixture controller failure')
    monkeypatch.setattr(gen,'build',fail)
    with pytest.raises(RuntimeError,match='fixture controller failure'):
        pipeline.pipeline(spec,tmp_path/'run')
    assert os.environ['CUDA_VISIBLE_DEVICES']=='8'
    assert len(frontend.read_rows(tmp_path/'run/controller_failures.jsonl'))==1


@pytest.mark.parametrize('evaluation', [
    {'metrics':['qwen']}, {'metrics':['gravtrace','unknown']}, {'metrics':[]},
    {'metrics':'gravtrace'}, {'metrics':['gravtrace','gravtrace']},
    {'metrics':['gravtrace'],'qwen_model_dir':'unused'}, None])
def test_unavailable_or_invalid_evaluation_rejected_before_output(tmp_path,monkeypatch,evaluation):
    spec=missing_source_spec(tmp_path);spec['evaluation']=evaluation
    monkeypatch.setattr(gen,'build',lambda *a:pytest.fail('must not start pipeline'))
    with pytest.raises(ValueError,match='evaluation|Unsupported'):
        pipeline.pipeline(spec,tmp_path/'run')
    assert not (tmp_path/'run').exists()


def test_plan_declares_actual_metrics_and_gpu_scope(tmp_path):
    spec=missing_source_spec(tmp_path);spec['evaluation']={'metrics':['gravtrace']}
    result=pipeline.execution_plan(spec)
    assert result['evaluation_metrics']==['gravtrace']
    assert result['gpu_devices']=='3'
    assert 'qwen' not in result['stages']


@pytest.mark.parametrize('where,key', [('spec','qwen'),('runtime','gup_devices')])
def test_unknown_settings_are_not_silently_ignored(tmp_path,where,key):
    spec=missing_source_spec(tmp_path)
    (spec if where=='spec' else spec['generation_runtime'])[key]='unused'
    with pytest.raises(ValueError,match='Unsupported'):
        pipeline.execution_plan(spec)


@pytest.mark.parametrize('extra_metrics',[False,True])
def test_cpu_one_click_success_and_failure_all_stages(tmp_path,monkeypatch,extra_metrics):
    # Real CPU source/generated media and V4; only model observations and fit are artificial.
    video(tmp_path/'source.avi',frames=75)
    model = tmp_path/'fixture_model'
    model.mkdir()
    spec=dict(items=str(dump(tmp_path/'items',[item(window=dict(start_frame=25,max_frames=10)),
                          item('missing',video='absent')])),data_root=str(tmp_path),compact='unused',
              model='ltx_i2v',model_dir=str(model),frames=81,fps=16,sam3='fixture_sam',checkpoint='fixture_weight',
              generation_runtime=dict(ffmpeg=sys.executable,gpu_devices='3'))
    spec['applicability'] = reference_evidence(tmp_path, gen._json_rows(spec['items']))
    if extra_metrics:
        from physedit import evaluations as ev, qwen_judge as judge
        spec['evaluation']=dict(metrics=['gravtrace','vp','qwen'],qwen=dict(backend='api',model='Qwen-fixture',base_url='http://localhost:1/v1'))
        answer={k:dict(present=False,severity=0,evidence='synthetic evidence') for k in judge.CATEGORIES}
        answer.update(confidence=.9,insufficient_evidence=False)
        monkeypatch.setattr(ev,'call_api',lambda *a:dict(judgement=answer,raw=json.dumps(answer),served_model='Qwen-fixture'))
    def prompts(args):
        jobs=[dict(id=r['sample_id'],video=r['generated_video_resized_to_source'],prompt_frame=0,
                   objects={'book':[20,20,35,35]}, input_failure=r.get('input_failure')) for r in gen._json_rows(args.rows)]
        dump(Path(args.out),jobs)
    monkeypatch.setattr(gen,'track_jobs',prompts)
    monkeypatch.setattr(frontend, 'validate_runtime', lambda *a: dict(gpu_started=False, fixture=True))
    monkeypatch.setattr(runner,'_load_pipeline',lambda *a:object())
    monkeypatch.setattr(runner,'_generate_one',lambda pipe,args,r,path,log:video(path,frames=r['num_frames'],fps=r['output_fps']))
    monkeypatch.setattr(runner,'_resize_to_source',lambda raw,source,path,**kw:video(path,frames=81,fps=16))
    def invoke(command,**kw):
        assert 'diffusers_i2v.py' in command[1]
        assert kw['env']['CUDA_VISIBLE_DEVICES']=='3'
        return SimpleNamespace(returncode=runner.main(command[2:]))
    monkeypatch.setattr(subprocess,'run',invoke)
    def observations(root,*args):
        assert os.environ['CUDA_VISIBLE_DEVICES']=='3'
        tracks=[]; masks=root/'runs/sam31_visible_projection_full30_masks';masks.mkdir()
        for j in frontend.read_rows(root/'all_jobs.jsonl'):
            if j['input_failure']:continue
            for f in j['frames']:
                mask=np.zeros((64,80),np.uint8);mask[20:35,20:35]=1
                np.savez_compressed(masks/f'{hashlib.sha256(j["id"].encode()).hexdigest()[:12]}_{f}.npz',mask=mask)
            tracks.append(dict(id=j['id'],frames=j['frames'],boxes=[[20,20,35,35]]*len(j['frames']),reasons=['fixture']*len(j['frames'])))
        frontend.write_rows(root/'runs/sam31_visible_projection_full30_tracks.jsonl',tracks)
        return frontend.measure(root)
    monkeypatch.setattr(frontend,'run',observations)
    captured=[]
    monkeypatch.setattr(gen,'safe_fit',lambda sample: captured.append(sample) or
                        dict(id=sample['id'],status='ok',gravity=9.81,frames=len(sample['boxes']['frames'])))
    result=pipeline.pipeline(spec,tmp_path/'run')
    assert result['registered']==2 and result['scored']==1 and result['failed']==1
    assert result['failure_rate_percent']==50 and result['coverage_percent']==50
    assert len(captured)==1 and captured[0]['motion']['speed']==[0,8] and 'v0' not in captured[0]['motion']
    assert captured[0]['offset_mode']=='anchor' and not captured[0]['window']['contact_check']
    assert len(read_rows:=frontend.read_rows(tmp_path/'run/predictions.jsonl'))==2
    assert read_rows[1]['reason']=='missing_source_video'
    if extra_metrics:
        assert result['evaluations']['qwen']['scored']==1
        assert result['evaluations']['vp']['metrics']['trajectory_error_full']['scored']==1
        assert result['evaluations']['vp']['metrics']['camera_motion_full']['scored']==0  # Feature-poor media is insufficient, not zero error.
        assert result['evaluation_failed']==2
        for stage in ('vp','qwen'):
            records=frontend.read_rows(tmp_path/'run/evaluation'/f'{stage}_results.jsonl')
            assert len(records)==2 and 'missing_source_video' in records[1]['reason']
        assert captured[0]['boxes']['frames']==[0,1,2,3]  # Native 16fps window; V/P full-clip masks do not extend it.


def test_survey_never_counts_nonempty_corrupt_video(tmp_path):
    row=runner_row(tmp_path);row['out_dir']=str(tmp_path/'bench/x5/ltx/case')
    path=tmp_path/'bench/x5/ltx/generated/case/resized.mp4';path.parent.mkdir(parents=True)
    row['generated_video_resized_to_source']=str(path);path.write_bytes(b'not an mp4 video')
    dump(tmp_path/'bench/x5/ltx/manifest.jsonl',[row])
    args={'dir':str(tmp_path/'bench'),'media_contract_source':Path(media.__file__).read_text()}
    result=subprocess.run([sys.executable,str(Path(pipeline.__file__).with_name('survey.py')),json.dumps(args)],
                          text=True,capture_output=True,check=True)
    info=json.loads(result.stdout)['items']['x5/ltx']
    assert info['done']==0 and info['validated_files']==[] and info['validation_failures']['case']


def test_changed_input_during_generation_not_sealed(tmp_path,monkeypatch):
    row=runner_row(tmp_path)
    monkeypatch.setattr(runner,'_load_pipeline',lambda *a:object())
    def generate(pipe,args,r,path,log):
        video(path,frames=5,fps=30)
        Path(r['condition_image']).write_text('changed during inference')
    monkeypatch.setattr(runner,'_generate_one',generate)
    monkeypatch.setattr(runner,'_resize_to_source',lambda raw,source,path,**kw:video(path,frames=5,fps=30))
    assert runner.main(runner_args(tmp_path,row))==1
    assert Path(row['generated_video_resized_to_source']).exists()
    assert not media.completion_path(row).exists()


@pytest.mark.parametrize('failure', ['frontend', 'model'])
def test_runtime_failure_preserves_eligible_and_missing_rows_without_inference(tmp_path, monkeypatch, failure):
    video(tmp_path/'source.avi')
    spec = dict(items=str(dump(tmp_path/'items', [item(), item('missing', video='absent')])),
                data_root=str(tmp_path), compact='unused', model='ltx_i2v', model_dir=str(tmp_path/'absent_model'),
                sam3=str(tmp_path/'absent_sam'), checkpoint=str(tmp_path/'absent_checkpoint'))
    spec['applicability'] = reference_evidence(tmp_path, gen._json_rows(spec['items']))
    def prompts(args):
        dump(Path(args.out), [dict(id=r['sample_id'], prompt_frame=0, objects={'book':[20,20,35,35]},
                                  input_failure=r.get('input_failure')) for r in gen._json_rows(args.rows)])
    monkeypatch.setattr(gen, 'track_jobs', prompts)
    if failure == 'model':
        monkeypatch.setattr(frontend, 'validate_runtime', lambda *a: dict(fixture=True, gpu_started=False))
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: pytest.fail('must not start generation or SAM'))
    monkeypatch.setattr(gen, 'safe_fit', lambda *a: pytest.fail('must not fit'))
    result = pipeline.pipeline(spec, tmp_path/'run')
    assert result['registered'] == result['failed'] == 2
    predictions = gen._json_rows(tmp_path/'run/predictions.jsonl')
    assert ('frontend_runtime_failure' if failure == 'frontend' else 'registered_model_dir_missing') in predictions[0]['reason']
    assert predictions[1]['reason'] == 'missing_source_video'


def test_diffusers_load_is_local_only_and_refuses_text_only_api(monkeypatch):
    class ImagePipeline:
        def __call__(self, image, prompt):
            raise AssertionError('must not infer')
        @classmethod
        def from_pretrained(cls, model, **kwargs):
            assert kwargs['local_files_only'] is True
            return cls()
        def to(self, device):
            pass
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(bfloat16='bf16', float16='fp16'))
    monkeypatch.setitem(sys.modules, 'diffusers', SimpleNamespace(LTXImageToVideoPipeline=ImagePipeline))
    assert isinstance(runner._load_pipeline('ltx_i2v', 'local_weights', 'bfloat16', 'none', None), ImagePipeline)
    class TextOnlyPipeline:
        def __call__(self, prompt):
            pass
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            pytest.fail('must refuse before loading weights')
    sys.modules['diffusers'].LTXImageToVideoPipeline = TextOnlyPipeline
    with pytest.raises(ValueError, match='does not accept an image'):
        runner._load_pipeline('ltx_i2v', 'local_weights', 'bfloat16', 'none', None)


def test_controller_keeps_actual_diffusers_failure_in_prediction(tmp_path, monkeypatch):
    video(tmp_path/'source.avi', frames=75)
    weights = tmp_path/'weights'
    weights.mkdir()
    spec = dict(items=str(dump(tmp_path/'items', [item()])), data_root=str(tmp_path), compact='unused',
                model='ltx_i2v', model_dir=str(weights), sam3='fixture_sam', checkpoint='fixture_weight',
                generation_runtime=dict(ffmpeg=sys.executable))
    spec['applicability'] = reference_evidence(tmp_path, gen._json_rows(spec['items']))
    def prompts(args):
        dump(Path(args.out), [dict(id=r['sample_id'], video=r['generated_video_resized_to_source'],
             prompt_frame=0, objects={'book':[20,20,35,35]}, input_failure=r.get('input_failure'))
             for r in gen._json_rows(args.rows)])
    monkeypatch.setattr(gen, 'track_jobs', prompts)
    monkeypatch.setattr(frontend, 'validate_runtime', lambda *a: dict(gpu_started=False, fixture=True))
    def fail_loading(*args):
        raise ValueError('fixture_VAE_shape_mismatch')
    monkeypatch.setattr(runner, '_load_pipeline', fail_loading)
    monkeypatch.setattr(subprocess, 'run', lambda command, **kw: SimpleNamespace(returncode=runner.main(command[2:])))
    monkeypatch.setattr(frontend, 'run', lambda root, *a: frontend.measure(root))
    monkeypatch.setattr(gen, 'safe_fit', lambda *a: pytest.fail('must not fit a failed generation'))
    result = pipeline.pipeline(spec, tmp_path/'run')
    pred = gen._json_rows(tmp_path/'run/predictions.jsonl')[0]
    assert result['registered'] == result['failed'] == 1
    assert 'fixture_VAE_shape_mismatch' in pred['reason']
    assert 'resized.completed.json' not in pred['reason']


def test_diffusers_preserves_zero_seed_and_image_condition(tmp_path, monkeypatch):
    image = object()
    seeds = []
    class Generator:
        def __init__(self, device):
            pass
        def manual_seed(self, seed):
            seeds.append(seed)
            return self
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(Generator=Generator, inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, 'diffusers.utils', SimpleNamespace(
        load_image=lambda p: image, export_to_video=lambda *a, **kw: None))
    row = runner_row(tmp_path)
    row['seed'] = 0
    class Pipeline:
        def __call__(self, prompt, image, generator):
            assert image is not None
            return SimpleNamespace(frames=[np.zeros((2, 2, 3), dtype=np.uint8)])
    args = SimpleNamespace(pipeline='ltx_i2v', model_dir='weights', height=None, width=None,
                           num_inference_steps=None, guidance_scale=None, num_frames=None, wan_invert_output=False)
    runner._generate_one(Pipeline(), args, row, tmp_path/'raw.mp4', tmp_path/'log.json')
    assert seeds == [0]


def test_controller_failure_retains_all_original_ids(tmp_path,monkeypatch):
    spec=dict(items=str(dump(tmp_path/'items',[item('a'),item('b')])),data_root='missing',compact='missing',
              model='ltx_i2v',model_dir='missing',frames=81,fps=16,sam3='missing',checkpoint='missing')
    monkeypatch.setattr(gen,'build',lambda *a:(_ for _ in ()).throw(ValueError('fixture controller crash')))
    with pytest.raises(ValueError,match='fixture controller crash'):pipeline.pipeline(spec,tmp_path/'run')
    assert [r['item_id'] for r in frontend.read_rows(tmp_path/'run/controller_failures.jsonl')]==['a','b']


def test_custom_runner_plan_and_bad_argv(tmp_path):
    spec=dict(items=str(dump(tmp_path/'items',[item()])),data_root='missing',compact='missing',model='cosmos3_nano',
              model_dir='missing',frames=81,fps=16,sam3='missing',checkpoint='missing',
              generation_command=['python','/registered/cosmos3.py','--manifest','{manifest}'])
    assert pipeline.execution_plan(spec)['model']=='cosmos3_nano'
    spec['generation_command']='shell string'
    with pytest.raises(ValueError,match='argv list'):pipeline.execution_plan(spec)


def test_remote_transfer_manifest_and_partial_preservation(tmp_path,monkeypatch):
    # Local fake hosts exercise transfer logic; no SSH or Linux worker startup.
    from physedit import driver,config
    srcdir=tmp_path/'src';dest=tmp_path/'dst';srcdir.mkdir();dest.mkdir()
    row=runner_row(srcdir)
    path=video(Path(row['generated_video_resized_to_source']),frames=5,fps=30)
    dump(srcdir/'manifest.jsonl',[row])
    rel=str(path.relative_to(srcdir))
    prior=dest/rel;prior.parent.mkdir(parents=True);prior.write_bytes(b'old partial')
    class Host:
        def sh(self,cmd):
            if cmd.startswith('cat '):return (srcdir/'manifest.jsonl').read_text()
            old=dest/rel
            if old.exists():old.rename(str(old)+'.retained.fixture')
            return ''
        def write(self,p,text):Path(p).write_text(text)
    hosts={'source':Host(),'home':Host()}
    def local_copy(src,d,home,rd,files):
        import shutil
        for f in files:
            (Path(rd)/f).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(Path(d)/f,Path(rd)/f)
    monkeypatch.setattr(driver,'copy',local_copy)
    monkeypatch.setitem(config.SITES,'home',{'vars':{'python':sys.executable}})
    d=object.__new__(driver.Driver);d.home='home'
    d.host=lambda site:hosts[site]
    d.rundir=lambda *a:str(srcdir);d.readable=lambda it:str(dest)
    d.site_items=lambda *a:{}
    d.transfer_media(dict(site='source',run='r',model='m',validated_files=[rel],media_sha256={rel:media.sha256(path)}))
    assert Path(str(prior)+'.retained.fixture').read_bytes()==b'old partial'
    copied=frontend.read_rows(dest/'manifest.jsonl')[0]
    assert copied['generated_video_resized_to_source']==str(dest/rel)
    assert media.validate_row(copied)['frames']==5
    assert json.loads((dest/'replica.json').read_text())['producer']=='source'
