"""Verify an additive prompt export against its untouched input catalog."""
from pathlib import Path
import gzip
import hashlib
import itertools
import json
import collections

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'review/prompt_revision_20261101'
SOURCE=ROOT/'review/prompt_rewrite_release_20261101/source/videos.jsonl.gz'
sha=lambda s:hashlib.sha256(s.encode()).hexdigest()

def rows(p):
    with gzip.open(p,'rt',encoding='utf8') as f:
        yield from (json.loads(line) for line in f)

def main():
    core=json.loads((BASE/'Core100_revised.json').read_text(encoding='utf8'))
    original=json.loads((BASE/'backup/Core100_original.json').read_text(encoding='utf8'))['tasks']
    assert len(core)==len(original)==100
    for old,new in zip(original,core):
        for k in ['clip_id','sample_id','reference','parameter_facts']:
            assert old[k]==new[k],(old['clip_id'],k)
        assert old['prompt_variants_en']==new['original_prompt_variants_en']
        assert len(new['prompt_variants_en'])==3
        assert new['prompt_variant_sha256']==[sha(s) for s in new['prompt_variants_en']]
        for text in new['prompt_variants_en']:
            assert all(clause in text for clause in new['source_control_clauses'])
    counts=collections.Counter();seen=set();pending=[]
    for old,backup,new in itertools.zip_longest(rows(SOURCE),rows(BASE/'backup/original_72000.jsonl.gz'),rows(BASE/'revised_72000.jsonl.gz')):
        assert old is not None and backup is not None and new is not None
        assert old==backup
        assert old['canonical_video_id']==new['video_id'] and new['video_id'] not in seen
        seen.add(new['video_id'])
        for a,b in [('sha256','video_sha256'),('download','download'),('split','split'),('source_group_id','source_group_id'),('parameter_facts','parameter_facts'),('config_download','config_download')]:
            assert old.get(a)==new.get(b),(new['video_id'],a)
        assert len(new['prompt_variants_en'])==3
        assert new['original_prompt_variant_sha256']==[sha(s) for s in old['prompt_variants_en']]
        assert new['prompt_variant_sha256']==[sha(s) for s in new['prompt_variants_en']]
        if new['parameter_conflicts']:assert old['prompt_variants_en']==new['prompt_variants_en']
        for text in new['prompt_variants_en']:
            assert all(clause in text for clause in new['source_control_clauses'])
        counts[new['status']]+=1
        if new['issues']:pending.append({'video_id':new['video_id'],'issues':new['issues'],'conflicts':new['parameter_conflicts']})
    assert len(seen)==72000
    (BASE/'pending_review.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2),encoding='utf8')
    report={'verified_rows':72000,'core100_rows':100,'three_variants_each':True,'original_backup_identical':True,'video_paths_hashes_splits_and_parameter_facts_unchanged':True,'control_clauses_present_in_all_three_variants':True,'parameter_conflict_prompts_unchanged':True,'status':dict(counts),'semantic_final_approval':False}
    (BASE/'VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
