"""Replay five existing videos, preserving controls separately from model scores."""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from physedit.boundary import read_rows, write_rows, write_json, digest, score
from physedit.boundary_screening import prepare

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'review/t15_qwen_judge_20261015'
F=ROOT/'review/t15_followup_20261014'
OUT=ROOT/'review/t15_screening_replay_20261016'
EVENT='laptop_falls_to_floor'

def main():
    OUT.mkdir(exist_ok=False)
    roster=json.loads((P/'answer_key.json').read_text())
    manifest={r['sample_id']:r for r in read_rows(P/'inputs.jsonl')}
    qwen={r['sample_id']:r for r in read_rows(P/'corrected/results.jsonl')}
    keys={r['sample_id']:r for r in read_rows(F/'run06/answers.jsonl')}
    keys.update({r['sample_id']:r for r in read_rows(F/'answers_new_seed.jsonl')})
    anns={r['sample_id']:r for name in ('events_run06.jsonl','events_run09.jsonl') for r in read_rows(F/name)}
    summary={}
    for name,ids,chain in [('all_five_fall_diagnostic',list(manifest),False),
                           ('reference_controls',['case02','case04'],False),
                           ('generated_full_chain',['case01','case03','case05'],True)]:
        base=OUT/name;base.mkdir()
        inputs=[];answers=[];observed=[];annotations=[];reviews=[]
        for item in roster:
            sid=item['sample_id']
            if sid not in ids:continue
            m=manifest[sid];video=P/m['video'];assert digest(video)==m['sha256']
            isgen=item['source_type']=='generated'
            if isgen:
                key=copy.deepcopy(keys[item['source_id']]);key['pair_ids']=[]
                ann=copy.deepcopy(anns[item['source_id']])
            else:
                key=dict(scene_id='T15',source_group_id='reference_controls',family_id='controls',
                         point_id=sid,theta=2.832 if sid=='case02' else 1.728,target_event=EVENT,
                         events={EVENT:item['prior_fall']},pair_ids=[],required_order=[],gravity=9.81,
                         inversion=dict(status='pending_reference_validation' if sid=='case02' else 'not_applicable',
                                        reason='no_frozen_inversion_registration' if sid=='case02' else 'reference_no_fall'))
                ann=dict(method='qwen_existing_result',events={EVENT:qwen[sid]['judgement']['fall']},
                         event_times_s={},evidence=qwen[sid]['judgement']['reason'])
            key['sample_id']=sid;key['source_type']=item['source_type']
            if not chain:
                key['events']={EVENT:key['events'][EVENT]};key['required_order']=[]
                ann['events']={EVENT:ann['events'].get(EVENT)}
            if chain and sid in ('case01','case03'):
                key['pair_ids']=['exploratory_reassembled_A1_A2']
                key['pairing_mode']='independent'
            ann.update(sample_id=sid,video_sha256=m['sha256'])
            annotations.append(ann);answers.append(key)
            inputs.append(dict(sample_id=sid,seed=1 if sid=='case01' else 0,evaluation_duration_s=6,
                               source_start_frame=m['start_frame'],source_type=item['source_type']))
            observed.append(dict(sample_id=sid,status='ok',video=str(video),video_sha256=m['sha256']))
            if isgen:
                failure=sid in ('case01','case05')
                reviews.append(dict(sample_id=sid,video_sha256=m['sha256'],
                    status='confirmed_failure' if failure else 'pass',reviewer='assistant_provisional_NOT_independent_human',
                    evidence=ann['evidence'],blocked_events=list(key['events']) if failure else [],block_inversion=failure))
        write_rows(base/'inputs.jsonl',inputs);write_rows(base/'answers.jsonl',answers)
        write_rows(base/'observed_rows.jsonl',observed);write_rows(base/'events.jsonl',annotations)
        write_rows(base/'reviews.jsonl',reviews);write_rows(base/'qwen.jsonl',[qwen[s] for s in ids])
        write_json(base/'registered.json',dict(model='LTX_existing_outputs' if chain else name,
                    imported_existing_media=True,retrospective_development_diagnostic=True,
                    code_sha256=digest(ROOT/'physedit/boundary.py'),screening_code_sha256=digest(ROOT/'physedit/boundary_screening.py')))
        write_json(base/'snapshot_hashes.json',{n:digest(base/n) for n in ('inputs.jsonl','answers.jsonl','registered.json')})
        stages={}
        for stage,review in [('vlm_only',None),('assistant_review',base/'reviews.jsonl')]:
            prepare(base,base/'qwen.jsonl',review,base/stage)
            result=score(base,base/'events.jsonl',screening=base/stage/'screening.jsonl')
            write_json(base/(stage+'_score.json'),result)
            stages[stage]={k:v for k,v in result.items() if k not in ('rows','families')}
            assert result['registered']==len(ids)==result['scored_rows']
        summary[name]=stages
    write_json(OUT/'summary.json',summary)
    write_json(OUT/'provenance.json',dict(qwen_results_sha256=digest(P/'corrected/results.jsonl'),
        script_sha256=digest(__file__),review_basis='existing assistant dense reviews and renewed contact-sheet inspection; NOT human adjudication',
        inversion='No fit performed; applicability inherited from prior registration',
        pairs='A1_s1 and A2_s0 reassembled retrospectively for diagnostic only; not a preregistered experiment',
        media_check='SHA256 matches prior fully decoded videos; no new generation or VLM inference'))
    print(json.dumps(summary,ensure_ascii=True,indent=2))

if __name__=='__main__':main()
