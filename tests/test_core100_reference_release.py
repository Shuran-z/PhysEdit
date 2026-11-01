import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from physedit import core100_release as release
from physedit.boundary import distance, plan, score
from physedit.known_conditions import attach


ROOT=Path(__file__).resolve().parents[1]


def read_rows(path):
    return [json.loads(s) for s in path.read_text(encoding='utf8').splitlines()]


def test_active_roster_replaces_exactly_five_and_preserves_95():
    root,manifest,conditions,rows=release.load()
    previous=json.loads((ROOT/'review/core100_admission_20261023/v6_known_conditions.json').read_text(encoding='utf8'))
    old={r['clip_id']:r for r in previous['tasks']}
    assert len(rows)==100
    for c in conditions['tasks']:
        assert (c==old[c['clip_id']]) == (not c['clip_id'].startswith('T19'))
    # Actual existing attachment path must accept the replacement identities.
    attached=attach(rows,root/'known_conditions.json')
    assert len(attached)==100
    assert len({r['native_sample_id'] for r in manifest['replacements']})==5
    assert sum(r['uses_updated_media'] for r in manifest['replacements'])==1


def test_boundary_pairs_and_other_side_of_contact_band():
    root,manifest,_,_=release.load()
    keys={r['point_id']:r for r in read_rows(root/'answers_t19.jsonl')}
    for pair in manifest['pairs']:
        a,b=(keys[c] for c in pair['clips'])
        assert a['source_group_id']==b['source_group_id']
        assert [a['events'][a['target_event']],b['events'][b['target_event']]]==[0,1]
        assert distance(a)['bin']==distance(b)['bin']=='near'
    c=keys['T19_C05']
    assert c['boundary']['bracket']==[.0875,.105]
    assert distance(c)['normalized_absolute_interval']==pytest.approx([.125,.1875])
    assert distance(c)['bin'] is None


@pytest.mark.parametrize('mode',['independent','coupled_seed'])
def test_new_generation_runs_reach_existing_scorer(tmp_path,mode):
    out=tmp_path/'run'
    receipt=release.prepare(out,'contract_test',pairing_mode=mode)
    assert receipt['registered']==5 and receipt['generation_not_gated_by_inversion']
    inputs=read_rows(out/'inputs.jsonl');answers=read_rows(out/'answers.jsonl')
    by={r['point_id']:r for r in answers};seeds={r['clip_id']:r['seed'] for r in inputs}
    assert (seeds['T19_C01']==seeds['T19_C02']) == (mode=='coupled_seed')
    assert all('core100_t19_v1_' in r['sample_id'] for r in inputs)
    # Deterministic protocol self-check using reference videos, never a model score.
    registered={'model':'reference_oracle_contract_test'}
    (out/'registered.json').write_text(json.dumps(registered),encoding='utf8')
    hashes={n:release.digest(out/n) for n in ['inputs.jsonl','answers.jsonl','registered.json']}
    (out/'snapshot_hashes.json').write_text(json.dumps(hashes),encoding='utf8')
    observed=[];annotations=[]
    for inp,key in zip(inputs,answers):
        observed.append(dict(sample_id=inp['sample_id'],status='ok',video=inp['source_video'],video_sha256=inp['source_video_sha256']))
        annotations.append(dict(sample_id=inp['sample_id'],video_sha256=inp['source_video_sha256'],
            method='source_truth_protocol_selfcheck_not_model_result',evidence=['native_source_qa'],
            events=key['events'],event_times_s=key['reference_event_times_s']))
    for name,data in [('observed_rows.jsonl',observed),('oracle_annotations.jsonl',annotations)]:
        (out/name).write_text(''.join(json.dumps(r)+'\n' for r in data),encoding='utf8')
    result=score(out,out/'oracle_annotations.jsonl')
    assert result['registered']==5
    assert result['balanced_accuracy']==result['near_accuracy']==result['event_exact']==1
    metric='independent_pair_accuracy' if mode=='independent' else 'coupled_pair_accuracy'
    assert result[metric]==1


def test_old_t19_outputs_cannot_be_relabelled_as_new():
    root,manifest,conditions,rows=release.load()
    new=manifest['replacements'][0]
    old={'payload':dict(clip_id=new['clip_id'],reference_video_sha256='0'*64,
                        condition_sha256=new['condition_sha256'],reference_release_version=manifest['version'])}
    value=release.status([old])
    assert value['matching_generated_records']==0
    assert value['historical_T19_records_not_relabelled']==1


def test_tampering_with_frozen_parameters_is_rejected(tmp_path):
    root,_,_,_=release.load()
    dest=tmp_path/'bundle';shutil.copytree(root,dest)
    pointer=json.loads(release.ACTIVE.read_text(encoding='utf8'))
    pointer['release_root']='bundle'
    p=tmp_path/'active.json';p.write_text(json.dumps(pointer),encoding='utf8')
    (dest/'known_conditions.json').write_text('{}',encoding='utf8')
    with pytest.raises(ValueError,match='active_core100_file_changed'):
        release.load(p)


def test_annotation_input_and_window_use_new_version_without_changing_v6():
    import sys
    sys.path.insert(0,str(ROOT/'annotation_site'))
    from input_contract import matches_frozen_input
    from window_contract import window_binding
    _,manifest,conditions,_=release.load()
    case=manifest['replacements'][0]
    condition=next(c for c in conditions['tasks'] if c['clip_id']==case['clip_id'])
    payload=dict(clip_id=case['clip_id'],reference_release_version=manifest['version'],
        reference_video_sha256=case['video_sha256'],condition_sha256=case['condition_sha256'],
        prompt_variant=1,seed=0,source=dict(generation_metadata=dict(prompt=condition['prompt_variants_en'][0])),
        fps=30.,frames=210,duration_s=209/30.,window_s=209/30.)
    old=json.loads((ROOT/'annotation_site/resources/core100_final_input_policy.json').read_text(encoding='utf8'))
    # A reference replacement is not proof that a new generated output belongs
    # to the author's separately registered actual-generation cohort.
    if old.get('schema')=='core100-actual-generation-inputs-v1':
        assert not matches_frozen_input(payload,old)
    reference_policy={**old,'schema':'reference-release-input-check'}
    assert matches_frozen_input(payload,reference_policy)
    assert window_binding(payload,{})['native_covers']
    payload['duration_s']=5.
    assert not window_binding(payload,{})['native_covers']
    payload['source']['generation_metadata']['prompt']='old input'
    assert not matches_frozen_input(payload,reference_policy)
