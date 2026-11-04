"""Prepare a narrow CAS overlay and calculate the unchanged-label formal scores."""
import csv
import gzip
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_remaining74_admission_20261101'
BEFORE=WORK/'live_before';STAGE=WORK/'stage';STAGE.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda raw:hashlib.sha256(raw).hexdigest()
sys.path.insert(0,str(ROOT/'annotation_site'))
from formal_critical_cohorts import calculate
registry=read(ROOT/'annotation_site/resources/core100_formal_cohorts.json')
old=read(BEFORE/'resources/core100_formal_cohorts.json')
tasks=json.loads(gzip.decompress((WORK/'TASKS.json.gz').read_bytes()))
assert len(tasks)==3600
previous=read(ROOT/'review/core100_reference_admission_continue_20261101/t16_followup/LIVE_FORMAL.json')
stub={'admitted_cohort':{'outputs':previous['cohorts'][0]['outputs']}}
policy=read(ROOT/'annotation_site/resources/core100_final_input_policy.json')
oldmedia={r['sha256']:r for r in read(BEFORE/'resources/core100_additional_media_verification.json')['rows']}
media={r['sha256']:r for r in read(ROOT/'annotation_site/resources/core100_additional_media_verification.json')['rows']}
before=calculate(old,stub,tasks,policy,oldmedia)
after=calculate(registry,stub,tasks,policy,media)
by={c['cohort_id']:c for c in after['cohorts']}
for cohort in before['cohorts']:
    assert by[cohort['cohort_id']]==cohort,'Old cohort changed: '+cohort['cohort_id']
(WORK/'CALCULATED_FORMAL.json').write_text(json.dumps(after,indent=2))
with (WORK/'SCENE_MODEL_RESULTS.csv').open('w',encoding='utf-8-sig',newline='')as f:
    w=csv.DictWriter(f,fieldnames=list(after['per_scene_model'][0]));w.writeheader();w.writerows(after['per_scene_model'])

names=['formal_critical_cohorts.py','formal_boundary_evaluation.py',
       'resources/core100_formal_cohorts.json','resources/core100_additional_media_verification.json',
       'resources/core100_reference_observability_progress.json']
files={n:(ROOT/'annotation_site'/n).read_bytes()for n in names}
code=(BEFORE/'static/app.js').read_text(encoding='utf8')
needle='正式目标事件参考已接${s.formally_registered_reference_cases}/100条；Near参考'
assert code.count(needle)==1
code=code.replace(needle,'正式目标事件参考已接${s.formally_registered_reference_cases}/100条；原边界区间已核验${s.formally_registered_interval_reference_cases??"待核验"}条；Near参考')
files['static/app.js']=code.encode()
manifest=read(BEFORE/'resources/active_distance_join_manifest.json')
spec=dict(schema='core100-remaining74-original-admission-v1',registry_summary=manifest['registry_summary'],formal_summary=registry['summary'],files=[])
for n,raw in files.items():
    p=STAGE/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    spec['files'].append(dict(target=n,before_sha256=sha((BEFORE/n).read_bytes()),after_sha256=sha(raw)))
(STAGE/'DEPLOY_INPUT.json').write_text(json.dumps(spec,indent=2))
with zipfile.ZipFile(WORK/'overlay.zip','w',zipfile.ZIP_DEFLATED)as z:
    for n in files:z.write(STAGE/n,n)
    z.write(STAGE/'DEPLOY_INPUT.json','DEPLOY_INPUT.json')
print(json.dumps(dict(summary=registry['summary'],old_cohorts_preserved=len(before['cohorts']),known=sum(r['final_correct']is not None for r in after['outputs']),correct=sum(r['final_correct']or 0 for r in after['outputs']),outputs=len(after['outputs']))))
