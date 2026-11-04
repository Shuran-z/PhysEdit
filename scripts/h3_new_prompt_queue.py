"""Start the fresh prompt-version H3 run once its actual inputs and GPUs are ready."""
from h3_new_prompt_common import *
import subprocess,fcntl,sys,shutil,signal,traceback
PY='/data/yangkaiyuan/cogvideox15_attn_ffn_lora_trial_20261030/venv/bin/python'
N=Path('/home/yangkaiyuan/phy_nvme/cog_final_native_sg_v1');O=R/'training'
def read(p):return json.loads(p.read_text()) if p.exists() else None
def resources():
 raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free','--format=csv,noheader,nounits']).decode();gpus={int(v[0]):dict(uuid=v[1].strip(),free_mib=int(v[2])) for v in [s.split(',') for s in raw.splitlines()]}
 apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader,nounits']).decode();active={g['uuid']:[] for g in gpus.values()}
 for line in apps.splitlines():
  if line.strip():v=line.split(',');active[v[1].strip()].append(dict(pid=int(v[0]),used_mib=v[2].strip()))
 for g in gpus.values():g['compute_contexts']=active[g['uuid']]
 memory=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
 return gpus,memory
def main():
 lock=(R/'training_queue.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert not (R/'TRAINER_LAUNCHED.json').exists(),'No duplicate or automatic replay'
 plan,data=rows();ids=json.loads((R/'training_order.json').read_text());start=time.time();leases=[]
 while True:
  assert not (R/'STOP_QUEUE').exists() and time.time()-start<14*86400
  if (R/'ENCODER_FAILED.json').exists():raise RuntimeError('Versioned encoder failed; training not launched')
  mode=read(R/'RESOURCE_MODE.json') or {'mode':'wait_existing_validation'};native=read(N/'INDEPENDENT_MATRIX_COMPLETE.json');done=bool(native and native.get('complete') and native.get('verified_outputs')==600 and native.get('verified_pairs')==300 and native.get('all_frozen_assets_rehashed'))
  allowed=mode['mode']=='priority_h3' or done
  if mode['mode']=='priority_h3':assert (R/'COG_VALIDATION_PAUSED_BY_USER_REQUEST.json').exists()
  available=sum((R/'cache'/(vid+'.pt')).exists() for vid in ids[:12]);gpus,mem=resources();chosen=[1,2]
  ready=all(not gpus[i]['compute_contexts'] and gpus[i]['free_mib']>=58000 for i in chosen)
  save(R/'QUEUE_STATUS.json',dict(time=time.time(),stage='waiting_input_prefix_and_gpu_release',hf_revision=REV,prefix_cache_ready=available,prefix_required=12,resource_mode=mode,native600_complete=done,gpus=gpus,host_memory_available_bytes=mem,training_started=False))
  if allowed and available==12 and ready and mem>=170*1024**3 and shutil.disk_usage(R).free>=700*1024**3:
   try:
    for i in chosen:
     f=Path('/tmp/physedit_sg_native_gpu%d.lock'%i).open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);leases.append(f)
   except BlockingIOError:
    for f in leases:f.close()
    leases=[];time.sleep(15);continue
   fresh,_=resources()
   if all(not fresh[i]['compute_contexts'] and fresh[i]['free_mib']>=58000 for i in chosen):break
   for f in leases:f.close()
   leases=[]
  time.sleep(15)
 # Read the exact producer output, verify all prompt/source/tensor hashes before GPU allocation.
 os.environ['RANK']='0';import h3_new_prompt_train as engine
 checks=[]
 for i in range(12):
  d,h=engine.cached(i,ids,data,plan);checks.append(dict(id=d['canonical_video_id'],cache_sha256=h,prompt_sha256=d['prompt_sha256'],source_sha256=d['source_sha256']));del d
 save(R/'TRAINING_PREFIX_CPU_VERIFIED.json',dict(status='PASS',records=checks,cuda_initialized=False))
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=','.join(gpus[i]['uuid'] for i in chosen),OMP_NUM_THREADS='2',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONUNBUFFERED='1',PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True');env.pop('FSDP_CPU_OFFLOAD',None);env.pop('RANK',None)
 command=[PY,'-m','torch.distributed.run','--standalone','--nproc_per_node=2',str(R/'h3_new_prompt_train.py')]
 O.mkdir(exist_ok=True)
 with (R/'trainer.log').open('ab') as log:child=subprocess.Popen(command,cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 save(R/'TRAINER_LAUNCHED.json',dict(time=time.time(),pid=child.pid,command=command,physical_gpu_indices=chosen,initial_step=0,target_steps=3764,hf_revision=REV,old_checkpoint_resumed=False))
 while child.poll() is None:
  _,mem=resources()
  if mem<24*1024**3 or shutil.disk_usage(R).free<40*1024**3 or (R/'STOP_TRAINING').exists():
   os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=60);raise RuntimeError('Own H3 stopped by infrastructure/stop guard; no automatic replay')
  save(R/'QUEUE_STATUS.json',dict(time=time.time(),stage='fresh_h3_training_running',pid=child.pid,training_started=True,progress=read(O/'progress.json'),ten_step_audit=read(O/'TEN_STEP_AUDIT_PASS.json')));time.sleep(15)
 save(R/'QUEUE_STATUS.json',dict(time=time.time(),stage='trainer_exited',returncode=child.returncode,training_started=True,complete=read(O/'COMPLETE.json')));assert child.returncode==0
if __name__=='__main__':
 try:main()
 except BaseException:
  save(R/'QUEUE_FAILED.json',dict(time=time.time(),traceback=traceback.format_exc(),automatic_training_replay=False));raise
