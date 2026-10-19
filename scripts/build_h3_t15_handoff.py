"""Package existing inputs and executable source; no weights or credentials."""
from pathlib import Path
import shutil
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'review/h3_t15_handoff_20261016'
out.mkdir(exist_ok=False)
files=['docs/critical_boundary/H3_T15_HANDOFF.md','docs/critical_boundary/FAILURE_HANDLING.md',
       'docs/critical_boundary/PIPELINE.md','physedit/boundary.py','physedit/boundary_screening.py',
       'physedit/runners/minimax_h3.py']
files += [str(p.relative_to(ROOT)) for p in (ROOT/'gravtrace').glob('*.py')]
for f in files:
    dst=out/f;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/f,dst)
(out/'physedit/__init__.py').write_text('',encoding='utf-8')
base=ROOT/'review/t15_basic_validation_20261014'
for name in ['case01.png','case02.png','case01.txt','case02.txt']:
    dst=out/'inputs'/name;dst.parent.mkdir(exist_ok=True);shutil.copy2(base/'h3_inputs'/name,dst)
for name in ['references.json','fall_source.json','nofall_source.json']:
    shutil.copy2(base/name,out/'inputs'/name)
(out/'prepare_h3_manifest.py').write_text('''from pathlib import Path
import json
root=Path(__file__).resolve().parent
rows=[]
for seed in (41000,41001):
    for case in ('case01','case02'):
        sid=f't15_h3_{case}_s{seed}'
        rows.append(dict(sample_id=sid,source_sample_id=sid,index=len(rows),
            prompt_granularity='basic_initial_conditions',
            condition_image=str(root/'inputs'/f'{case}.png'),
            prompt_file=str(root/'inputs'/f'{case}.txt'),seed=seed,
            source_width=854,source_height=480,gen_width=896,gen_height=512,
            scenario='T15',template='basic_validation',num_frames=124,output_fps=24))
with (root/'h3_manifest.jsonl').open('x',encoding='utf-8') as f:
    for row in rows:f.write(json.dumps(row)+'\\n')
print('Registered four outputs, unique directories; shared seeds 41000/41001.')
''',encoding='utf-8')
(out/'README.md').write_text('Start with docs/critical_boundary/H3_T15_HANDOFF.md. This is a source/input handoff, not an installed environment. No generation or inference has been launched.\n',encoding='utf-8')
hashes={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
(out/'checksums.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
shutil.make_archive(str(out),'zip',out)
print(out.with_suffix('.zip'))
