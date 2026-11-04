from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.h3_prompt_sg_transport import run,PY
OUT=ROOT/'review/prompt_semantic_repair_20261102';REMOTE='/data/yangkaiyuan/h3_prompt_retrain_semantic_v2_20261102'
def main():
 code=f'''from pathlib import Path
import os,sys,json,time
r=Path({REMOTE!r});sys.path.insert(0,str(r));os.environ['RANK']='0'
from h3_new_prompt_common import rows,save
from h3_new_prompt_train import cached
plan,data=rows();ids=json.loads((r/'training_order.json').read_text());start=time.time()
while sum((r/'cache'/(x+'.pt')).exists()for x in ids[:12])<12:
 assert time.time()-start<600 and not(r/'ENCODER_FAILED.json').exists();time.sleep(5)
records=[]
for i in range(12):
 d,h=cached(i,ids,data,plan);row=data[ids[i]];assert d['prompt_sha256']==d['source_prompt_sha256']==row['prompt_variant_sha256'][d['prompt_variant']-1]
 records.append(dict(id=ids[i],cache_sha256=h,prompt_sha256=d['prompt_sha256'],source_sha256=d['source_sha256'],vae_reused=d['vae_reuse']['reused'],condition_reused=bool(d.get('condition_reuse'))));del d
import torch
assert not torch.cuda.is_initialized()
result=dict(status='PASS',time=time.time(),hf_revision=plan['hf_revision'],training_manifest_sha256=plan['manifest_sha256'],verified_current_features=12,all_model_texts_byte_identical_to_selected_published_variant=True,records=records,model_loaded=False,training_updates=0,cuda_initialized=False)
save(r/'INDEPENDENT_PREFIX_VERIFIED.json',result);print(json.dumps(result))
'''
 result=json.loads(run(code,python=PY,timeout=650));(OUT/'H3_INDEPENDENT_PREFIX_VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
if __name__=='__main__':main()
