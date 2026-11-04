"""Package a narrow overlay against an exact live-site source snapshot."""
import datetime
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'review/core100_all_connect_20261101'
before = WORK / 'live_before'
stage = WORK / 'stage'
stage.mkdir(exist_ok=True)
registry_raw = (ROOT / 'annotation_site/resources/core100_distance_bindings.json').read_bytes()
registry = json.loads(registry_raw)
verified = {}
for name, expected in registry['evidence_sha256'].items():
    actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    assert actual == expected, name
    verified[name] = actual
manifest = json.loads((before / 'resources/active_distance_join_manifest.json').read_bytes())
manifest.update(created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    registry_sha256=hashlib.sha256(registry_raw).hexdigest(), registry_summary=registry['summary'],
    previous_manifest_sha256=hashlib.sha256((before / 'resources/active_distance_join_manifest.json').read_bytes()).hexdigest(),
    source_evidence_hashes_verified=len(verified), source_evidence_sha256=verified,
    formal_reference_admission_granted=False, all100_connection=True)
files = {'resources/core100_active_distance_bindings.json': registry_raw,
         'resources/active_distance_join_manifest.json': json.dumps(manifest, indent=2).encode(),
         'core100_connection.py': (ROOT / 'annotation_site/core100_connection.py').read_bytes()}
code = (before / 'active_distance_results.py').read_text(encoding='utf8')
needle = ' return attach_scoped(result,tasks)'
assert code.count(needle) == 1
code = code.replace(needle, " from core100_connection import calculate as connect_all\n result['core100_connection']=connect_all(registry,tasks,policy,json.loads((root/'resources/reference_window_admission.json').read_text()))\n" + needle)
files['active_distance_results.py'] = code.encode()
code = (before / 'server.py').read_text(encoding='utf8')
old = "'/api/critical-window-gaps.csv')"
assert code.count(old) == 1
code = code.replace(old, "'/api/critical-window-gaps.csv','/api/core100-connections.csv','/api/core100-connected-outputs.csv','/api/core100-connected-boundaries.csv')")
needle = "                rows=result['execution_readiness']['cases']"
assert code.count(needle) == 1
code = code.replace(needle, "                if p in ('/api/core100-connections.csv','/api/core100-connected-outputs.csv','/api/core100-connected-boundaries.csv'):\n                    key={'/api/core100-connections.csv':'cases','/api/core100-connected-outputs.csv':'outputs','/api/core100-connected-boundaries.csv':'boundaries'}[p]\n                    return self.respond(critical_csv({'outputs':result['core100_connection'][key]}),ctype='text/csv; charset=utf-8')\n" + needle)
files['server.py'] = code.encode()
code = (before / 'static/app.js').read_text(encoding='utf8')
needle = " if(cr.contact_amendment)$('readiness-report')"
assert code.count(needle) == 1
code = code.replace(needle, " if(cr.core100_connection)$('readiness-report').insertAdjacentHTML('afterbegin',renderCore100Connections(cr.core100_connection));\n" + needle)
code += '''
function renderCore100Connections(c){const s=c.summary;return `<section class="measure-section"><h3>Core100当前临界边界 · 全20场景</h3><p>已连接${s.cases}个案例、${s.registered_outputs}条模型视频；数值参考${s.numerical_ready}/100，待闭合${s.numerical_pending}条。原参数族已有参考${s.original_family_ready??'待核对'}/100；全部登记参数轴${s.connected_parameter_axes}个，事件边界区间${s.boundary_records}条。校准值、辅助轴与正式边界分别保留。</p><p>当前事件与观察窗对应的输出证据齐备${s.current_window_output_ready}条；该计数不等于NearAcc准入。已有T17正式子集保持原窗口，其他案例的参考、窗口、配对缺项在下表列出，不填零。</p><p><a href="api/core100-connections.csv">100条接入及缺项</a> · <a href="api/core100-connected-boundaries.csv">全部参数轴与事件边界</a> · <a href="api/core100-connected-outputs.csv">3600条逐视频接入状态</a></p>${dataTable(['场景','数值参考 / 案例','待闭合','边界区间','视频'],c.scenes.map(r=>[r.scene,r.numerical_ready+'/'+r.cases,r.pending,r.boundary_records,r.registered_outputs]))}<details><summary>展开100条当前边界、观察窗及缺项</summary>${dataTable(['案例','参数轴','事件','参考窗(s)','数值状态','已复核/视频','参考/配对缺项','视频缺项'],c.cases.map(r=>[r.clip_id,r.connected_axes.join(' / ')||r.parameter,r.boundary_events.join(' / ')||'待登记边界',r.horizon_s.toFixed(3),r.distance_status,r.final_human+'/'+r.registered_outputs,r.reference_blockers.join('；'),Object.entries(r.output_blockers).map(([k,n])=>k+': '+n).join('；')]))}</details></section>`;}
'''
files['static/app.js'] = code.encode()
spec = dict(schema='core100-all-connection-overlay-v1', files=[], registry_summary=registry['summary'])
for name, raw in files.items():
    p = stage / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
    old = before / name
    spec['files'].append(dict(target=name, before_sha256=hashlib.sha256(old.read_bytes()).hexdigest() if old.exists() else None,
                              after_sha256=hashlib.sha256(raw).hexdigest()))
(stage / 'DEPLOY_INPUT.json').write_text(json.dumps(spec, indent=2))
with zipfile.ZipFile(WORK / 'overlay.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for p in stage.rglob('*'):
        if p.is_file(): archive.write(p, p.relative_to(stage).as_posix())
print(json.dumps(dict(files=len(files), evidence_verified=len(verified), summary=registry['summary'])))
