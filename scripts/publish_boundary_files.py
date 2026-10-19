"""Copy explicitly scoped files into a clean worktree based on current remote main."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1];out=root.parent/'PhysEdit-GravTrace-boundary-publish'
files=['physedit/boundary.py','physedit/boundary_screening.py','physedit/boundary_pipeline.py','physedit/qwen_boundary_judge.py','physedit/boundary_triage.py','physedit/boundary_window.py','physedit/boundary_event_judge.py','physedit/boundary_dual_judge.py','tests/test_boundary_dual_judge.py',
'physedit/runners/boundary_ltx.py','scripts/build_t15_boundary_run.py','BOUNDARY_EVALUATION.md',
'tests/test_boundary.py','tests/test_boundary_pipeline.py','tests/test_boundary_triage.py','tests/test_boundary_window.py','tests/test_boundary_event_judge.py']
files += [str(p.relative_to(root)) for p in (root/'docs/critical_boundary').glob('*.md')]
for f in files:
 dest=out/f;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/f,dest)
p=out/'physedit/__main__.py';s=p.read_text(encoding='utf-8')
s=s.replace('import fcntl\n','').replace('from .driver import HUB_DIR, Driver\n','')
needle='    argv = list(sys.argv[1:] if argv is None else argv)\n'
replacement=needle+'''    if argv[:1] == ['boundary-evaluate']:
        from .boundary_pipeline import main as pipeline_main
        return pipeline_main(argv[1:])
    if argv[:1] == ['boundary']:
        from .boundary import main as boundary_main
        return boundary_main(argv[1:])
    import fcntl
    from .driver import HUB_DIR, Driver
'''
assert needle in s;s=s.replace(needle,replacement,1);p.write_text(s,encoding='utf-8')
p=out/'README.md';s=p.read_text(encoding='utf-8');s+='\n## Boundary event evaluation\n\nUse `python -m physedit boundary-evaluate` for independent quality screening, event preannotations, human review and full-roster scoring. See [the two-stage pipeline](docs/critical_boundary/TWO_STAGE_PIPELINE.md). Automatic labels remain provisional; default scores use human-confirmed event labels.\n';p.write_text(s,encoding='utf-8')
print(len(files),'scoped files copied; remote CLI preserved')
