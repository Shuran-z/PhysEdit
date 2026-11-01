"""Package immutable T17 supplemental and versioned T19 replacement inputs."""
import collections,hashlib,html,json,math,shutil,zipfile,gzip
from pathlib import Path
from PIL import Image
from physedit.core100_release import load

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/generation_handoff_20261030';OUT.mkdir(exist_ok=True)
PACK=OUT/'physics_generation_handoff'
assert not PACK.exists(),'Use a separately named build; do not overwrite an existing handoff.'
PACK.mkdir();sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
release,manifest,conditions,_=load()
version=manifest['version'];replacements={r['clip_id']:r for r in manifest['replacements']}
t19={r['clip_id']:r for r in conditions['tasks']if r['clip_id']in replacements}
snapshot=ROOT/'review/core100_all20_audit_20261030/live_snapshot.json.gz'
old=json.load(gzip.open(snapshot,'rt'))['tasks'];byid={t['id']:t['payload']for t in old}
sources=json.loads((ROOT/'annotation_site/resources/core100_t19_replacement_source.json').read_text(encoding='utf8'))
assert sources['version']==version
published=sources['published'];assert published['manifest_sha256']==sha(release/'MANIFEST.json')
bindings={r['clip_id']:r for r in map(json.loads,(ROOT.parent/'prompts_72000_unified/core100_generation_input_bindings.jsonl').read_text(encoding='utf8').splitlines())}
jobs=[];case_inputs=[]
def put_image(src,name,expected):
 assert sha(src)==expected
 dst=PACK/name;dst.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(src,dst)
 with Image.open(dst)as im:im.verify()
 with Image.open(dst)as im:return im.size
def prompt_file(group,case,variant,text):
 name=f'prompts/{group}/{case}__p{variant:02d}.txt';dst=PACK/name;dst.parent.mkdir(exist_ok=True,parents=True)
 if dst.exists():assert dst.read_bytes()==text.encode()
 else:dst.write_bytes(text.encode())
 return name
def finish(row,parent):
 fps=parent['fps'];row.update(recorded_model_native_fps=fps,minimum_frames_at_recorded_native_fps=math.ceil(row['evaluation_window_s']*fps-1e-9)+1,
  fps_requirement='Use genuine model native fps. Frame count must satisfy (frames-1)/fps >= evaluation_window_s; no retiming, looping, or frozen padding.',
  generation_status='not_started',actual_model_revision=None)
 row['output_video']=f"outputs/{row['group']}/{row['model']}/{row['task_id']}.mp4"
 row['output_receipt']=row['output_video'].removesuffix('.mp4')+'.json'
 assert row['seed']==parent['seed']and row['prompt_variant']==parent['prompt_variant']
 assert hashlib.sha256(row['prompt'].encode()).hexdigest()==row['prompt_sha256']
 jobs.append(row)

# T17 uses exactly the already prepared27 slots; Core100 negative outputs stay intact.
t17source=ROOT/'review/core100_execution_20261030/t17_positive_missing27.jsonl'
t17rows=[json.loads(l)for l in t17source.read_text(encoding='utf8').splitlines()];assert len(t17rows)==27
condition=ROOT/'review/prompt_length_natural_20261030/conditions/T17_C05.png';image='images/T17_W5_S01.png'
w,h=put_image(condition,image,bindings['T17_C05']['condition_image_sha256'])
assert bindings['T17_C04']['condition_pixel_sha256']==bindings['T17_C05']['condition_pixel_sha256']
for r in t17rows:
 parent=byid[r['negative_task_id']];assert parent['duration_s']>=5
 task=f"T17w5supp__{r['model']}__p{r['prompt_variant']}__s{r['seed']}"
 finish(dict(task_id=task,group='T17_W5_SUPPLEMENT',case_id='T17_W5_S01',model=r['model'],
  prompt_variant=r['prompt_variant'],seed=r['seed'],prompt=r['prompt'],prompt_sha256=r['prompt_sha256'],
  prompt_file=prompt_file('T17_W5_SUPPLEMENT','T17_W5_S01',r['prompt_variant'],r['prompt']),
  condition_image=image,condition_sha256=sha(PACK/image),condition_width=w,condition_height=h,
  reference_release_version='t17-window5-supplement-v1-20261030',condition_frame_index=4,
  evaluation_window_s=5.,requested_duration_s=5.,legacy_slot_id=r['negative_task_id'],
  paired_existing_negative_video_sha256=r['negative_video_sha256'],legacy_annotations_reusable=False,
  reference_status='new_parameter_point; numerical reference verified; RGB admission pending'),parent)

