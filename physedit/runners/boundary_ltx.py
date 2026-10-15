"""Bounded offline LTX I2V pilot adapter. No reference answers or inversion inputs."""
import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import shutil


def check_gpu(gpu):
    # Shared host: recheck capacity just before loading, do not terminate others.
    query=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free,utilization.gpu',
                                   '--format=csv,noheader,nounits'],text=True)
    selected=next([int(x.strip()) for x in line.split(',')] for line in query.splitlines()
                  if int(line.split(',')[0])==gpu)
    # Pilot observed ~10–11 GiB incremental use with CPU offload; keep >=3 GiB headroom.
    if selected[1]<14000 or selected[2]>=10:
        raise RuntimeError('GPU no longer has the registered idle capacity')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True)
    p.add_argument('--model-dir',required=True)
    p.add_argument('--gpu',required=True,type=int)
    p.add_argument('--steps',default=50,type=int)
    p.add_argument('--pad-input',action='store_true',help='Pad without rescaling; remove padding from output')
    p.add_argument('--reuse-run',help='Explicit prior run; reuse only fully bound successful identical inputs')
    args=p.parse_args()
    if args.pad_input and args.reuse_run:
        raise ValueError('padded inputs require a fresh run')
    os.environ['CUDA_VISIBLE_DEVICES']=str(args.gpu)
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import cv2
    import torch
    import diffusers
    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    from diffusers import LTXImageToVideoPipeline
    from diffusers.utils import load_image
    rows=[json.loads(s) for s in Path(args.manifest).read_text().splitlines() if s.strip()]
    if len(rows)>2:
        raise ValueError('bounded pilot supports at most two registered videos')
    pipe=None
    previous={}
    previous_media={}
    if args.reuse_run:
        prior=Path(args.reuse_run)
        previous={r['sample_id']:r for r in map(json.loads,(prior/'generation_rows.jsonl').read_text().splitlines())}
        previous_media={r['sample_id']:r for r in map(json.loads,(prior/'observed_rows.jsonl').read_text().splitlines())}
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    results=[]
    for r in rows:
        out=Path(r['out_dir']);out.mkdir(parents=True,exist_ok=False)
        try:
            old=previous.get(r['sample_id'])
            old_media=previous_media.get(r['sample_id'],{})
            if old and old_media.get('status')=='ok':
                for key in ('seed','num_frames','output_fps','source_width','source_height','width','height'):
                    if old[key]!=r[key]:raise ValueError('reuse input mismatch: '+key)
                for key in ('condition_image','prompt_file','negative_prompt_file'):
                    if sha(old[key])!=sha(r[key]):raise ValueError('reuse content mismatch: '+key)
                old_receipt=json.loads((Path(old['out_dir'])/'inference.json').read_text())
                if (old_receipt['model_dir']!=args.model_dir or old_receipt['steps']!=args.steps or
                    old_receipt['model_index_sha256']!=sha(Path(args.model_dir)/'model_index.json')):
                    raise ValueError('reuse model registration mismatch')
                if sha(old_media['video'])!=old_media['video_sha256']:raise ValueError('reuse video hash mismatch')
                shutil.copyfile(old_media['video'],out/'resized.mp4')
                (out/'inference.json').write_text(json.dumps(dict(old_receipt,reused_from=old_media['video'],
                    reused_video_sha256=old_media['video_sha256']),indent=2))
                results.append(dict(sample_id=r['sample_id'],status='reused_verified'))
                (out/'runner_status.json').write_text(json.dumps(results[-1]))
                continue
            if pipe is None:
                check_gpu(args.gpu)
                pipe=LTXImageToVideoPipeline.from_pretrained(args.model_dir,torch_dtype=torch.bfloat16,local_files_only=True)
                if 'frame_rate' not in inspect.signature(pipe.__call__).parameters:
                    raise RuntimeError('LTX interface must support explicit physical frame rate')
                pipe.enable_model_cpu_offload();pipe.vae.enable_tiling()
                cv2.setNumThreads(1)
            prompt=Path(r['prompt_file']).read_text(encoding='utf-8')
            max_tokens=256
            token_count=len(pipe.tokenizer(prompt,add_special_tokens=True)['input_ids'])
            receipt=dict(model_dir=args.model_dir,model_index_sha256=hashlib.sha256((Path(args.model_dir)/'model_index.json').read_bytes()).hexdigest(),
                         torch=torch.__version__,diffusers=diffusers.__version__,gpu=args.gpu,
                         steps=args.steps,guidance_scale=3.,frames=r['num_frames'],fps=r['output_fps'],
                         prompt_tokens=token_count,max_sequence_length=max_tokens,
                         prompt_truncated=token_count>max_tokens)
            (out/'inference.json').write_text(json.dumps(receipt,indent=2))
            if token_count>max_tokens:
                raise ValueError('registered prompt exceeds model token budget; revise before inference')
            source_image=load_image(r['condition_image'])
            left=top=0
            if args.pad_input:
                import numpy as np
                if source_image.size!=(r['source_width'],r['source_height']):
                    raise ValueError('source dimensions do not match manifest')
                dw=r['width']-source_image.width;dh=r['height']-source_image.height
                if dw<0 or dh<0 or dw>=32 or dh>=32:
                    raise ValueError('padding must only round dimensions up to a multiple of 32')
                if r['width']%32 or r['height']%32:
                    raise ValueError('LTX canvas dimensions must be divisible by 32')
                from PIL import Image
                left=dw//2;top=dh//2
                source_image=Image.fromarray(np.pad(np.asarray(source_image),
                    ((top,dh-top),(left,dw-left),(0,0)),mode='edge'))
            source_image.save(out/'model_input.png')
            receipt.update(pad_input=args.pad_input,padding_left=left,padding_top=top,
                           model_input_sha256=sha(out/'model_input.png'),
                           canvas=[r['width'],r['height']])
            (out/'inference.json').write_text(json.dumps(receipt,indent=2))
            frames=pipe(image=source_image,prompt=prompt,
                 negative_prompt=Path(r['negative_prompt_file']).read_text(),
                 height=r['height'],width=r['width'],num_frames=r['num_frames'],frame_rate=r['output_fps'],
                 num_inference_steps=args.steps,guidance_scale=3.,max_sequence_length=max_tokens,
                 generator=torch.Generator(device='cuda').manual_seed(r['seed'])).frames[0]
            if len(frames)!=r['num_frames']:raise ValueError('model_frame_count_mismatch')
            partial=out/'resized.partial.mp4'
            writer=cv2.VideoWriter(str(partial),cv2.VideoWriter_fourcc(*'mp4v'),r['output_fps'],
                                   (r['source_width'],r['source_height']))
            if not writer.isOpened():raise RuntimeError('video writer unavailable')
            import numpy as np
            try:
                for frame in frames:
                    rgb=np.asarray(frame)
                    if args.pad_input:
                        rgb=rgb[top:top+r['source_height'],left:left+r['source_width']]
                    writer.write(cv2.resize(cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),
                                            (r['source_width'],r['source_height']),interpolation=cv2.INTER_AREA))
            finally:writer.release()
            partial.rename(out/'resized.mp4')
            results.append(dict(sample_id=r['sample_id'],status='generated'))
        except Exception as error:
            results.append(dict(sample_id=r['sample_id'],status='failed',reason=str(error)))
        (out/'runner_status.json').write_text(json.dumps(results[-1],indent=2))
        torch.cuda.empty_cache()
    print(json.dumps(results))
    return int(any(r['status'] not in ('generated','reused_verified') for r in results))


if __name__=='__main__':raise SystemExit(main())
