"""Real CPU pixels and model-interface spies; no model inference or GPU claims."""
import json
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from physedit import video_conditioning as vc, vp_metrics as vp
from physedit.pixel_metrics import InsufficientEvidence
from physedit.runners import media_contract as media, diffusers_i2v as runner
from physedit.runners.oneclick_registry import MODELS, validate_registration
from physedit.runners.model_parameters import PROFILES


def masks(times, speed):
    out = []
    for t in times:
        mask = np.zeros((80, 200), bool)
        x = int(round(10 + speed * t))
        mask[20:30, x:x+10] = True
        out.append(mask)
    return out


def test_trajectory_compares_physical_time_not_normalized_video_length():
    a = np.arange(61) / 30
    b = np.arange(81) / 20
    src, same = masks(a, 30), masks(b, 30)
    score = lambda dst: vp.trajectory_error(src, dst, 0, 0, source_times=a,
        generated_times=b, duration_seconds=2, sampling_fps=30)
    assert score(same) < 0.003  # native pixel quantization, not time stretching
    # Same total displacement over twice the duration must remain slower.
    assert score(masks(b, 15)) > 0.06


def test_trajectory_rejects_short_missing_and_invalid_timestamps():
    times = np.arange(31) / 30
    track = masks(times, 20)
    call = lambda dst, clock, duration: vp.trajectory_error(track, dst, 0, 0,
        source_times=times, generated_times=clock, duration_seconds=duration)
    with pytest.raises(InsufficientEvidence, match='incomplete_trajectory'):
        call(track, times, 5)
    missing = [m.copy() for m in track]
    missing[15][:] = False
    with pytest.raises(InsufficientEvidence, match='missing_target_inside'):
        call(missing, times, 1)
    bad = times.copy(); bad[10] = bad[9]
    with pytest.raises(ValueError, match='invalid_trajectory_timestamps'):
        call(track, bad, 1)


def source_fixture(tmp, *, frames=161):
    path = tmp/'source.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'FFV1'), 25, (80,64))
    assert writer.isOpened()
    initial = None
    for n in range(frames):
        pixels = np.full((64,80,3), 190, np.uint8)
        pixels[20:30, 10+n%40:20+n%40] = 15
        if initial is None: initial = pixels.copy()
        writer.write(pixels)
    writer.release()
    condition = tmp/'condition.png'; assert cv2.imwrite(str(condition), initial)
    row = dict(item_id='item', sample_id='case', source_video='distinct_target_reference',
        source_video_sha256='target-reference-sha', source_width=80, source_height=64,
        condition_image=str(condition), num_frames=161, output_fps=25, input_failure=None)
    manifest = tmp/'v2v.jsonl'
    manifest.write_text(json.dumps(dict(item_id='item', video=str(path), video_sha256=media.sha256(path),
        fps=25, frames=frames, start_frame=0))+'\n')
    spec = dict(model='ltx_i2v', conditioning_mode='v2v', v2v=dict(manifest=str(manifest),
        manifest_sha256=media.sha256(manifest), denoise_strength=0.6, conditioning_strength=0.7))
    return row, spec


def test_full_video_registration_and_separate_failure_denominator(tmp_path):
    row, spec = source_fixture(tmp_path)
    missing = {**row, 'item_id':'missing', 'sample_id':'missing'}
    rows = vc.attach([row, missing], spec)
    assert len(rows) == 2 and row['input_failure'] is None
    assert 'missing_registered_v2v_source' in missing['input_failure']
    frames = vc.load_frames(row)
    assert len(frames) == 161
    assert not np.array_equal(np.asarray(frames[0]), np.asarray(frames[10]))
    for k in ('prompt_file','negative_prompt_file'):
        p=tmp_path/k; p.write_text('test');row[k]=str(p)
    assert media.input_hashes(row)['conditioning_video'] == row['conditioning_video_sha256']
    Path(row['conditioning_video']).write_bytes(b'drift')
    with pytest.raises(ValueError, match='changed_since_registration'):
        vc.load_frames(row)


@pytest.mark.parametrize('fault', ['short','target','initial','strength','manifest'])
def test_v2v_refuses_incomplete_target_leak_initial_drift_and_bad_settings(tmp_path, fault):
    row, spec = source_fixture(tmp_path, frames=21 if fault=='short' else 161)
    if fault=='target': row['source_video_sha256'] = media.sha256(tmp_path/'source.avi')
    if fault=='initial': cv2.imwrite(row['condition_image'], np.zeros((64,80,3),np.uint8))
    if fault=='strength': spec['v2v']['denoise_strength'] = 0
    if fault=='manifest': spec['v2v']['manifest_sha256'] = 'wrong'
    if fault in ('manifest','strength'):
        with pytest.raises(ValueError):vc.attach([row],spec)
    else:
        vc.attach([row],spec)
        assert row['input_failure'].startswith('v2v_input_failure:')


