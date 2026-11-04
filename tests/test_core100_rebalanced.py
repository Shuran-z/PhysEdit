import json
from collections import Counter
from pathlib import Path
import sys

import pytest
from physedit import boundary,critical_supplement
from physedit import core100_rebalanced as roster
from physedit.core100_release import load as old_load

def test_new_roster_is_100_with_5_each_and_exactly_92_unchanged():
    _,m,tasks,mapping=roster.load()
    assert len(tasks)==100 and Counter(r['clip_id'][:3]for r in tasks)=={f'T{i:02}':5 for i in range(1,21)}
    changed={r['clip_id']for r in mapping};assert len(changed)==8
    assert {'T04_C01','T05_C01','T10_C01','T10_C02','T11_C01','T11_C02'}<=changed
    before={r['clip_id']:r for r in old_load()[2]['tasks']}
    assert sum(r==before[r['clip_id']]for r in tasks)==92
    assert all(r['new_generation_required']and r['new_annotation_required']for r in tasks if r['clip_id']in changed)
    assert not m['legacy_tasks_outputs_annotations_modified']

def test_new_pairs_and_old_active_entry_remain_separately_bound(tmp_path):
    _,m,tasks,mapping=roster.load()
    assert old_load()[1]['version']=='core100-t19-isaac-v1-20261031'
    result=roster.export_replacements(tmp_path/'new','TEST_ONLY',fps=24,seeds=[0,1,2])
    rows=boundary.read_rows(tmp_path/'new/inputs.jsonl')
    assert result['registered']==result['generation_candidates']==24
    assert result['target_counts']=={'1':12,'0':12}
    assert len({r['clip_id']for r in rows})==8
    assert all(r['core100_roster_release']==m['version']for r in rows)
    assert all('events'not in r and 'distance'not in r for r in rows)

def test_replacement_scoring_binds_roster_and_never_claims_all100(tmp_path,monkeypatch):
    out=tmp_path/'input';roster.export_replacements(out,'FIXTURE_NOT_MODEL',fps=24)
    spec=json.loads((out/'spec.json').read_text());spec['generation_command']=[sys.executable,'-c','pass']
    def media(path,row):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(row['sample_id'].encode())
        return dict(status='ok',video=str(path),video_sha256=boundary.digest(path))
    monkeypatch.setattr(boundary,'media',media)
    run=tmp_path/'run';boundary.run(spec,run)
    score=critical_supplement.score(run)
    assert score['registered']==8 and score['core100_roster_release']==roster.load()[1]['version']
    assert 'not the complete 100-case score'in score['evaluation_scope']
    rows=boundary.read_rows(run/'inputs.jsonl');rows[0]['clip_id']='T04_C05'
    (run/'inputs.jsonl').write_text(''.join(json.dumps(r)+'\n'for r in rows),encoding='utf8')
    with pytest.raises(ValueError,match='roster_binding_changed'):critical_supplement.score(run)
