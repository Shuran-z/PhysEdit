"""Local review page; prefix media physically excludes frames beyond its horizon."""
import json,shutil
from pathlib import Path
import cv2

root=Path(__file__).resolve().parents[1]
run=root/'review/qwen35_window_v2_20261016';old=root/'review/other_scene_window_probe_20261016'
rows=[json.loads(x) for x in (run/'inputs.jsonl').read_text().splitlines()]
(run/'media').mkdir(exist_ok=True)
for row in rows:
    source=old/row['video'];dest=run/'media'/f"{row['sample_id']}.mp4"
    if dest.exists():
        check=cv2.VideoCapture(str(dest));fps=check.get(5);n=int(check.get(7));check.release()
        if n==round(row['duration_s']*fps)+1:continue
    if row.get('tracking_id'):
        cap=cv2.VideoCapture(str(source));fps=cap.get(5)
        writer=cv2.VideoWriter(str(dest),cv2.VideoWriter_fourcc(*'mp4v'),fps,(int(cap.get(3)),int(cap.get(4))))
        end=round(row['duration_s']*fps)
        for idx in range(end+1):
            ok,f=cap.read();assert ok;writer.write(f)
        writer.release();cap.release()
        check=cv2.VideoCapture(str(dest));assert int(check.get(7))==end+1;check.release()
    else:shutil.copyfile(source,dest)
items=json.loads((run/'routing_summary.json').read_text(encoding='utf-8'))['samples']
data=[dict(row,auto=next(s for s in items if s['sample_id']==row['sample_id'])) for row in rows]
page='''<!doctype html><meta charset="utf-8"><title>事件人工复核</title>
<style>body{font:17px system-ui;max-width:1050px;margin:30px auto;background:#f6f7fa;color:#172035}article{background:white;padding:22px;margin:20px 0;border-radius:12px}video{width:100%;max-height:460px}label{display:inline-block;margin:10px}select,input{padding:8px}button{padding:12px}textarea{width:95%;height:60px}</style>
<h1>观察窗事件人工复核</h1><p>先独立观看再填写。脱离支撑、下落、地面接触分开判断；“未观察到”不等于永远不发生。前缀视频已物理截断，无后续画面。全部五个开发输入供复核，不代表独立验证集。</p>
<label>审核人 <input id="reviewer" placeholder="必填"></label><button onclick="save()">导出人工记录 JSON</button><main id="cases"></main>
<script>const data=DATA;
const fields={departure:'是否脱离原支撑',descent:'是否脱离后下落',ground_contact:'是否观察到接触地面',identity_valid:'目标身份是否可追踪'};
const states=['pending','observed_yes','observed_no_within_window','not_observed_or_uncertain'];
for(const r of data){let a=document.createElement('article');a.id=r.sample_id;a.innerHTML=`<h2>${r.sample_id}</h2><p>${r.target} · ${r.window} · 截止 ${r.duration_s.toFixed(3)} 秒</p><video controls preload="metadata" src="media/${r.sample_id}.mp4"></video>`;
for(const [k,v] of Object.entries(fields)){let l=document.createElement('label');l.textContent=v+' ';let s=document.createElement('select');s.name=k;states.forEach(x=>{let o=document.createElement('option');o.value=x;o.textContent=x;s.append(o)});l.append(s);a.append(l)}
let t=document.createElement('textarea');t.placeholder='请写证据时间、可见现象或无法判断的原因';a.append(t);
let d=document.createElement('details');let sum=document.createElement('summary');sum.textContent='填写后可查看机器路由（避免先入为主）';d.append(sum);let pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.textContent=JSON.stringify(r.auto,null,2);d.append(pre);a.append(d);document.getElementById('cases').append(a)}
function save(){const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){alert('请填写审核人');return}const out=data.map(r=>{let a=document.getElementById(r.sample_id);return {sample_id:r.sample_id,source_sha256:r.sha256,window_end_s:r.duration_s,reviewer_id:reviewer,reviewed_at:new Date().toISOString(),labels:Object.fromEntries([...a.querySelectorAll('select')].map(x=>[x.name,x.value])),evidence_note:a.querySelector('textarea').value,protocol:'window-v2-human'}});let link=document.createElement('a');link.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));link.download='human_window_review.json';link.click();URL.revokeObjectURL(link.href)}
</script>'''
(run/'review.html').write_text(page.replace('DATA',json.dumps(data,ensure_ascii=False).replace('</','<\\/')),encoding='utf-8')
