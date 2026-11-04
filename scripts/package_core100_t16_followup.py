"""Narrow T16 evidence overlay, preserving the live 24-reference release."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'review/core100_reference_admission_continue_20261101/t16_followup'
BEFORE = WORK / 'live_before'
STAGE = WORK / 'stage'
STAGE.mkdir(exist_ok=True)
names = ['formal_critical_cohorts.py', 'formal_boundary_evaluation.py',
         'resources/core100_formal_cohorts.json',
         'resources/core100_additional_media_verification.json',
         'resources/core100_reference_observability_progress.json']
formal = json.loads((ROOT / 'annotation_site/resources/core100_formal_cohorts.json').read_text())
old = json.loads((BEFORE / 'resources/core100_formal_cohorts.json').read_text())
by_id = {c['cohort_id']: c for c in formal['cohorts']}
for c in old['cohorts']:
    new = by_id[c['cohort_id']]
    assert new['pairs'] == c['pairs']
    for previous, current in zip(c['references'], new['references']):
        assert all(current[k] == v for k, v in previous.items() if k != 'original_protocol_scope')
    by_id[c['cohort_id']] = c
formal['cohorts'] = [by_id[c['cohort_id']] for c in formal['cohorts']]
assert formal['summary']['formally_registered_reference_cases'] == 26
old_media = json.loads((BEFORE / 'resources/core100_additional_media_verification.json').read_text())
media = json.loads((ROOT / 'annotation_site/resources/core100_additional_media_verification.json').read_text())
by_sha = {r['sha256']: r for r in media['rows']}
assert all(by_sha[r['sha256']] == r for r in old_media['rows']), 'Existing media proof changed'
manifest = json.loads((BEFORE / 'resources/active_distance_join_manifest.json').read_text())
spec = dict(schema='core100-t16-followup-v1', registry_summary=manifest['registry_summary'],
            formal_summary=formal['summary'], files=[])
for name in names:
    raw = (json.dumps(formal, ensure_ascii=False, indent=2).encode('utf8')
           if name == 'resources/core100_formal_cohorts.json'
           else (ROOT / 'annotation_site' / name).read_bytes())
    p = STAGE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    spec['files'].append(dict(target=name,
        before_sha256=hashlib.sha256((BEFORE / name).read_bytes()).hexdigest(),
        after_sha256=hashlib.sha256(raw).hexdigest()))
(STAGE / 'DEPLOY_INPUT.json').write_text(json.dumps(spec, indent=2))
with zipfile.ZipFile(WORK / 'overlay.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for name in names:
        z.write(STAGE / name, name)
    z.write(STAGE / 'DEPLOY_INPUT.json', 'DEPLOY_INPUT.json')
print(json.dumps(spec['formal_summary']))
