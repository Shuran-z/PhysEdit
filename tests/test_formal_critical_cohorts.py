import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'annotation_site'))
from formal_critical_cohorts import aggregate, replacement_observation


def test_registered_authorized_near_and_pair_counts():
    r=json.loads((ROOT/'annotation_site/resources/core100_formal_cohorts.json').read_text(encoding='utf8'))
    assert r['summary']['formally_registered_reference_cases']==81
    assert r['summary']['formally_registered_near_points']==10
    assert r['summary']['formally_registered_pairs']==3
    assert r['summary']['newly_admitted_reference_cases']==74
    new={x['clip_id']:x for c in r['cohorts']for x in c['references']}
    assert all(new[cid]['target_event']=='passed_channel'for cid in ('T14_C01','T14_C02'))
    assert all(new[cid]['horizon_s']==205/30 for cid in ('T05_C02','T05_C04','T05_C05'))


def test_unmatched_seeds_never_form_a_cartesian_pair():
    refs=[dict(clip_id='a',reference_label=0,bin='near'),dict(clip_id='b',reference_label=1,bin='near')]
    rows=[dict(clip_id='a',model='m',seed=0,prompt_variant=1,final_correct=1),
          dict(clip_id='b',model='m',seed=1,prompt_variant=1,final_correct=1)]
    value=aggregate(rows,refs,[dict(clips=['a','b'])],'m')
    assert value['NearAcc']==1 and value['coupled_PairAcc'] is None
    assert value['independent_PairAcc'] is None and value['known_pair_slots']==0


def test_historical_outputs_are_not_new_version_denominator():
    refs=[dict(clip_id='a',reference_label=0,bin='near'),dict(clip_id='b',reference_label=1,bin='near')]
    rows=[dict(clip_id='a',model='m',seed=0,prompt_variant=1,final_correct=None,historical_input_excluded=True)]
    value=aggregate(rows,refs,[dict(clips=['a','b'])],'m')
    assert value['status']=='awaiting_matching_generation'
    assert value['matching_registered']==0 and value['historical_excluded']==1
    assert value['NearAcc'] is None and value['coupled_PairAcc'] is None


def test_matching_seeds_pair_both_correct_and_pending_stays_unknown():
    refs=[dict(clip_id='a',reference_label=0,bin='near'),dict(clip_id='b',reference_label=1,bin='near')]
    rows=[dict(clip_id='a',model='m',seed=0,prompt_variant=1,final_correct=1),
          dict(clip_id='b',model='m',seed=0,prompt_variant=1,final_correct=0)]
    before=copy.deepcopy(rows);value=aggregate(rows,refs,[dict(clips=['a','b'])],'m')
    assert value['NearAcc']==.5 and value['coupled_PairAcc']==0 and rows==before
    rows[1]['final_correct']=None
    value=aggregate(rows,refs,[dict(clips=['a','b'])],'m')
    assert value['NearAcc'] is None and value['coupled_PairAcc'] is None


def test_replacement_requires_exact_reference_prompt_window_and_human_identity(monkeypatch):
    import formal_critical_cohorts as module
    registry=json.loads((ROOT/'annotation_site/resources/core100_formal_cohorts.json').read_text(encoding='utf8'))
    ref=registry['cohorts'][1]['references'][1]
    p=dict(clip_id=ref['clip_id'],model='m',seed=0,prompt_variant=1,video_sha256='v',protocol_sha256='p',
        reference_release_version=ref['reference_release_version'],reference_video_sha256=ref['reference_video_sha256'],
        condition_sha256=ref['condition_sha256'],duration_s=ref['horizon_s'],window_s=ref['horizon_s'],fps=30,frames=210,
        source={'generation_metadata':{'prompt':ref['prompt_variants_en'][0],'condition_frame_index':0}},
        protocol={'events':{ref['target_event']:{}}},remote_media={'size':123},
        machine={'media_verified':{'sha256':'v','frames':210,'fps':30,'size':123}})
    human=dict(video_sha256='v',protocol_sha256='p',quality={'status':'pass'},events={ref['target_event']:{'label':'yes'}})
    monkeypatch.setattr(module,'final_annotation',lambda task:human)
    task=dict(id='new',payload=p)
    assert replacement_observation(task,ref)['final_correct']==1
    p['window_s']=5
    assert replacement_observation(task,ref)['final_correct'] is None
    p['window_s']=ref['horizon_s'];p['reference_video_sha256']='old'
    value=replacement_observation(task,ref)
    assert value['historical_input_excluded'] and value['final_correct'] is None


def test_one_sided_near_is_reported_without_manufacturing_balanced_score_or_pair():
    refs=[dict(clip_id='a',reference_label=1,bin='near')]
    rows=[dict(clip_id='a',model='m',seed=0,prompt_variant=1,final_correct=1)]
    value=aggregate(rows,refs,[],'m')
    assert value['NearAcc'] is None and value['coupled_PairAcc'] is None
    assert value['OneSidedNearTargetAccuracy']==1 and value['TargetAccuracy']==1


def test_t13_clock_binding_is_original_24fps_five_second_prefix():
    r=json.loads((ROOT/'annotation_site/resources/core100_formal_cohorts.json').read_text(encoding='utf8'))
    refs=[x for c in r['cohorts']for x in c['references']if x['clip_id'].startswith('T13')]
    assert len(refs)==5
    assert all(x['end_frame_index']==124 and x['condition_frame_index']==4 and x['reference_fps']==24 for x in refs)
    assert all((x['end_frame_index']-x['condition_frame_index'])/x['reference_fps']==x['horizon_s']==5 for x in refs)


def test_remaining74_keeps_old_reference_events_and_original_scopes():
    import hashlib
    work=ROOT/'review/core100_remaining74_admission_20261101'
    old=json.loads((work/'live_before/resources/core100_formal_cohorts.json').read_text(encoding='utf8'))
    current=json.loads((ROOT/'annotation_site/resources/core100_formal_cohorts.json').read_text(encoding='utf8'))
    by={c['cohort_id']:c for c in current['cohorts']}
    assert all(by[c['cohort_id']]==c for c in old['cohorts'])
    new=[r for c in current['cohorts']for r in c['references']if r['clip_id']not in {r['clip_id']for c in old['cohorts']for r in c['references']}]
    assert len(new)==55
    assert not any(r['clip_id'].startswith('T11')for r in new)
    assert next(r for r in new if r['clip_id']=='T15_C04')['reference_label']==0
    assert all(r['distance_admitted'] is False for r in new if not r['clip_id'].startswith(('T01','T04','T08','T16','T17')))
    assert current['summary']['formally_registered_interval_reference_cases']==40
    for r in new:
        proof=r['original_state_readback_evidence']
        assert hashlib.sha256((ROOT/proof['file']).read_bytes()).hexdigest()==proof['sha256']
        for key in ('artifact','sequence_artifact'):
            d=r['observability_evidence'];assert hashlib.sha256((ROOT/d[key]).read_bytes()).hexdigest()==d[key+'_sha256']
