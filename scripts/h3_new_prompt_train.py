"""Fresh original-base H3 LoRA with pinned current prompts; never restore old Adam state."""
from h3_new_prompt_common import *
import sys,gc,math,traceback,datetime
O=R/'training'
def cached(index,ids,data,plan):
 import torch
 vid=ids[index%len(ids)];row=data[vid];p=R/'cache'/(vid+'.pt');started=time.time()
 while not p.exists():
  save(O/('phase_rank'+os.environ['RANK']+'.json'),dict(time=time.time(),phase='waiting_versioned_feature',id=vid,index=index))
  assert not (R/'STOP_TRAINING').exists() and not (R/'ENCODER_FAILED.json').exists() and time.time()-started<21600,'Current feature unavailable; never fall back to old text embeddings'
  time.sleep(3)
 digest=sha(p);d=torch.load(p,map_location='cpu',weights_only=True);rec=d['full_window_receipt'];variant,text=caption(row,rec['fps'])
 assert d['hf_revision']==REV and d['manifest_sha256']==plan['manifest_sha256']
 assert d['canonical_video_id']==vid and d['source_sha256']==rec['source_sha256']==row['sha256']
 assert d['prompt_variant']==variant and d['source_prompt_sha256']==row['prompt_variant_sha256'][variant-1]
 assert rec['model_input_prompt']==text and hashlib.sha256(text.encode()).hexdigest()==d['prompt_sha256']==rec['model_input_prompt_sha256']
 assert d['condition_populated_frames']==1 and d['fps']==24 and d['frames']==rec['model_frames']
 assert rec['model_sample_indices']==[min(rec['frames']-1,round(i*rec['fps']/24)) for i in range(d['frames'])]
 assert tuple(d['latent'].shape)==(1,24,((d['frames']+16)//17)*5-3,18,32) and tuple(d['first'].shape)==(1,24,1,18,32)
 assert d['embeddings'].ndim==2 and d['embeddings'].shape[-1]==5120 and d['tags'].numel()==d['embeddings'].shape[0]
 assert all(torch.isfinite(d[k]).all() for k in ['latent','first','embeddings','tags']) and sha(p)==digest
 assert tensor_sha(d['latent'])==d['vae_reuse']['latent_sha256'] and tensor_sha(d['first'])==d['vae_reuse']['first_sha256']
 return d,digest
def main():
 import torch,torch.distributed as dist
 import torch.distributed.checkpoint as dcp
 from torch.distributed.checkpoint.state_dict import get_model_state_dict,get_optimizer_state_dict,StateDictOptions
 from peft import get_peft_model_state_dict
 from safetensors.torch import save_file
 sys.path.insert(0,str(OLD));sys.path.insert(0,str(SCIENTIFIC))
 from native_restore_functions import make_model
 from native_prediction import prediction
 from native_clip import clip
 plan,data=rows()
 for name in ['CURRENT_CLOCKS.json','training_order.json','REUSE_INDEX.json']:assert sha(R/name)==plan[name+'_sha256'],name
 ids=json.loads((R/'training_order.json').read_text());assert len(ids)==45165 and set(ids)==set(data)
 local=int(os.environ['LOCAL_RANK']);torch.set_num_threads(2);torch.cuda.set_device(local);torch.cuda.set_per_process_memory_fraction(.80,local)
 dist.init_process_group('nccl',timeout=datetime.timedelta(hours=6));rank=dist.get_rank();assert dist.get_world_size()==2
 feature_group=dist.new_group(backend='gloo',timeout=datetime.timedelta(hours=6));O.mkdir(exist_ok=True)
 assert not (O/'progress.json').exists(),'Existing training is preserved; no automatic replay'
 for f,m in [('native_restore_functions.py','NATIVE_FUNCTIONS_MANIFEST.json'),('native_prediction.py','NATIVE_PREDICTION_MANIFEST.json'),('native_clip.py','NATIVE_CLIP_MANIFEST.json')]:
  proof=json.loads((SCIENTIFIC.parent/m).read_text());assert sha(SCIENTIFIC/f)==(proof.get('extracted_module_sha256') or proof['module_sha256'])
 save(O/('phase_rank%d.json'%rank),dict(time=time.time(),phase='initializing_original_base_fresh_lora',resume_checkpoint=None))
 torch.manual_seed(plan['seed']);model,targets,expected=make_model('h3',torch.bfloat16);assert expected==208
 torch.manual_seed(plan['seed']+rank);params=[p for p in model.parameters() if p.requires_grad];assert len(params)==416
 assert all(torch.count_nonzero(p.to_local() if hasattr(p,'to_local') else p)==0 for n,p in model.named_parameters() if '.lora_B.' in n)
 opt=torch.optim.AdamW(params,lr=2e-5,betas=(.9,.95),eps=1e-8,weight_decay=.01);assert len(opt.state)==0
 total=plan['total_steps'];schedule=torch.optim.lr_scheduler.LambdaLR(opt,lambda s:min((s+1)/100,max(0.,(total-s)/(total-100))))
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 if rank==0:save(O/'configuration.json',dict(**plan,world_size=2,accumulation=6,targets=targets,lora_rank=64,lora_alpha=64,trainable_tensors=416,optimizer_state_fresh=True,checkpoint_resume=None,old_checkpoint150_used=False,parameter_cpu_offload=False,activation_cpu_offload=True,preprocessing='512x288 / 24 physical fps / H3 grid tail crop',native_prediction_sha256=sha(SCIENTIFIC/'native_prediction.py')))
 model.train();opt.zero_grad();seen=set();began=time.time()
 for step in range(1,total+1):
  assert not (R/'STOP_TRAINING').exists()
  loss_sum=0.;sample_started=time.time()
  for micro in range(6):
   index=(step-1)*12+rank+micro*2;d,digest=cached(index,ids,data,plan);vid=ids[index%len(ids)]
   dist.barrier(group=feature_group)
   save(O/('phase_rank%d.json'%rank),dict(time=time.time(),phase='forward_backward',step=step,microbatch=micro+1,id=vid))
   with torch.autograd.graph.save_on_cpu(pin_memory=False):
    loss=prediction(model,'h3',d,torch.device('cuda',local),torch.bfloat16);assert torch.isfinite(loss);(loss/6).backward()
   loss_sum+=loss.detach().item()
   for n,p in model.named_parameters():
    if p.requires_grad and p.grad is not None:
     g=p.grad.to_local() if hasattr(p.grad,'to_local') else p.grad;assert torch.isfinite(g).all(),n
     if g.numel() and g.abs().max()>0:seen.add(n)
   with (O/('samples_rank%d.jsonl'%rank)).open('a') as f:f.write(json.dumps(dict(global_index=index,id=vid,source_sha256=d['source_sha256'],prompt_sha256=d['prompt_sha256'],source_prompt_sha256=d['source_prompt_sha256'],cache_sha256=digest,step=step))+'\n')
   del d,loss;gc.collect();torch.cuda.empty_cache()
  norm=clip(params,torch.device('cuda',local));assert math.isfinite(norm) and norm>0
  opt.step();schedule.step();opt.zero_grad();assert len(opt.state)==416
  value=torch.tensor(loss_sum/6,device='cuda');dist.all_reduce(value)
  progress=dict(time=time.time(),step=step,total_steps=total,samples_seen=step*12,unique_training_videos=45165,mean_loss=value.item()/2,gradient_norm=norm,nonzero_gradient_tensors_seen=len(seen),lr=opt.param_groups[0]['lr'],step_seconds=time.time()-sample_started,elapsed_seconds=time.time()-began,peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),hf_revision=REV)
  if rank==0:save(O/'progress.json',progress)
  for state in opt.state.values():
   for k in ['exp_avg','exp_avg_sq']:
    t=state[k].to_local() if hasattr(state[k],'to_local') else state[k];assert torch.isfinite(t).all()
  if step==10:
   assert len(seen)==416,('Fresh initial B=0 gives zero A gradients at step1, but every supervised tensor must receive gradients by step10',len(seen))
   if rank==0:save(O/'TEN_STEP_AUDIT_PASS.json',dict(**progress,finite_loss_gradients_and_adam_state=True))
  if step not in [1,10,total] and step%50:continue
  ck=O/('checkpoint-%06d'%step);ck.mkdir(exist_ok=True);adapter={}
  for n,p in get_peft_model_state_dict(model).items():
   t=p.full_tensor() if hasattr(p,'full_tensor') else p
   if rank==0:adapter[n]=t.detach().cpu().contiguous()
  if rank==0:
   assert len(adapter)==416 and all(torch.isfinite(t).all() for t in adapter.values());save_file(adapter,str(ck/'adapter_model.safetensors'))
  state={'model':get_model_state_dict(model,options=StateDictOptions(ignore_frozen_params=True)),'optimizer':get_optimizer_state_dict(model,opt)}
  dcp.save(state,checkpoint_id=ck/'distributed_state');save(ck/('runtime_rank%d.json'%rank),dict(step=step,samples_seen=step*12,scheduler=schedule.state_dict()))
  torch.save(dict(step=step,rank=rank,cpu_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state(local)),ck/('rng_rank%d.pt'%rank));dist.barrier()
  if rank==0:save(O/'DURABLE_FRONTIER.json',dict(step=step,checkpoint=str(ck),time=time.time(),independent_readback_pending=True))
 if rank==0:save(O/'COMPLETE.json',dict(step=total,time=time.time(),revision=REV,independent_final_checkpoint_verification_pending=True))
 dist.barrier();dist.destroy_process_group()
if __name__=='__main__':
 O.mkdir(exist_ok=True)
 try:main()
 except BaseException:
  save(O/('FAILED_rank'+os.environ.get('RANK','unknown')+'.json'),dict(time=time.time(),traceback=traceback.format_exc(),automatic_retry=False));raise
