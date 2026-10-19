"""CPU media and substituted producer tests; no model weights or GPU."""
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from physedit import future_conditioning as future, phyediting
from physedit.runners import registered_oneclick
from physedit.runners.media_contract import sha256, validate_video, verified_completion
from physedit.runners.oneclick_registry import validate_registration


def fixture(tmp_path):
    source = tmp_path/'reference.mp4'
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 16, (80,64))
    for i in range(100):
        writer.write(np.full((64,80,3), i*2, np.uint8))
    writer.release()
    cap = cv2.VideoCapture(str(source)); cap.set(cv2.CAP_PROP_POS_FRAMES,23)
    ok, condition = cap.read(); cap.release(); assert ok
    cv2.imwrite(str(tmp_path/'condition.png'), condition)
    out = tmp_path/'out'
    row = dict(item_id='case', sample_id='case__g9', condition_frame_index=23,
               condition_image=str(tmp_path/'condition.png'), source_video=str(source),
               source_video_sha256=sha256(source), source_native_fps=16,
               source_width=80, source_height=64, output_fps=16, num_frames=81,
               out_dir=str(out), generated_video=str(out/'raw.mp4'),
               generated_video_resized_to_source=str(out/'resized.mp4'))
    entry = dict(item_id='case',video=str(source),video_sha256=sha256(source),fps=16,frames=100,end_frame=23)
    manifest = tmp_path/'history.jsonl'; manifest.write_text(json.dumps(entry)+'\n')
    spec = dict(model='cosmos', conditioning_mode='v2v_future', frames=81, fps=16,
                future=dict(manifest=str(manifest),manifest_sha256=sha256(manifest)),
                generation_runtime=dict(code_dir=str(tmp_path)))
    for key in ('prompt_file', 'negative_prompt_file'):
        path=tmp_path/key;path.write_text('A moving object.');row[key]=str(path)
    return row,entry,spec


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')
def test_five_real_history_frames_end_at_condition_and_seal_inputs(tmp_path):
    row,entry,spec=fixture(tmp_path)
    future.attach([row],spec)
    assert not row.get('input_failure')
    assert row['history_source_indices']==[19,20,21,22,23]
    assert row['history_relative_times_s']==[-.25,-.1875,-.125,-.0625,0]
    assert row['num_frames']==77 and row['native_num_frames']==81
    assert validate_video(row['conditioning_video'],fps=16,frames=5)['full_decode']
    from physedit.runners.cosmos_predict2 import _validate_history
    _validate_history(row)
    Path(row['conditioning_source_video']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='source_changed'):
        _validate_history(row)


@pytest.mark.parametrize('change,reason',[
    ({'end_frame':22},'end_time_mismatch'),
    ({'video_sha256':'0'*64},'sha256_mismatch'),
    ({'fps':8},'end_time_mismatch'),
    ({'end_frame':101},'outside_video'),
])
def test_bad_history_retains_case_with_reason(tmp_path,change,reason):
    row,entry,spec=fixture(tmp_path);entry.update(change)
    manifest=Path(spec['future']['manifest']);manifest.write_text(json.dumps(entry)+'\n')
    spec['future']['manifest_sha256']=sha256(manifest)
    rows=future.attach([row],spec)
    assert len(rows)==1 and rows[0]['item_id']=='case'
    assert reason in row['input_failure']
    assert not Path(row['generated_video']).exists()


def test_short_history_is_rejected_without_padding(tmp_path):
    row,entry,_=fixture(tmp_path);entry['end_frame']=3;row['condition_frame_index']=3
    with pytest.raises(ValueError,match='insufficient_distinct'):
        future.history(row,entry)


def test_wrong_condition_pixels_and_manifest_drift_rejected(tmp_path):
    row,entry,spec=fixture(tmp_path)
    cv2.imwrite(row['condition_image'],np.zeros((64,80,3),np.uint8))
    with pytest.raises(ValueError,match='last_history_frame'):
        future.history(row,entry)
    Path(spec['future']['manifest']).write_text('')
    with pytest.raises(ValueError,match='manifest_sha256'):
        future.registration(spec)


