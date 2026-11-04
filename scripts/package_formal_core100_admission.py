"""Package explicit already-admitted cohorts while retaining legacy score fields."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_formal_admission_20261101';BEFORE=WORK/'live_before';STAGE=WORK/'stage'
STAGE.mkdir(exist_ok=True)
files={name:(ROOT/'annotation_site'/name).read_bytes() for name in [
    'formal_critical_cohorts.py','resources/core100_formal_cohorts.json']}
code=(BEFORE/'active_distance_results.py').read_text(encoding='utf8')
needle=' return attach_scoped(result,tasks)';assert code.count(needle)==1
code=code.replace(needle," result=attach_scoped(result,tasks)\n from formal_critical_cohorts import attach as attach_formal\n return attach_formal(result,tasks)")
files['active_distance_results.py']=code.encode()
registry_raw=(ROOT/'annotation_site/resources/core100_distance_bindings.json').read_bytes()
registry=json.loads(registry_raw)
for name,expected in registry['evidence_sha256'].items():
 assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
manifest=json.loads((BEFORE/'resources/active_distance_join_manifest.json').read_text(encoding='utf8'))
manifest.update(registry_sha256=hashlib.sha256(registry_raw).hexdigest(),registry_summary=registry['summary'],
                source_evidence_hashes_verified=len(registry['evidence_sha256']),source_evidence_sha256=registry['evidence_sha256'])
files['resources/core100_active_distance_bindings.json']=registry_raw
files['resources/active_distance_join_manifest.json']=json.dumps(manifest,indent=2).encode()
code=(BEFORE/'formal_boundary_evaluation.py').read_text(encoding='utf8')
needle="    references=[];outputs=[]";assert code.count(needle)==1
code=code.replace(needle,"    extra=result.get('formal_critical_cohorts',{})\n    explicit=[r for c in extra.get('cohorts',[])if c['cohort_id']=='t19-isaac-v1-h209f' for r in c['references']]\n    replacement_outputs={r['task_id']:r for c in extra.get('cohorts',[])if c['cohort_id']=='t19-isaac-v1-h209f' for r in c['outputs']}\n"+needle)
needle="            key=hashlib.sha256";assert code.count(needle)==1
code=code.replace(needle,"            restored=any(e['reference_video_sha256']==ref['reference_video_sha256'] and e['reference_release_version']==ref['reference_release_version'] and e['target_event']==event and e['horizon_s']==ref['horizon_s'] and e['theta']==axis['theta'] and e['reference_label']==axis['reference_events'][event] and e['boundary_interval']==boundary['bracket'] and e['normalization_span']==axis['normalization_span'] for e in explicit)\n            admitted=admitted or restored\n"+needle)
needle="                outputs.append(dict(task_id=";assert code.count(needle)==1
code=code.replace(needle,"                if restored:\n                    strict=replacement_outputs.get(task['id'])\n                    correct=strict['final_correct'] if strict else None\n                    problems=list(strict['blockers']) if strict else ['strict_replacement_observation_missing']\n"+needle)
needle="    return result";assert code.count(needle)==1
code=code.replace(needle,"    result['formal_boundary_evaluation']['explicit_formal_cohorts']=extra\n    result['formal_boundary_evaluation']['summary'].update(current_formal_near_points=extra.get('summary',{}).get('formally_registered_near_points'),current_formal_pairs=extra.get('summary',{}).get('formally_registered_pairs'))\n"+needle)
files['formal_boundary_evaluation.py']=code.encode()
code=(BEFORE/'server.py').read_text(encoding='utf8')
needle="'/api/core100-connected-boundaries.csv')";assert code.count(needle)==2
# Both the route allowlist and the CSV dispatch need the additional paths.
code=code.replace(needle,"'/api/core100-connected-boundaries.csv','/api/formal-critical-references.csv','/api/formal-critical-outputs.csv')")
needle="                    key={'/api/core100-connections.csv'";assert code.count(needle)==1
code=code.replace(needle,"                    if p in ('/api/formal-critical-references.csv','/api/formal-critical-outputs.csv'):\n                        key='references' if p=='/api/formal-critical-references.csv' else 'outputs'\n                        return self.respond(critical_csv({'outputs':result['formal_critical_cohorts'][key]}),ctype='text/csv; charset=utf-8')\n"+needle)
files['server.py']=code.encode()
code=(BEFORE/'static/app.js').read_text(encoding='utf8')
needle=" if(cr.core100_connection)$('readiness-report')";assert code.count(needle)==1
code=code.replace(needle," if(cr.formal_critical_cohorts)$('readiness-report').insertAdjacentHTML('afterbegin',renderFormalCriticalCohorts(cr.formal_critical_cohorts));\n"+needle)
code+='''
function renderFormalCriticalCohorts(f){const s=f.summary;return `<section class="measure-section"><h3>正式准入参考与实时评分</h3><p>已登记正式参考${s.formally_registered_reference_cases}条，其中Near点${s.formally_registered_near_points}条、跨界配对${s.formally_registered_pairs}组。T17与新版T19按各自冻结窗口分别评分；新版T19不得继承旧视频标签。</p><p><a href="api/formal-critical-references.csv">下载正式参考、边界与窗口</a> · <a href="api/formal-critical-outputs.csv">下载正式子集逐视频评分及缺项</a></p>${f.cohorts.map(c=>`<h4>${esc(c.cohort_id)} · ${c.horizon_s.toFixed(3)}秒</h4><p>参考${c.reference_cases}条，Near点${c.near_points}条，配对${c.reference_pairs}组。PairAcc按相同prompt变体与seed逐对计算；不将两侧准确率相乘冒充同seed配对成绩。</p>${dataTable(['模型','匹配新输入','历史输入排除','已判定','NearAcc','同seed PairAcc','有效/登记配对','状态'],c.per_model.map(m=>[m.model,m.matching_registered,m.historical_excluded,m.known,scoreValue(m.NearAcc),scoreValue(m.coupled_PairAcc),m.known_pair_slots+'/'+m.pair_slots,{awaiting_matching_generation:'缺对应版本生成视频',complete:'已完成',coverage_or_review_pending:'窗口或复核待补'}[m.status]||m.status]))}`).join('')}<p class="subtle">未覆盖窗口、缺新版输出或复核未完成时为N/A；原有正式字段及历史结果保留。</p></section>`;}
'''
files['static/app.js']=code.encode()
summary=registry['summary']
spec=dict(schema='core100-formal-admission-overlay-v1',registry_summary=summary,files=[])
for name,raw in files.items():
 p=STAGE/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);old=BEFORE/name
 spec['files'].append(dict(target=name,before_sha256=hashlib.sha256(old.read_bytes()).hexdigest() if old.exists() else None,
                          after_sha256=hashlib.sha256(raw).hexdigest()))
(STAGE/'DEPLOY_INPUT.json').write_text(json.dumps(spec,indent=2))
with zipfile.ZipFile(WORK/'overlay.zip','w',zipfile.ZIP_DEFLATED)as z:
 for name in files:z.write(STAGE/name,name)
 z.write(STAGE/'DEPLOY_INPUT.json','DEPLOY_INPUT.json')
print('packaged',len(files),'files')
