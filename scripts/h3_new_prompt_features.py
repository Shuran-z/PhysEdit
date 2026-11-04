"""Re-encode Qwen image/text conditioning, preserving eligible frozen VAE tensors."""
from h3_new_prompt_common import *
import sys,gc,fcntl,traceback
sys.path.insert(0,str(OLD))
import torch
from PIL import Image
from accelerate import init_empty_weights,cpu_offload
from transformers import AutoConfig,AutoTokenizer,AutoProcessor,Qwen3VLForConditionalGeneration
from safetensors.torch import load_file
from native_h3.vae import MiniMaxH3VideoVAE
from native_h3.text_encoder import encode_minimax_h3_prompt
def main():
 lock=(R/'encoder.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 torch.set_num_threads(3);plan,data=rows();ids=json.loads((R/'training_order.json').read_text());reuse=json.loads((R/'REUSE_INDEX.json').read_text())
 old={r['canonical_video_id']:r for r in map(json.loads,gzip.open(OLD/'train_manifest_runtime.jsonl.gz','rt'))};clocks=json.loads((OLD/'verified_clocks.json').read_text())
 device=torch.device('cuda:0');torch.cuda.set_per_process_memory_fraction(.25,0)
 meta=WEIGHTS/'h3_metadata/FL2VA';base=WEIGHTS/'h3_base_bf16'
 save(R/'ENCODER_STATUS.json',dict(stage='loading_frozen_qwen',pid=os.getpid(),time=time.time(),new_prompt_revision=REV))
 config=AutoConfig.from_pretrained(meta/'text_encoder',local_files_only=True);config.text_config.num_hidden_layers=50;config.tie_word_embeddings=False
 with init_empty_weights():te=Qwen3VLForConditionalGeneration(config)
 te.lm_head=None;state=load_file(base/'text_encoders/qwen3vl_32b_minimax_h3_bf16.safetensors')
 def rename(k):
  if k.startswith('model.'):return 'model.language_model.'+k[len('model.'):]
  if k.startswith('visual.'):return 'model.'+k
  return k
 result=te.load_state_dict({rename(k):v for k,v in state.items()},assign=True,strict=False);assert not result.unexpected_keys and all(k=='model.language_model.norm.weight' for k in result.missing_keys)
 te.model.language_model.norm=torch.nn.Identity();te.eval().requires_grad_(False);del state
 tokenizer=AutoTokenizer.from_pretrained(meta/'tokenizer',local_files_only=True);processor=AutoProcessor.from_pretrained(meta/'processor',local_files_only=True)
 cpu_offload(te,execution_device=device,offload_buffers=False,preload_module_classes=['Qwen3VLVisionModel'])
 vae=None;done=0;reused=0
 for index,vid in enumerate(ids):
  if (R/'STOP_ENCODER').exists():return
  dst=R/'cache'/(vid+'.pt')
  if dst.exists():done+=1;continue
  row=data[vid];fps,clock_evidence=clock(row,old,clocks);variant,prompt=caption(row,fps)
  assert len(tokenizer(prompt)['input_ids'])<=512,'No silent caption truncation'
  frames,rec=sampled(row,fps);poster=Image.fromarray(frames[0]);rec.update(clock_provenance=clock_evidence,prompt_variant=variant,prompt_sha256=row['prompt_variant_sha256'],model_input_prompt=prompt,model_input_prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),hf_revision=REV)
  save(R/'ENCODER_STATUS.json',dict(stage='encoding_current_prompt',pid=os.getpid(),index=index,completed=done,vae_reused=reused,id=vid,time=time.time(),new_prompt_revision=REV))
  with torch.inference_mode():
   embeds,tags=encode_minimax_h3_prompt(te,tokenizer,processor,prompt,keyframes=[poster],device=device,dtype=torch.bfloat16,max_length=None)
   if vid in reuse:
    previous=torch.load(reuse[vid]['path'],map_location='cpu',weights_only=True,mmap=True);assert previous['source_sha256']==row['sha256'] and previous['frames']==len(frames) and previous['full_window_receipt']['model_sample_indices']==rec['model_sample_indices']
    latent=previous['latent'].clone();first=previous['first'].clone();old_latent_sha=tensor_sha(previous['latent']);old_first_sha=tensor_sha(previous['first']);assert tensor_sha(latent)==old_latent_sha and tensor_sha(first)==old_first_sha
    proof=dict(reused=True,source_cache=reuse[vid]['path'],latent_sha256=old_latent_sha,first_sha256=old_first_sha,byte_identical_tensors=True);reused+=1;del previous
   else:
    if vae is None:
     vae=MiniMaxH3VideoVAE.load_from_state_dict(load_file(base/'vae/minimax_h3_video_vae_fp16.safetensors'));vae.encoder.to(device);vae.quant_conv.to(device)
     for name,value in list(vae._buffers.items()):
      if value is not None:vae._buffers[name]=value.to(device)
    video=torch.from_numpy(frames.copy()).permute(3,0,1,2).unsqueeze(0).float().div(127.5).sub(1).to(device)
    gen=torch.Generator('cpu').manual_seed(int(hashlib.sha256(vid.encode()).hexdigest()[:8],16));latent=vae.encode(video,generator=gen).cpu();first=vae.encode(video[:,:,:1],generator=torch.Generator('cpu').manual_seed(42),fp16_round=True).cpu();del video
    proof=dict(reused=False,reason='missing or media/clock changed',latent_sha256=tensor_sha(latent),first_sha256=tensor_sha(first))
  d=dict(canonical_video_id=vid,latent=latent,first=first,embeddings=embeds.cpu(),tags=tags.cpu(),source_sha256=row['sha256'],manifest_sha256=plan['manifest_sha256'],prompt_sha256=rec['model_input_prompt_sha256'],prompt_variant=variant,source_prompt_sha256=row['prompt_variant_sha256'][variant-1],condition_populated_frames=1,frames=len(frames),fps=24,full_window_receipt=rec,hf_revision=REV,vae_reuse=proof)
  assert all(torch.isfinite(d[k]).all() for k in ['latent','first','embeddings','tags'])
  tmp=dst.with_suffix('.partial');torch.save(d,tmp);tmp.replace(dst);done+=1
  with (R/'CACHE_PROVENANCE.jsonl').open('a') as f:f.write(json.dumps(dict(id=vid,manifest_sha256=d['manifest_sha256'],source_sha256=d['source_sha256'],source_prompt_sha256=d['source_prompt_sha256'],prompt_sha256=d['prompt_sha256'],vae_reuse=proof))+'\n')
  save(R/'ENCODER_STATUS.json',dict(stage='encoding',pid=os.getpid(),completed=done,total=len(ids),vae_reused=reused,last_id=vid,time=time.time(),new_prompt_revision=REV))
  del d,embeds,tags,latent,first,frames;gc.collect()
 save(R/'ENCODER_COMPLETE.json',dict(time=time.time(),completed=done,revision=REV))
if __name__=='__main__':
 try:main()
 except BaseException:
  save(R/'ENCODER_FAILED.json',dict(time=time.time(),traceback=traceback.format_exc()));raise