# T19 is five replacement cases, with each model's three original selected slots.
for cid,r in sorted(t19.items()):
 case=replacements[cid];image=f'images/T19_ISAAC_V1/{cid}.png'
 w,h=put_image(release/case['condition_image'],image,case['condition_sha256'])
 assert r['reference_release_version']==version
 assert case['condition_frame_index']==0
 horizon=(r['clock']['frame_count']-1)/r['clock']['media_fps'];assert horizon==209/30
 for variant,text in enumerate(r['prompt_variants_en'],1):
  assert hashlib.sha256(text.encode()).hexdigest()==r['prompt_variant_sha256'][variant-1]
  prompt_file('T19_ISAAC_V1',cid,variant,text)
 case_inputs.append({'case_id':cid,'reference_release_version':version,'condition_image':image,'condition_sha256':case['condition_sha256'],
  'reference_video_sha256':case['video_sha256'],'source_manifest_sha256':published['manifest_sha256'],
  'condition_frame_index':0,'condition_width':w,'condition_height':h,'evaluation_window_s':horizon,
  'prompt_variants':[{'variant':i,'prompt':text,'prompt_sha256':r['prompt_variant_sha256'][i-1]}for i,text in enumerate(r['prompt_variants_en'],1)]})
 for t in old:
  p=t['payload']
  if p['clip_id']!=cid:continue
  variant=p['prompt_variant'];task=f"T19isaacv1__{cid}__{p['model']}__p{variant}__s{p['seed']}"
  finish(dict(task_id=task,group='T19_ISAAC_V1',case_id=cid,model=p['model'],prompt_variant=variant,seed=p['seed'],
   prompt=r['prompt_variants_en'][variant-1],prompt_sha256=r['prompt_variant_sha256'][variant-1],
   prompt_file=f'prompts/T19_ISAAC_V1/{cid}__p{variant:02d}.txt',condition_image=image,condition_sha256=case['condition_sha256'],
   condition_width=w,condition_height=h,reference_release_version=version,reference_video_sha256=case['video_sha256'],
   condition_frame_index=0,evaluation_window_s=horizon,requested_duration_s=7.,reference_native_fps=30.,reference_native_frames=210,
   legacy_slot_id=t['id'],legacy_annotations_reusable=False,reference_status='active_versioned_replacement; generate new video; never inherit legacy label'),p)

assert len(jobs)==207 and len({r['task_id']for r in jobs})==207
models=sorted({r['model']for r in jobs});assert len(models)==12
def jl(path,rows):
 path.parent.mkdir(exist_ok=True,parents=True);path.write_bytes((''.join(json.dumps(r,ensure_ascii=False)+'\n'for r in rows)).encode())
jl(PACK/'tasks_all207.jsonl',jobs)
jl(PACK/'T17_tasks27.jsonl',[r for r in jobs if r['group']=='T17_W5_SUPPLEMENT'])
jl(PACK/'T19_tasks180.jsonl',[r for r in jobs if r['group']=='T19_ISAAC_V1'])
(PACK/'T19_case_inputs5.json').write_text(json.dumps(case_inputs,ensure_ascii=False,indent=2),encoding='utf8')
report=[]
for model in models:
 own=[r for r in jobs if r['model']==model];jl(PACK/f'model_tasks/{model}.jsonl',own)
 a=sum(r['group']=='T17_W5_SUPPLEMENT'for r in own);b=len(own)-a;assert b==15
 report.append({'model':model,'T17':a,'T19':b,'total':len(own)})
 lines=[f'# {model} 完整生成任务','',f'共{len(own)}条：T17补充{a}条，T19替换15条。路径均相对交付包根目录。逐行生成一次，seed及prompt不可自行改动。',
  '','T19按原生时长覆盖209/30秒（约6.966667秒）；若接口只提供时长预设，选足以覆盖的档位。标称7秒不保证末帧覆盖，必须核对实际帧数/fps。','']
 for r in own:
  lines += [f"## {r['task_id']}",'',f"- 组别／版本：{r['group']} / {r['reference_release_version']}",f"- 案例：{r['case_id']}；prompt变体：{r['prompt_variant']}；seed：**{r['seed']}**",f"- 参考图：[{r['condition_image']}](../{r['condition_image']})，{r['condition_width']}×{r['condition_height']}；条件帧索引{r['condition_frame_index']}",f"- 时长：请求{r['requested_duration_s']}秒，原生末帧时间至少{r['evaluation_window_s']:.9f}秒。若沿用原记录fps={r['recorded_model_native_fps']:g}，至少{r['minimum_frames_at_recorded_native_fps']}帧；还需满足模型自身帧数约束。",f"- 输出：`{r['output_video']}`",'', '完整prompt：','', '```text',r['prompt'],'```','']
  assert r['prompt']in '\n'.join(lines)
 (PACK/f'model_tasks/{model}.md').write_text('\n'.join(lines),encoding='utf8')

