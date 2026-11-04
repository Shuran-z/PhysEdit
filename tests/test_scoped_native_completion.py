import copy
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'annotation_site'))
from scoped_native_completion import apply, review_problem
from scoped_native_completion import registered_pair_results


def test_all_registered_context_pairs_visible_and_full_scene_stays_pending():
    refs=[dict(clip_id=f'c{i}',reference_label=i%2,bin='near',horizon_s=7.)for i in range(4)]
    pairs=[dict(pair_id='home',clips=['c0','c1']),dict(pair_id='studio',clips=['c2','c3'])]
    rows=[dict(task_id=f'{i}_{v}',clip_id=f'c{i}',model='m',prompt_variant=v,seed=0,final_correct=0 if i<2 else None,blockers=[])for i in range(4)for v in (1,2,3)]
    c=dict(cohort_id='t19',references=refs,pairs=pairs,outputs=rows,per_model=[dict(model='m')])
    value=registered_pair_results(dict(cohorts=[c]));assert len(value)==2
    assert value[0]['registered']==value[0]['scored']==6 and value[0]['NearAcc']==0 and value[0]['coupled_PairAcc']==0
    assert value[1]['registered']==6 and value[1]['scored']==0 and value[1]['NearAcc']is None and value[1]['coupled_PairAcc']is None
    from formal_critical_cohorts import aggregate
    assert aggregate(rows,refs,pairs,'m')['NearAcc']is None


def data():
    read=lambda p:json.loads(p.read_text(encoding='utf8'))
    registry=read(ROOT/'annotation_site/resources/scoped_native_completion_20261101.json')
    refs=read(ROOT/'annotation_site/resources/core100_formal_cohorts.json')
    tasks=read(ROOT/'review/t05_t19_scoped_completion_20261101/t05_original_tasks.json')
    return registry,refs,tasks


def test_real_reviews_bind_reference_slot_protocol_window_and_native_artifacts():
    r,refs,tasks=data();by={x['clip_id']:x for c in refs['cohorts']for x in c['references']};tb={t['id']:t for t in tasks}
    assert len({x['id']for x in r['reviews']})==27
    assert sum(x['decision']['quality']=='failure'for x in r['reviews'])==18
    intrusion=next(x for x in r['reviews']if x['id']=='core100_t19_v1_T19_C03_p3_s0')
    assert intrusion['decision']['failure_type']=='extra_body'
    assert intrusion['artifacts'][-1]['frames']==list(range(6))
    for x in r['reviews']:assert review_problem(x,by[x['clip_id']],tb.get(x['id']),ROOT/'annotation_site') is None
    x=copy.deepcopy(next(x for x in r['reviews']if x['kind']=='supplemental_generation'));ref=by[x['clip_id']]
    for key,value,problem in [('prompt_sha256','0'*64,'prompt_mismatch'),('reference_video_sha256','0'*64,'reference_video_sha256_mismatch'),('horizon_s',5.,'horizon_s_mismatch'),('end_frame',166,'frame_window_mismatch')]:
        bad=copy.deepcopy(x);bad[key]=value;assert review_problem(bad,ref)==problem


def test_pending_reviews_never_become_negative_truth_or_zero_and_tasks_stay_immutable():
    r,refs,tasks=data();before=copy.deepcopy(tasks)
    needed={x['clip_id']for x in r['reviews']};cohorts=[]
    for c in refs['cohorts']:
        if not any(x['clip_id']in needed for x in c['references']):continue
        c=copy.deepcopy(c);c['outputs']=[dict(task_id=t['id'],clip_id=t['payload']['clip_id'],model='Cosmos3-Nano',seed=0,prompt_variant=t['payload']['prompt_variant'],input_matches=True,historical_input_excluded=False,final_correct=None,blockers=['old_window'])for t in tasks if t['payload']['clip_id']in{x['clip_id']for x in c['references']}];cohorts.append(c)
    result=dict(per_model=['legacy'],admitted_cohort={'unchanged':True},formal_critical_cohorts=dict(cohorts=cohorts,references=[x for c in cohorts for x in c['references']]))
    apply(result,tasks,r,ROOT/'annotation_site');f=result['formal_critical_cohorts'];rows={x['task_id']:x for x in f['outputs']}
    assert len(rows)==27 and sum(x['final_correct']is not None for x in rows.values())==18
    assert sum(x['final_correct']is None for x in rows.values())==9
    assert all(rows[x['id']]['final_correct']is None for x in r['reviews']if x['decision']['quality']!='failure')
    assert result['per_model']==['legacy'] and result['admitted_cohort']=={'unchanged':True} and tasks==before
    snapshot=copy.deepcopy(result);apply(result,tasks,r,ROOT/'annotation_site');assert result==snapshot


def test_artifact_and_original_label_identity_cannot_be_bypassed(tmp_path):
    r,refs,tasks=data();x=r['reviews'][0];ref=next(x for c in refs['cohorts']for x in c['references']if x['clip_id']==r['reviews'][0]['clip_id']);task=next(t for t in tasks if t['id']==x['id'])
    assert review_problem(x,ref,task,tmp_path)=='review_artifact_unavailable'
    bad=copy.deepcopy(task);bad['payload']['protocol_sha256']='different'
    assert review_problem(x,ref,bad)=='old_task_protocol_mismatch'
