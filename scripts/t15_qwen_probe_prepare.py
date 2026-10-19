"""Prepare an outcome-blind five-video Qwen event-judge diagnostic."""
import hashlib,json,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/t15_qwen_judge_20261015'
OUT.mkdir(exist_ok=False)
media=OUT/'media';media.mkdir()
cases=[('case01','generated','t15_earth_A1_s1',None),
       ('case02','reference','fall',1),
       ('case03','generated','t15_earth_A2_s0',0),
       ('case04','reference','nofall',0),
       ('case05','generated','t15_earth_A0_s0',None)]
inputs=[];key=[]
for sid,kind,name,label in cases:
    dest=media/(sid+'.mp4')
    if kind=='reference':
        record=json.loads((ROOT/f'review/t15_basic_validation_20261014/{name}_source.json').read_text(encoding='utf-8'))
        subprocess.run(['scp','p25:'+record['video'],str(dest)],check=True,timeout=180)
    else:
        shutil.copyfile(ROOT/f'review/t15_followup_20261014/generated_media/{name}.mp4',dest)
    sha=hashlib.sha256(dest.read_bytes()).hexdigest()
    inputs.append(dict(sample_id=sid,video='media/'+sid+'.mp4',sha256=sha,start_frame=29 if kind=='reference' else 0,duration_s=6))
    key.append(dict(sample_id=sid,source_type=kind,source_id=name,prior_fall=label,
                    prior_status='state_audit_and_visual_check' if kind=='reference' else 'assistant_review_not_independent_human_gold'))
(OUT/'inputs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in inputs),encoding='utf-8')
(OUT/'answer_key.json').write_text(json.dumps(key,indent=2),encoding='utf-8')
print(str(OUT))