def test_future_plan_and_registered_profile_preserve_native_clock(tmp_path):
    row,entry,spec=fixture(tmp_path)
    items=tmp_path/'items.jsonl';items.write_text('{"id":"case"}\n')
    spec.update(items=str(items),data_root='data',compact='compact',model_dir='weights',sam3='sam',checkpoint='sam.pt')
    plan=phyediting.execution_plan(spec)
    assert plan['conditioning_mode']=='v2v_future'
    assert plan['native_output_frames']==81 and plan['evaluated_frames']==77
    assert plan['post_condition_seconds']==4.75 and not plan['gpu_started']
    assert validate_registration(spec).mode=='v2v_future'
    spec['model']='wan_ti2v5b';spec['frames']=121;spec['fps']=24
    with pytest.raises(ValueError,match='conditioning mode'):
        phyediting.execution_plan(spec)


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')
def test_actual_registered_subprocess_chain_trims_only_four_history_frames(tmp_path):
    row,entry,spec=fixture(tmp_path)
    future.attach([row],spec); assert not row.get('input_failure')
    # A CPU producer substitutes only the generative model. Both repository
    # runner processes, frame validation, cropping and completion binding run.
    producer=tmp_path/'run_cosmos_v2w_from_video.py'
    producer.write_text('''import argparse,json,cv2,numpy as np
from pathlib import Path
p=argparse.ArgumentParser()
for k in ['video_path','out_dir','model_dir','model_size','resolution','fps','aspect_ratio','num_frames','num_conditional_frames','sample_fps','seed','guidance','prompt_file','negative_prompt_file','tokenizer_path','text_encoder_path']:p.add_argument('--'+k)
a=p.parse_args();d=Path(a.out_dir);(d/'actual_args.json').write_text(json.dumps(vars(a)))
cap=cv2.VideoCapture(a.video_path);hist=[]
while True:
 ok,bgr=cap.read()
 if not ok:break
 hist.append(bgr)
cap.release();assert len(hist)==5 and a.num_conditional_frames=='5' and float(a.sample_fps)==16
w=cv2.VideoWriter(str(d/'raw.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),16,(80,64))
for i in range(81):w.write(hist[i] if i<5 else np.full((64,80,3),100+i,np.uint8))
w.release()
''')
    weights=tmp_path/'weights';weights.mkdir()
    spec.update(model_dir=str(weights))
    spec['generation_runtime'].update(python=sys.executable,ffmpeg=shutil.which('ffmpeg'))
    manifest=tmp_path/'rows.jsonl';manifest.write_text(json.dumps(row)+'\n')
    root=tmp_path/'run';root.mkdir()
    assert registered_oneclick.run(spec,manifest,root)==0
    args=json.loads((Path(row['out_dir'])/'actual_args.json').read_text())
    assert args['video_path']==row['conditioning_video'] and args['num_frames']=='81'
    assert args['aspect_ratio']=='4:3'
    assert row['source_video'] not in args.values()
    assert validate_video(row['generated_video'],fps=16,frames=81)['full_decode']
    assert validate_video(row['generated_video_resized_to_source'],fps=16,frames=77)['full_decode']
    native=cv2.VideoCapture(row['generated_video']);native.set(cv2.CAP_PROP_POS_FRAMES,4)
    _,anchor=native.read();native.release()
    scored=cv2.VideoCapture(row['generated_video_resized_to_source']);_,first=scored.read();_,prediction=scored.read();scored.release()
    assert np.max(np.abs(first.astype(float)-anchor.astype(float)))<8
    assert prediction.mean()>first.mean()+40
    receipt=verified_completion(row)
    assert set(receipt['input_sha256']) >= {'conditioning_video','conditioning_source_video','future_manifest'}


def test_physical_summary_exposes_three_parallel_parameters():
    from physedit.evaluations import attach_summary
    stats=dict(registered=2,scored=1,failed=1,coverage_percent=50,failure_rate_percent=50,
               mean_error_percent=2,max_error_percent=3,failures=[{'sample_id':'bad'}])
    result=attach_summary(stats,{'friction':dict(stats,static_bounds=1),'velocity':stats},
                          ['gravtrace','friction','velocity'])
    p=result['physical_parameters']
    assert list(p)==['gravity','friction','initial_velocity']
    assert all(x['registered']==2 and x['mean_error_percent']==2 and x['point_coverage_percent']==50 for x in p.values())
    assert p['friction']['static_bounds']==1 and result['evaluation_failed']==1


def test_measure_gravity_routes_to_the_original_fitter(monkeypatch):
    from physedit.__main__ import main
    import gravtrace.__main__ as original
    seen=[]
    monkeypatch.setattr(original,'main',lambda:seen.extend(sys.argv))
    before=sys.argv
    main(['measure','gravity','samples.jsonl','-o','results.jsonl'])
    assert seen[1:]==['fit','samples.jsonl','-o','results.jsonl']
    assert sys.argv is before


def test_models_exposes_future_video_mode(capsys):
    from physedit.__main__ import main
    main(['models','--json'])
    models=json.loads(capsys.readouterr().out)
    assert len(models)==12
    assert 'v2v_future' in models['cosmos']['supported_modes']
    assert models['cosmos']['future_prediction']['predicted_frames']==76


def test_measure_help_lists_three_physical_parameters(capsys):
    from physedit.__main__ import main
    with pytest.raises(SystemExit) as result:
        main(['measure','--help'])
    assert result.value.code==0
    text=capsys.readouterr().out
    assert all(name in text for name in ('gravity','friction','velocity'))
