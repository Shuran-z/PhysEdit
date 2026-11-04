"""Publish original-reference evidence and new scores without replacing legacy scores."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_reference_admission_continue_20261101';BEFORE=WORK/'live_before';STAGE=WORK/'stage';STAGE.mkdir(exist_ok=True)
names=['formal_critical_cohorts.py','resources/core100_formal_cohorts.json',
       'resources/core100_additional_media_verification.json','resources/core100_reference_observability_progress.json']
files={name:(ROOT/'annotation_site'/name).read_bytes()for name in names}
raw=(ROOT/'annotation_site/resources/core100_distance_bindings.json').read_bytes();registry=json.loads(raw)
for name,digest in registry['evidence_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
manifest=json.loads((BEFORE/'resources/active_distance_join_manifest.json').read_text(encoding='utf8'))
manifest.update(registry_sha256=hashlib.sha256(raw).hexdigest(),registry_summary=registry['summary'],
                source_evidence_sha256=registry['evidence_sha256'],source_evidence_hashes_verified=len(registry['evidence_sha256']))
files['resources/core100_active_distance_bindings.json']=raw
files['resources/active_distance_join_manifest.json']=json.dumps(manifest,indent=2).encode()
code=(BEFORE/'formal_boundary_evaluation.py').read_text(encoding='utf8')
old="if c['cohort_id']=='t19-isaac-v1-h209f'";assert code.count(old)==2
code=code.replace(old,"if c['cohort_id']!='t17-contact-h6p4'")
needle='    # These are author-accepted observations';assert code.count(needle)==1
code=code.replace(needle,"    for row in outputs:\n        proof=replacement_outputs.get(row['task_id'])\n        if proof and any(e['clip_id']==row['clip_id'] and e['target_event']==row['event'] for e in explicit):\n            row['native_media_verified']=proof.get('native_media_verified',False)\n"+needle)
files['formal_boundary_evaluation.py']=(ROOT/'annotation_site/formal_boundary_evaluation.py').read_bytes()
code=(BEFORE/'server.py').read_text(encoding='utf8');old="'/api/formal-critical-outputs.csv')";assert code.count(old)==3
code=code.replace(old,"'/api/formal-critical-outputs.csv','/api/formal-critical-scene-models.csv')")
old="key='references' if p=='/api/formal-critical-references.csv' else 'outputs'";assert code.count(old)==1
code=code.replace(old,"key={'/api/formal-critical-references.csv':'references','/api/formal-critical-outputs.csv':'outputs','/api/formal-critical-scene-models.csv':'per_scene_model'}[p]")
files['server.py']=code.encode()
lines=(BEFORE/'static/app.js').read_text(encoding='utf8').splitlines();assert sum(line.startswith('function renderFormalCriticalCohorts(f)')for line in lines)==1
lines=[line for line in lines if not line.startswith('function renderFormalCriticalCohorts(f)')]
code='\n'.join(lines)+'\n'+'''
function renderFormalCriticalCohorts(f){const s=f.summary,p=f.all100_reference_progress;return `<section class="measure-section"><h3>Core100正式事件评分与临界子集</h3><p>Core100总量保持100条；原生参考视频已核对哈希并解码${p?.original_hash_verified_decoded??'待核验'}/100条。正式目标事件参考已接${s.formally_registered_reference_cases}/100条；Near参考${s.formally_registered_near_points}条，合法配对${s.formally_registered_pairs}组。仅有正侧的Near成绩单列，不补负侧、不伪造PairAcc。</p><p><a href="api/formal-critical-scene-models.csv">下载各场景各模型成绩</a> · <a href="api/formal-critical-references.csv">下载正式参考及观察窗</a> · <a href="api/formal-critical-outputs.csv">下载正式子集逐视频结果</a> · <a href="api/core100-connections.csv">下载全100条准入及缺项</a></p>${dataTable(['场景','模型','已判定/匹配输出','正确','完整场景目标正确率','已判定部分正确率','待补'],f.per_scene_model.map(m=>[m.scene,m.model,m.known+'/'+m.registered,m.correct,scoreValue(m.TargetAccuracy),scoreValue(m.accuracy_on_scored),m.pending]))}<details><summary>展开逐案例目标、单侧Near与跨界配对成绩</summary>${f.cohorts.map(c=>`<h4>${esc(c.cohort_id)} · ${c.horizon_s.toFixed(3)}秒</h4><p>参考${c.reference_cases}条；Near点${c.near_points}条；配对${c.reference_pairs}组。不同窗口分别评分，缺新版输出不继承旧标签。</p>${dataTable(['模型','匹配输出','历史输入排除','已判定','目标正确率','双侧NearAcc','单侧Near目标正确率','同seed PairAcc'],c.per_model.map(m=>[m.model,m.matching_registered,m.historical_excluded,m.known,scoreValue(m.TargetAccuracy),scoreValue(m.NearAcc),scoreValue(m.OneSidedNearTargetAccuracy),scoreValue(m.coupled_PairAcc)]))}`).join('')}</details><p class="subtle">单侧、已判定部分和限定场景的成绩均不冒充完整Core100成绩。原有正式字段与历史结果保留；质量失败按原协议计错，缺参考、窗口或人工定稿不填零。</p></section>`;}
'''
old='function renderFormalBoundary(c){const s=c.summary;'
assert code.count(old)==1
new='function renderFormalBoundary(c){if(c.explicit_formal_cohorts?.cohorts?.length>1){const s=c.explicit_formal_cohorts.summary;return `<section class="measure-section"><h3>正式评测入口</h3><p>当前正式目标参考${s.formally_registered_reference_cases}/100条；Near点${s.formally_registered_near_points}条、配对${s.formally_registered_pairs}组。各场景、窗口和模型成绩见下方“Core100正式事件评分与临界子集”；原T17历史对照字段保留，不再作为全场景汇总。</p></section>`;}const s=c.summary;'
code=code.replace(old,new)
files['static/app.js']=code.encode()
formal=json.loads(files['resources/core100_formal_cohorts.json'])
spec=dict(schema='core100-observable-continuation-overlay-v1',registry_summary=registry['summary'],formal_summary=formal['summary'],files=[])
for name,raw in files.items():
 p=STAGE/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);old=BEFORE/name
 spec['files'].append(dict(target=name,before_sha256=hashlib.sha256(old.read_bytes()).hexdigest()if old.exists()else None,after_sha256=hashlib.sha256(raw).hexdigest()))
(STAGE/'DEPLOY_INPUT.json').write_text(json.dumps(spec,indent=2))
with zipfile.ZipFile(WORK/'overlay.zip','w',zipfile.ZIP_DEFLATED)as z:
 for name in files:z.write(STAGE/name,name)
 z.write(STAGE/'DEPLOY_INPUT.json','DEPLOY_INPUT.json')
print(json.dumps(dict(files=len(files),formal=formal['summary'])))