jl(PACK/'results.template.jsonl',[{'task_id':r['task_id'],'reference_release_version':r['reference_release_version'],'model':r['model'],
 'case_id':r['case_id'],'prompt_variant':r['prompt_variant'],'requested_seed':r['seed'],'status':'pending','effective_seed':None,
 'actual_model_id':None,'model_revision':None,'actual_prompt':None,'actual_prompt_sha256':None,'uploaded_condition_sha256':None,
 'image_preprocessing':None,'output_video':r['output_video'],'output_sha256':None,'frames':None,'fps':None,'native_duration_s':None,'error':None}for r in jobs])
(PACK/'models_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
(PACK/'source_bindings.json').write_text(json.dumps({'T17_source_tasks_sha256':sha(t17source),'legacy_task_snapshot_sha256':sha(snapshot),
 'T19_release_version':version,'T19_manifest_sha256':sha(release/'MANIFEST.json'),'T19_repo':published['repo'],'T19_revision':published['revision'],
 'T19_known_conditions_sha256':sha(release/'known_conditions.json'),'old_videos_and_annotations_modified':False,
 'T19_source_files_hash_verified':len(manifest['files']),'T19_generation_combo_policy':'reuse exactly3 original selected prompt/seed slots per model per case; no outcome-dependent seed'},ensure_ascii=False,indent=2),encoding='utf8')
shutil.copy2(ROOT/'review/core100_execution_20261030/t17_short_native9_retained.json',PACK/'T17_short_native9_not_requested.json')
readme='''# 物理视频补生成交付包

请先解压，再打开任务浏览器.html，或按model_tasks中对应模型的JSONL/完整说明运行。

共207条：T17正侧补充27条（9模型各3条）；T19新替换5个案例按12模型、每案例3组已冻结prompt/seed，共180条。T19“5条”指5个参考案例，不是总共只生成5条。全部完整prompt、整数seed、参考图和输出路径都在逐任务记录中。

## 怎么跑

1. 只跑自己负责模型的model_tasks/<模型>.jsonl，每行一次，不额外组合seed/变体。模型名称是原评测登记名，沿用对应权重，实际model_id/revision填入回执。
2. prompt字段原样提交（无截断、翻译、润色或加事件结局）；condition_image是相对包根目录的路径。使用整张指定图，模型若强制缩放/补边，记录实际处理和上传图哈希，不自行裁剪换图。
3. T17原生末帧至少5秒。T19原生末帧至少209/30秒≈6.966667秒；210帧30fps满足要求。其他fps按任务中最低帧数核对并满足模型自身约束。API按预设秒数生成时，若7秒档末帧不足，选择更长档（如8秒）。原生视频保留完整长度，评测再取登记窗口。
4. 不支持目标时长或seed时，在回执填unsupported_duration或unsupported_seed，不用减速、插帧、循环或静止补帧冒充。不要静默改seed或换模型。
5. 按output_video存到本包独立outputs目录，填写results.template.jsonl。记录实际prompt、seed是否生效、模型版本、帧数、fps、输出SHA256；原生末帧时间=(frames-1)/fps。

## 新旧版本

- T17使用新补充编号T17_W5_S01。legacy_slot_id只用于找到保留的负侧视频，绝不能覆盖它。三个短原生模型共9条负侧没有列入本轮27条请求，仍保留原结果。
- T19版本是core100-t19-isaac-v1-20261031，条件帧索引0；必须使用本包5张新图和新文本。不能使用旧T19图、旧输出或旧人工标签填新结果。
- 即使T19部分prompt相同，也不能按prompt去重：背景/参考图不同，任务身份由版本+案例+模型+变体+seed+图哈希共同确定。
- 旧视频、旧任务、旧标注保留为历史；新结果采用新task_id与独立输出路径。旧标注不可自动迁移，新视频后续另做质量/事件评测。

生成器只输入prompt和condition_image；本包没有参考事件答案、完整参考视频或预期结局。T17参考图来自原输入，T19参考图与已发布替换版本绑定。图像、文本及版本哈希见SHA256SUMS.json和source_bindings.json。

verify_package.py只检查交付包，不生成视频、不读写旧数据。使用Python运行：python verify_package.py。每个模型完整任务见下表。

|模型|T17补充|T19替换|总数|
|---|---:|---:|---:|
'''
for r in report:readme+=f"|{r['model']}|{r['T17']}|{r['T19']}|{r['total']}|\n"
(PACK/'README_先读.md').write_text(readme,encoding='utf8')

# Offline browser: embedded data, local images, no network or external libraries.
payload=json.dumps(jobs,ensure_ascii=False).replace('<','\\u003c')
page='''<!doctype html><meta charset="utf-8"><title>补生成任务完整输入</title><style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:0 20px;color:#193447}select{padding:9px;margin:8px}pre{white-space:pre-wrap;background:#edf3f7;padding:18px;line-height:1.7}img{max-width:100%;max-height:420px}code{overflow-wrap:anywhere}li{margin:8px 0}</style><h1>207条补生成任务</h1><p>T17补充27条；T19替换180条（5案例）。旧输出和旧标注保留。完整运行规则见README_先读.md。</p><label>模型<select id="model"></select></label><label>任务<select id="task"></select></label><main id="view"></main><script>
const rows=DATA;const models=[...new Set(rows.map(r=>r.model))];const m=document.getElementById('model'),t=document.getElementById('task'),v=document.getElementById('view');
function esc(x){return String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
m.innerHTML=models.map(x=>'<option>'+esc(x)+'</option>').join('');
function render(){const r=rows.find(r=>r.task_id===t.value);v.innerHTML='<h2>'+esc(r.case_id)+'</h2><ul><li>版本：'+esc(r.reference_release_version)+'</li><li>seed：<b>'+r.seed+'</b>；prompt变体：'+r.prompt_variant+'</li><li>原生末帧时间至少：'+r.evaluation_window_s.toFixed(9)+'秒；请求时长：'+r.requested_duration_s+'秒</li><li>原记录fps='+r.recorded_model_native_fps+'时，最低帧数='+r.minimum_frames_at_recorded_native_fps+'，还需满足模型约束</li><li>参考图：'+esc(r.condition_image)+'（条件帧索引'+r.condition_frame_index+'）</li><li>输出：<code>'+esc(r.output_video)+'</code></li></ul><img src="'+esc(r.condition_image)+'"><h3>完整prompt（原样复制）</h3><pre>'+esc(r.prompt)+'</pre>';}
function filter(){t.innerHTML=rows.filter(r=>r.model===m.value).map(r=>'<option value="'+esc(r.task_id)+'">'+esc(r.case_id)+' / p'+r.prompt_variant+' / seed '+r.seed+'</option>').join('');render();}
m.onchange=filter;t.onchange=render;filter();</script>'''.replace('DATA',payload)
(PACK/'任务浏览器.html').write_text(page,encoding='utf8')
shutil.copy2(ROOT/'scripts/verify_generation_handoff.py',PACK/'verify_package.py')
hashes={p.relative_to(PACK).as_posix():sha(p)for p in PACK.rglob('*')if p.is_file()}
(PACK/'SHA256SUMS.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
archive=OUT/'T17补生成27条_T19替换5例_207任务交付包.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as z:
 for p in sorted(PACK.rglob('*')):
  if p.is_file():z.write(p,'physics_generation_handoff/'+p.relative_to(PACK).as_posix())
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'tasks':len(jobs),'models':report},ensure_ascii=False,indent=2))