def test_v2v_actual_adapter_passes_full_video_clock_and_strengths(tmp_path, monkeypatch):
    row, spec = source_fixture(tmp_path);vc.attach([row],spec)
    for name in ('prompt_file', 'negative_prompt_file'):
        p=tmp_path/name;p.write_text('test');row[name]=str(p)
    class Generator:
        def __init__(self,device): pass
        def manual_seed(self,seed): return self
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(Generator=Generator,inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules,'diffusers.utils',SimpleNamespace(load_image=lambda _:None,export_to_video=lambda *a,**kw:None))
    class Pipe:
        def __call__(self,prompt,negative_prompt,video,frame_index,strength,denoise_strength,
                     height,width,num_frames,num_inference_steps,guidance_scale,generator,frame_rate):
            assert len(video)==1 and len(video[0])==161
            assert not np.array_equal(np.asarray(video[0][0]),np.asarray(video[0][10]))
            assert frame_rate==25 and num_frames==161
            assert denoise_strength==0.6 and strength==[0.7] and frame_index==[0]
            return SimpleNamespace(frames=[np.zeros((64,80,3),np.uint8)])
    args=SimpleNamespace(pipeline='ltx_v2v',model_dir='weights',height=None,width=None,
        num_inference_steps=50,guidance_scale=3,num_frames=None,wan_invert_output=False)
    runner._generate_one(Pipe(),args,row,tmp_path/'out.mp4',tmp_path/'call.json')
    logged=json.loads((tmp_path/'call.json').read_text())
    assert logged['conditioning_mode']=='v2v' and 'image' not in logged['accepted_call_args']
    assert logged['conditioning_video_sha256']==row['conditioning_video_sha256']


def test_all_twelve_profiles_have_sampling_and_registered_clocks():
    assert set(PROFILES)==set(MODELS) and len(MODELS)==12
    assert (MODELS['wan_ti2v5b'].frames,MODELS['wan_ti2v5b'].fps)==(121,24)
    assert MODELS['dynamicrafter_i2v'].fps==PROFILES['dynamicrafter_i2v']['frame_stride']==10
    assert validate_registration(dict(model='ltx_i2v', conditioning_mode='v2v',frames=161,fps=25)).mode=='v2v'
    with pytest.raises(ValueError,match='conditioning mode'):
        validate_registration(dict(model='wan_ti2v5b',conditioning_mode='v2v',frames=121,fps=24))


def test_dynamicrafter_export_clock_keeps_all_native_frames(tmp_path):
    from physedit.runners.dynamicrafter import _reclock_native_frames
    import shutil
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg executable required for native export regression')
    path=tmp_path/'official.mp4'
    w=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),8,(80,64))
    for n in range(16): w.write(np.full((64,80,3),n*10,np.uint8))
    w.release()
    out=tmp_path/'native.mp4';_reclock_native_frames(path,out,10)
    assert media.validate_video(out,fps=10,frames=16)['full_decode']
    assert media.validate_video(path,fps=8,frames=16)['full_decode']


def test_v2v_old_library_is_rejected_before_loading_weights(tmp_path, monkeypatch):
    class Old:
        def __call__(self, video, frame_rate, frame_index, strength): pass
        @classmethod
        def from_pretrained(cls,*a,**kw): pytest.fail('must reject before weights/GPU')
    monkeypatch.setitem(sys.modules,'diffusers',SimpleNamespace(LTXConditionPipeline=Old))
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace())
    with pytest.raises(ValueError,match='lacks full editing arguments'):
        runner._load_pipeline('ltx_v2v','weights','bfloat16','model',None)


def test_native_clock_and_sampler_reach_diffusers_launch(tmp_path,monkeypatch):
    from physedit import phyediting
    monkeypatch.setattr('physedit.runners.registered_oneclick._preflight',lambda *a:('python','ffmpeg',{}))
    for model, steps, guidance, shift in [('wan_ti2v5b',50,5,5),('hunyuan15_i2v',12,1,7)]:
        command,_=phyediting.diffusers_launch(dict(model=model,model_dir=str(tmp_path)),tmp_path/'rows')
        assert float(command[command.index('--num-inference-steps')+1])==steps
        assert float(command[command.index('--guidance-scale')+1])==guidance
        assert float(command[command.index('--flow-shift')+1])==shift
