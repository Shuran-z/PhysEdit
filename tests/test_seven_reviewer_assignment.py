import ast
import collections
from pathlib import Path
import random


def test_every_video_gets_two_distinct_reviewers_with_exact_workload():
    p=Path(__file__).resolve().parents[1]/'review/cvpr_experiments_20261031/auxiliary_review/split_seven_reviewers.py'
    tree=ast.parse(p.read_text(encoding='utf8'))
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='allocate']
    ns={'random':random,'collections':collections}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(p),'exec'),ns)
    groups={str(g):[str(g)+'_'+str(i)for i in range(18)]for g in range(4)}
    rows=ns['allocate'](groups)
    assert len(rows)==144
    assert collections.Counter(r['reviewer_id']for r in rows)=={r:24 if r in 'ABCDE'else 12 for r in 'ABCDEFG'}
    for group,ids in groups.items():
        selected=[r for r in rows if r['sample_id']in ids]
        assert collections.Counter(r['reviewer_id']for r in selected)=={r:6 if r in 'ABCDE'else 3 for r in 'ABCDEFG'}
        for sid in ids:assert len({r['reviewer_id']for r in selected if r['sample_id']==sid})==2
