import copy,json
from pathlib import Path
from physedit.core100_critical import ROOT,load,prepare,sha
from physedit.core100_rebalanced import load as load_roster


def restored():
    pointer=ROOT/'catalog/prepared_core100_critical_protocol_v5.json';p=json.loads(pointer.read_text())
    return load((pointer.parent/p['registry']).resolve(),p['registry_sha256'])


def test_actual_submission_restoration_changes_no_physical_reference_or_boundary():
    new,_=restored();p=new['prompt_binding_parent'];old,_=load(ROOT/p['path'],p['sha256'])
    assert new['cases']==old['cases']and new['pairs']==old['pairs']
    changed=[]
    for a,b in zip(old['input_bindings'],new['input_bindings']):
        av=copy.deepcopy(a);bv=copy.deepcopy(b)
        for k in ['prompt_variants_en','prompt_variant_sha256']:av.pop(k);bv.pop(k)
        assert av==bv
        if a!=b:changed.append(b['clip_id'])
    assert len(changed)==57 and changed==new['submitted_prompt_restoration']['cases']or sorted(changed)==new['submitted_prompt_restoration']['cases']
    assert new['summary']['critical_rgb_distance_cases']==100


def test_bound_text_matches_frozen_submission_hashes_not_recovered_wording():
    data,_=restored();root,manifest,tasks,_=load_roster(ROOT/'catalog/core100_critical_pairs_v5.json')
    evidence=json.loads((root/'evidence/ACTUAL_SUBMITTED_PROMPTS.json').read_text())
    assert evidence['policy_sha256']=='547d7045df9493cdb5cfcd0f78996c3049203169dfcdc43a0efd592178832fac'
    source={r['clip_id']:r for r in evidence['cases']};bindings={r['clip_id']:r for r in data['input_bindings']}
    assert len(source)==81
    assert bindings['T01_C01']['prompt_variant_sha256'][0]=='9e42c55cf2085cc408f76ee3087b3ec9af98e1fab64b15c8516e40e4877c02eb'
    for cid,s in source.items():
        assert bindings[cid]['prompt_variants_en']==s['prompt_variants_en']
        assert bindings[cid]['prompt_variant_sha256']==s['prompt_variant_sha256']
        assert len(s['source_generation_records'])==3
    assert len(manifest['model_generation_and_annotation_pending'])==15


def test_repaired_plan_exports_actual_text_and_keeps_all100_registered(tmp_path):
    data,path=restored();plan=tmp_path/'plan';prepare(plan,'INPUT_EXPORT_TEST_ONLY',fps=24.,registry_path=path,expected_sha256=sha(path))
    rows=[json.loads(s)for s in(plan/'inputs.jsonl').read_text().splitlines()]
    assert len(rows)==100
    r=next(r for r in rows if r['clip_id']=='T01_C01')
    assert r['prompt_sha256']=='9e42c55cf2085cc408f76ee3087b3ec9af98e1fab64b15c8516e40e4877c02eb'
    assert 'Surface friction 0.2.'in r['prompt']
    assert 'reference_events'not in r and 'boundary'not in r
