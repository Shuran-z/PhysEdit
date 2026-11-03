"""Versioned 100-case roster with eight approved published-contrast replacements."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
POINTER=ROOT/'catalog/core100_critical_pairs_v2.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(pointer_path=None):
    selected=Path(pointer_path).resolve()if pointer_path else POINTER
    if not selected.is_relative_to(ROOT):raise ValueError('rebalanced_pointer_outside_repository')
    pointer=json.loads(selected.read_text(encoding='utf8'));root=(selected.parent/pointer['release_root']).resolve()
    if not root.is_relative_to(ROOT):raise ValueError('rebalanced_release_outside_repository')
    if sha(root/pointer['manifest'])!=pointer['manifest_sha256']:raise ValueError('rebalanced_manifest_changed')
    m=json.loads((root/pointer['manifest']).read_text(encoding='utf8'))
    for name,digest in m['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root)or sha(path)!=digest:raise ValueError('rebalanced_file_changed')
    for name in ['parent_manifest','supplement_manifest']:
        if name not in m:continue
        ref=m[name]
        if sha(ROOT/ref['path'])!=ref['sha256']:raise ValueError('rebalanced_parent_changed')
    tasks=json.loads((root/'known_conditions.json').read_text(encoding='utf8'))['tasks']
    mapping=json.loads((root/'replacement_map.json').read_text(encoding='utf8'))
    wanted={f'T{i:02}_C{j:02}'for i in range(1,21)for j in range(1,6)}
    if len(tasks)!=100 or {r['clip_id']for r in tasks}!=wanted or Counter(r['clip_id'][:3]for r in tasks)!={f'T{i:02}':5 for i in range(1,21)}:
        raise ValueError('rebalanced_roster_invalid')
    return root,m,tasks,mapping

def export_replacements(out,model,*,fps,variant=1,seeds=(0,)):
    _,m,_,mapping=load()
    from .critical_supplement import export,DEFAULT
    result=export(DEFAULT,out,model,fps=fps,variant=variant,seeds=seeds)
    out=Path(out);point_to_clip={r['supplement_point_id']:r['clip_id']for r in mapping}
    # The immutable input source remains the supplement release. The complete
    # roster is separately identified; no old scores are renamed to this run.
    for name in ['inputs.jsonl','answers.jsonl']:
        rows=[json.loads(s)for s in (out/name).read_text(encoding='utf8').splitlines()]
        for row in rows:
            row['clip_id']=point_to_clip[row['point_id']];row['core100_roster_release']=m['version']
        (out/name).write_text(''.join(json.dumps(r)+'\n'for r in rows),encoding='utf8')
    spec=json.loads((out/'spec.json').read_text());spec['core100_roster_release']=m['version']
    (out/'spec.json').write_text(json.dumps(spec,indent=2),encoding='utf8')
    from .boundary import plan
    result=plan(spec);(out/'PRECHECK.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['status','export-replacements'])
    p.add_argument('--out',type=Path);p.add_argument('--model');p.add_argument('--fps',type=float,default=24)
    p.add_argument('--variant',type=int,default=1);p.add_argument('--seeds',nargs='+',type=int,default=[0])
    a=p.parse_args()
    if a.action=='status':
        _,m,_,mapping=load();print(json.dumps(dict(version=m['version'],registered=100,retained=92,replaced=8,
            per_scene=5,replacement_pairs=4,new_generation_pending=[r['clip_id']for r in mapping])))
    else:
        if not a.out or not a.model:p.error('--out and --model required')
        print(json.dumps(export_replacements(a.out,a.model,fps=a.fps,variant=a.variant,seeds=a.seeds)))

if __name__=='__main__':main()
