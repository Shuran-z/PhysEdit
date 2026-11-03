"""Bridge boundary manifests to registered local native model runners.

Preparation never loads weights. Execution preserves the full native media;
the judge observes only the unchanged registered reference window.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from ..boundary import digest,plan,read_rows,write_json,write_rows
from ..native_boundary import coverage,model_contract
from .oneclick_registry import contract,validate_registration
from .media_contract import input_hashes,validate_video,verified_completion


def configure(boundary_spec,out,*,model,model_dir,runtime=None):
    source=Path(boundary_spec).resolve();spec=json.loads(source.read_text(encoding='utf8'))
    plan(spec);profile=contract(model);runtime=dict(runtime or {})
    reg=dict(model=model,model_dir=str(model_dir),frames=profile.frames,fps=profile.fps,generation_runtime=runtime)
    validate_registration(reg,require_runtime=False)
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    path=out/'native_registration.json';write_json(path,reg)
    inputs=read_rows(spec['inputs']);native_inputs=[]
    for row in inputs:
        value=dict(row)
        if abs(row['fps']-profile.fps)<1e-8 and row['evaluation_duration_s']<=(profile.frames-1)/profile.fps+1e-6:
            value['num_frames']=profile.frames
        native_inputs.append(value)
    write_rows(out/'inputs.jsonl',native_inputs)
    bound=dict(spec,model=model,inputs=str(out/'inputs.jsonl'),native_generation_contract=dict(model_contract(model),
        registration_path=str(path),registration_sha256=digest(path)),
        generation_command=[sys.executable,'-m','physedit.runners.boundary_registered','run',
            '--manifest','{manifest}','--work-dir','{run_dir}/native_model_driver',
            '--registration',str(path),'--registration-sha256',digest(path)])
    result=plan(bound);write_json(out/'spec.json',bound);write_json(out/'PRECHECK.json',result)
    write_json(out/'SOURCE.json',dict(source_spec=str(source),source_spec_sha256=digest(source),
        inputs_sha256=digest(spec['inputs']),answers_sha256=digest(spec['answers']),
        task_windows_or_prompts_changed=False,generation_lengths_registered_to_native_model=True,execution_requested=False))
    return result


def native_rows(rows,profile):
    result=[]
    for index,r in enumerate(rows):
        dest=Path(r['out_dir']).resolve()/'native'
        canvas=profile.canvas or(r['source_width'],r['source_height'])
        if r['source_width']==r['source_height']and profile.square_canvas:canvas=(profile.square_canvas,profile.square_canvas)
        row={k:r[k]for k in ['sample_id','condition_image','prompt_file','negative_prompt_file','seed','source_width','source_height']}
        row.update(source_sample_id=r['sample_id'],index=index,prompt_granularity='registered_boundary_input',prompt_field='prompt_en',
            mode=profile.mode,out_dir=str(dest),generated_video=str(dest/'generated_video.mp4'),
            generated_video_resized_to_source=str(dest/'resized_to_source.mp4'),
            num_frames=profile.frames,output_fps=profile.fps,source_sample_fps=profile.fps,
            gen_width=canvas[0],gen_height=canvas[1])
        result.append(row)
    return result


def preserve_native(source,destination,*,frames,fps,width,height):
    destination=Path(destination)
    if destination.exists():raise ValueError('boundary_output_already_exists')
    partial=destination.with_name(destination.stem+'.native_copy.partial.mp4')
    # Byte copy only. The scorer already restricts observation to each task
    # window; retaining a longer native tail never changes reference truth.
    shutil.copy2(source,partial)
    media=validate_video(partial,fps=fps,frames=frames,width=width,height=height)
    if digest(partial)!=digest(source):raise ValueError('native_video_copy_changed')
    os.replace(partial,destination)
    return media


def run_bridge(registration,registration_sha256,manifest,work):
    path=Path(registration)
    if digest(path)!=registration_sha256:raise ValueError('native_generation_registration_changed')
    reg=json.loads(path.read_text(encoding='utf8'));profile=validate_registration(reg)
    manifest=Path(manifest).resolve();rows=read_rows(manifest)
    cap=coverage(model_contract(reg['model']),rows)
    if not cap['execution_supported']:raise ValueError('native_model_window_incompatible_before_generation')
    work=Path(work).resolve()
    if not work.is_relative_to(manifest.parent):raise ValueError('native_driver_outside_registered_run')
    for r in rows:
        dest=Path(r['out_dir']).resolve()
        if not dest.is_relative_to(manifest.parent):raise ValueError('native_output_outside_registered_run')
        if (dest/'resized.mp4').exists()or(dest/'native').exists():raise ValueError('existing_native_attempt_retained_no_restart')
    work.mkdir(parents=True,exist_ok=False);eligible=native_rows(rows,profile)
    for r in eligible:Path(r['out_dir']).mkdir(parents=True,exist_ok=False)
    native=work/'model_inputs.jsonl';write_rows(native,eligible)
    expected={r['sample_id']:input_hashes(r)for r in eligible}
    if profile.runner=='diffusers':
        from ..phyediting import diffusers_launch
        command,env=diffusers_launch(reg,native)
        with(work/'model.log').open('x')as log:code=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
    else:
        from .registered_oneclick import run
        code=run(reg,native,work)
    results=[]
    for outer,inner in zip(rows,eligible):
        try:
            verified_completion(inner)
            if input_hashes(inner)!=expected[inner['sample_id']]:raise ValueError('native_inputs_changed_during_generation')
            source=Path(inner['generated_video_resized_to_source']);before=digest(source)
            media=preserve_native(source,Path(outer['out_dir'])/'resized.mp4',frames=outer['num_frames'],fps=outer['output_fps'],
                width=outer['source_width'],height=outer['source_height'])
            if digest(source)!=before:raise ValueError('native_media_changed_during_prefix_export')
            r=dict(sample_id=outer['sample_id'],status='native_window_exported',native_source=str(source),native_video_sha256=before,
                native_completion_sha256=digest(source.with_suffix('.completed.json')),
                native_frames=profile.frames,native_fps=profile.fps,full_native_media_preserved=True,
                native_input_sha256=expected[inner['sample_id']],boundary_generation_row_sha256=digest(manifest),
                registration_sha256=registration_sha256,media=media,interpolation_or_clock_changes=False)
            write_json(Path(outer['out_dir'])/'native_window_completion.json',r)
        except Exception as error:r=dict(sample_id=outer['sample_id'],status='failed',reason=str(error))
        results.append(r)
    write_rows(work/'bridge_status.jsonl',results)
    write_json(work/'receipt.json',dict(registered=len(rows),exported=sum(r['status']=='native_window_exported'for r in results),
        native_model_exit_code=code,registration_sha256=registration_sha256,input_manifest_sha256=digest(manifest),
        old_native_outputs_preserved=True,reference_answers_exported=False))
    return int(code!=0 or any(r['status']=='failed'for r in results))


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare');a.add_argument('--boundary-spec',required=True);a.add_argument('--out',required=True)
    a.add_argument('--model',required=True);a.add_argument('--model-dir',required=True)
    a.add_argument('--runtime-json',help='Explicit local Python, GPU devices and model-specific code paths')
    a=sub.add_parser('run');a.add_argument('--registration',required=True);a.add_argument('--registration-sha256',required=True)
    a.add_argument('--manifest',required=True);a.add_argument('--work-dir',required=True);args=p.parse_args()
    if args.action=='prepare':
        runtime=json.loads(Path(args.runtime_json).read_text())if args.runtime_json else{}
        print(json.dumps(configure(args.boundary_spec,args.out,model=args.model,model_dir=args.model_dir,runtime=runtime)));return 0
    return run_bridge(args.registration,args.registration_sha256,args.manifest,args.work_dir)


if __name__=='__main__':sys.exit(main())
