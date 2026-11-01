"""Join immutable Core100 inputs, native event references and distance evidence.

Candidate distance bins never grant reference or generated-output admission.
No threshold is learned from generated videos; no missing label becomes zero.
"""
import collections
import csv
import gzip
import hashlib
import io
import itertools
import json
from pathlib import Path

ROOT=Path('review/core100_admission_20261023')
RES=Path('annotation_site/resources')
REVISION='f23ee3577952ec1e5357c8a729bfc4daa5c7272d'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(s):return hashlib.sha256(s.encode()).hexdigest()


def aliases(scene,event):
    exact={
      ('T16','contact_t16_folder__t16_downstream_box_occurred'):'folder_downstream_contact',
      ('T16','contact_t16_downstream_box__t16_folder_occurred'):'folder_downstream_contact',
      ('T17','contact_t17_can__t17_tissue_box_occurred'):'can_tissue_box_contact'}
    return exact.get((scene,event),event)


def build():
    conditions=json.loads((ROOT/'v6_known_conditions.json').read_text(encoding='utf-8'))
    by={t['clip_id']:t for t in conditions['tasks']}
    assert len(by)==100
    cat=json.loads((RES/'event_contracts.json').read_text(encoding='utf-8'))['clips']
    snapshot=json.loads(gzip.decompress((ROOT/'site_tasks_snapshot.json.gz').read_bytes()))
    candidates=json.loads((ROOT/'exact_id_distance_candidates.json').read_text(encoding='utf-8'))
    ids={v['sample_id']:clip for clip,v in by.items()}
    additional_sources={}
    # The combined historical ledger omits some newer verified registries.
    # Read their declared bracket/span directly; never infer a span or alias
    # a different engine merely because the sample name is shared.
    base=Path('review/scene_family_completion_20261018')
    for name in ['t02_published_scoring_registry.json','t07_original_search_distance_registry.json','isaac_verified_numerical_registry.json']:
        path=base/name
        if not path.exists():continue
        additional_sources[str(path)]=sha(path)
        for source in json.loads(path.read_text(encoding='utf-8')):
            sid=source.get('reference_sample_id',source.get('sample_id'));b=source.get('boundary',{})
            if sid not in ids or source.get('engine')=='isaac' or name.startswith('isaac') or not b.get('bracket') or not b.get('normalization_span'):continue
            candidates.append({**source,'clip_id':ids[sid],'original_boundary_interval':b['bracket'],'normalization_span':b['normalization_span'],'distance_bin':source.get('distance',source.get('pipeline_distance',{})).get('bin'),'ledger_source':str(path),'reference_category':'verified_registry','distance_record_id':digest(json.dumps(source,sort_keys=True))})
    old_recovery=json.loads((RES/'remaining50_recovery.json').read_text(encoding='utf-8'))
    recovery={r['clip_id']:r for r in old_recovery['rows']}
    pair_configs=json.loads((ROOT/'pair_original_configs.json').read_text(encoding='utf-8'))
    grouped=collections.defaultdict(list)
    for t in snapshot:grouped[t['payload']['clip_id']].append(t)
    prompt_rows=[];point_rows=[];near=[];all_distances=[]
    for clip,cond in by.items():
        tasks=grouped[clip];assert len(tasks)==36
        bad=0;human=0
        for task in tasks:
            p=task['payload'];gm=p['source']['generation_metadata'];variant=int(p['prompt_variant'])
            expected=cond['prompt_variants_en'][variant-1];actual=gm['prompt']
            assert digest(expected)==cond['prompt_variant_sha256'][variant-1]
            match=actual==expected;bad+=not match
            complete=any(a['stage'] in ('primary','adjudication') and a.get('submitted') for a in task['annotations']);human+=complete
            prompt_rows.append(dict(task_id=task['id'],clip_id=clip,model=p['model'],seed=p['seed'],prompt_variant=variant,video_sha256=p['video_sha256'],submitted_prompt_sha256=digest(actual),expected_v6_prompt_sha256=digest(expected),v6_exact_match=match,native_prompt_truncation=gm.get('native_prompt_truncation'),human_submitted=complete))
        ds=[];rejected=[]
        for r in candidates:
            if r['clip_id']!=clip:continue
            event=aliases(clip[:3],r.get('target_event'))
            if r.get('reference_category') in ('rendering_star','diagnostic_proxy') or r.get('publication_status')=='retired_T19_render':
                rejected.append({'record_id':r.get('distance_record_id'),'reason':r.get('reference_category') or r.get('publication_status')});continue
            if event not in cat[clip].get('formal_score_event_ids',[]):
                rejected.append({'record_id':r.get('distance_record_id'),'reason':'different_event_contract','target':r.get('target_event')});continue
            bracket=r.get('original_boundary_interval');span=r.get('normalization_span');theta=r.get('theta')
            if not bracket or not isinstance(span,(int,float)) or span<=0 or not isinstance(theta,(int,float)):continue
            a,b=bracket
            lo=max(a-theta,theta-b,0)/span;hi=max(abs(theta-a),abs(theta-b))/span
            bucket='near' if hi<=.05 else 'mid' if lo>.05 and hi<=.15 else 'far' if lo>.15 else None
            if r.get('distance_bin')!=bucket:raise ValueError('distance bin disagrees with frozen protocol: '+clip)
            entry={k:r.get(k) for k in ['clip_id','sample_id','revision','family_id','theta','parameter_unit','reference_state_sha256','reference_label','fixed_context_sha256','original_boundary_interval','normalization_domain','normalization_span','original_reference_kind','refinement_source_seed','simulation_seed','scope','ledger_source','distance_record_id']}
            entry.update(canonical_event=event,source_event=r['target_event'],normalized_distance_interval=[lo,hi],bin=bucket,reference_is_replay=r.get('reference_origin')=='supplemental_replay_not_original_annotation',registered_boundary_status=r.get('boundary',{}).get('status','observed_or_conditional_interval'),numerical_reference_verified=r.get('numerical_reference_verified'),boundary_scope='retain original registered numerical status; this audit grants no new uniqueness or RGB admission',formal_admitted=False)
            ds.append(entry)
        # Opposite object-pair spelling is an exact semantic alias, not a second sample.
        unique={}
        for r in ds:
            key=(r['canonical_event'],r['family_id'],tuple(r['original_boundary_interval']),r['reference_state_sha256'])
            unique.setdefault(key,r)
        ds=list(unique.values());all_distances.extend(ds)
        near.extend(r for r in ds if r['bin']=='near')
        blockers=[]
        if not cat[clip].get('formal_score_event_ids'):blockers.append('original_critical_target_missing')
        if not ds:blockers.append('no_same_event_normalized_boundary')
        if not any(r['bin']=='near' for r in ds):blockers.append('no_certified_near_bin_for_current_target')
        blockers.extend(['reference_RGB_observability_not_admitted','reference_to_generated_window_not_frozen'])
        if bad:blockers.append('site_outputs_not_exact_frozen_v6_inputs')
        if human<len(tasks):blockers.append('human_review_pending')
        if clip[:3]=='T19':blockers.append('reference_render_retired_by_author')
        point_rows.append(dict(clip_id=clip,source_sample_id=cond['sample_id'],reference=cond['reference'],source_header_provenance=cond.get('header_provenance'),reference_configuration_status=cond['configuration_status'],reference_clock=cond['clock'],original_contract_ready=bool(cat[clip].get('formal_score_event_ids')),registered_outputs=36,v6_exact_outputs=36-bad,human_submitted_outputs=human,numerical_distance_records=ds,rejected_evidence=rejected,nearacc_eligible=False,pairacc_eligible=False,blockers=blockers,source_recovery=recovery.get(clip)))
    pairs=[]
    for left,right in itertools.combinations(near,2):
        if left['clip_id']==right['clip_id'] or left['reference_label']==right['reference_label']:continue
        if not left.get('fixed_context_sha256') or any(left.get(k)!=right.get(k) for k in ('family_id','canonical_event','fixed_context_sha256','original_boundary_interval','normalization_span','revision')):continue
        clips=sorted([left['clip_id'],right['clip_id']]);pair_id='candidate_'+clips[0]+'__'+clips[1]+'__'+left['canonical_event']
        # With uncertain boundaries, the whole range must meet the frozen 0.02
        # symmetry tolerance; using bracket midpoints would invent precision.
        l0,l1=left['normalized_distance_interval'];r0,r1=right['normalized_distance_interval'];worst=max(abs(l0-r1),abs(l1-r0))
        seeds=[pair_configs.get(c,{}).get('config',{}).get('seed') for c in clips]
        blockers=['published_scan_interval_not_verified_fixed_seed_boundary','reference_RGB_observability_not_admitted','common_observation_window_not_registered','site_outputs_not_exact_frozen_v6_inputs','human_review_pending']
        if len(set(seeds))!=1:blockers.append('published_reference_seeds_differ')
        if worst>.02:blockers.append('pair_distance_symmetry_uncertain_at_frozen_0p02_tolerance')
        pairs.append(dict(pair_id=pair_id,clips=clips,target_event=left['canonical_event'],labels=[left['reference_label'],right['reference_label']],physical_family=left['family_id'],fixed_context_sha256=left['fixed_context_sha256'],boundary_interval=left['original_boundary_interval'],normalization_span=left['normalization_span'],normalized_distance_intervals=[left['normalized_distance_interval'],right['normalized_distance_interval']],worst_case_normalized_distance_asymmetry=worst,pair_tolerance=.02,source_seeds=seeds,status='candidate_not_admitted',blockers=blockers))
    original=json.loads(gzip.decompress(Path('review/original_contract_audit_20261023/remaining_sources/exact_original_states.json.gz').read_bytes()))
    window_rows=[]
    for pair in pairs:
        actors=('t16_folder','t16_downstream_box') if pair['clips'][0][:3]=='T16' else ('t17_can','t17_tissue_box')
        for model in sorted({p['model'] for p in prompt_rows}):
            outcomes=[];times=[];durations=[];variant_sets=[]
            for clip in pair['clips']:
                tasks=[t['payload'] for t in grouped[clip] if t['payload']['model']==model]
                windows={t['window_s'] for t in tasks};assert len(windows)==1
                window=next(iter(windows));durations.append(window);variant_sets.append({t['prompt_variant'] for t in tasks})
                offsets={t['source']['generation_metadata']['condition_frame_index'] for t in tasks};assert offsets=={4}
                st=original[clip]['data'];fps=st['time_diagnostic']['video_fps'];end=(len(st['frames'])-1-4)/fps
                hits=[f['frame_index'] for f in st['frames'] for c in f.get('contacts',[]) if {c.get('entity_a'),c.get('entity_b')}==set(actors)]
                first=(min(hits)-4)/fps if hits else None;times.append(first)
                outcomes.append(1 if first is not None and first<=window else 0 if window<=end else None)
            window_rows.append(dict(pair_id=pair['pair_id'],model=model,windows_s=durations,reference_first_event_from_condition_s=times,reference_labels_in_existing_windows=outcomes,opposite_labels_preserved=all(v is not None for v in outcomes) and len(set(outcomes))==2,common_prompt_variants=sorted(variant_sets[0]&variant_sets[1]),status='window_diagnostic_only; boundary must be rebound to the same declared horizon'))
    # These are audit result values, not a model score computed with pending=0.
    per_model=[]
    for model in sorted({p['model'] for p in prompt_rows}):
        own=[p for p in prompt_rows if p['model']==model]
        per_model.append(dict(model=model,registered=len(own),v6_exact_inputs=sum(p['v6_exact_match'] for p in own),human_submitted=sum(p['human_submitted'] for p in own),NearAcc=None,PairAcc=None,eligible_near_outputs=0,eligible_pairs=0,status='not_admitted',reason='frozen_v6_input_and_reference_window_admission_and_human_review_pending'))
    summary=dict(core_cases=100,source_definition_cases=sum(p['original_contract_ready'] for p in point_rows),source_definition_missing=[p['clip_id'] for p in point_rows if not p['original_contract_ready']],cases_with_same_event_numerical_distance=len({r['clip_id'] for r in all_distances}),candidate_near_cases=sorted({r['clip_id'] for r in near}),candidate_near_events=len(near),candidate_pairs=len(pairs),formal_near_cases=0,formal_pairs=0,registered_outputs=len(prompt_rows),exact_v6_outputs=sum(p['v6_exact_match'] for p in prompt_rows),human_submitted_outputs=sum(p['human_submitted'] for p in prompt_rows),NearAcc=None,PairAcc=None,T08_pinned_video_state_bindings=sum(bool(r.get('published_reference_binding')) for r in recovery.values()))
    result=dict(schema='core100-source-admission-audit-v1',input_release=dict(repository='phy2/phydataset',revision=REVISION,known_conditions_sha256=sha(ROOT/'v6_known_conditions.json')),frozen_policy=dict(near_upper=.05,mid_upper=.15,pair_distance_tolerance=.02,scope='existing protocol constants for candidate audit; not a new final admission',source='docs/critical_boundary/CRITICAL_BOUNDARY_PROTOCOL.md',source_sha256=sha('docs/critical_boundary/CRITICAL_BOUNDARY_PROTOCOL.md')),summary=summary,points=point_rows,candidate_pairs=pairs,model_window_diagnostics=window_rows,per_model=per_model,additional_registry_hashes=additional_sources,source_hashes={n:sha(ROOT/n) for n in ['site_tasks_snapshot.json.gz','exact_id_distance_candidates.json','pair_original_configs.json','t08_pinned_paths_info.json','remaining15_original_release_evidence.json']})
    for dest in [ROOT,RES]:
        (dest/'core100_admission.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        s=io.StringIO(newline='');w=csv.writer(s);w.writerow(['clip_id','original_contract_ready','numerical_events','near_candidate_events','v6_exact_outputs','registered_outputs','human_submitted_outputs','NearAcc_eligible','PairAcc_eligible','blockers'])
        for p in point_rows:w.writerow([p['clip_id'],p['original_contract_ready'],';'.join(sorted({r['canonical_event'] for r in p['numerical_distance_records']})),';'.join(sorted({r['canonical_event'] for r in p['numerical_distance_records'] if r['bin']=='near'})),p['v6_exact_outputs'],36,p['human_submitted_outputs'],False,False,';'.join(p['blockers'])])
        (dest/'core100_admission.csv').write_text('\ufeff'+s.getvalue(),encoding='utf-8')
        s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=list(prompt_rows[0]));w.writeheader();w.writerows(prompt_rows);(dest/'v6_input_bindings.csv').write_text('\ufeff'+s.getvalue(),encoding='utf-8')
    # Update the existing admin readiness surface without upgrading candidate
    # evidence to an admitted reference or turning input gaps into event failure.
    readiness=json.loads((RES/'core100_readiness.json').read_text(encoding='utf-8'))
    point_map={p['clip_id']:p for p in point_rows}
    for gap in readiness['rows']:
        p=point_map[gap['clip_id']]
        gap['admission_snapshot']={k:p[k] for k in ['v6_exact_outputs','registered_outputs','human_submitted_outputs','blockers']}
        gap['candidate_peer_ids']=sorted({other for pair in pairs if gap['clip_id'] in pair['clips'] for other in pair['clips'] if other!=gap['clip_id']})
        gap['registered_pair_peer_ids']=[]
        gap['nearacc_eligible']=False;gap['pairacc_eligible']=False
        evidence=[]
        for r in p['numerical_distance_records']:
            checks={'reference_admitted':False,'version_or_media_bound':r.get('revision')==p['reference'].get('source_revision'),'reference_state_bound':bool(r.get('reference_state_sha256')),'binary_target_label':r.get('reference_label') in (0,1),'target_contract':True,'boundary_verified':r['registered_boundary_status']=='verified','normalization_registered':True,'near_bin':r['bin']=='near'}
            evidence.append(dict(registry='core100_admission.json',target_event=r['canonical_event'],reference_label=r['reference_label'],family_id=r['family_id'],fixed_context_sha256=r['fixed_context_sha256'],theta=r['theta'],boundary_status=r['registered_boundary_status'],distance={'bin':r['bin'],'normalized_absolute_interval':r['normalized_distance_interval']},checks=checks,reference_state_sha256=r['reference_state_sha256'],registered_blockers=p['blockers'],pair_ids=[]))
        if evidence:
            gap['all_evidence']=[e for e in gap.get('all_evidence',[]) if e.get('registry')!='core100_admission.json']+evidence
            gap['evidence_match_count']=len(gap['all_evidence'])
            gap['best_evidence']=evidence[0]
        gap['near_blockers']=list(dict.fromkeys(gap['near_blockers']+p['blockers']))
        gap['pair_blockers']=list(dict.fromkeys(gap['pair_blockers']+['no_frozen_cross_boundary_pair_registration']+p['blockers']))
    readiness['summary'].update(exact_reference_matches=sum(bool(r.get('best_evidence')) for r in readiness['rows']),numerical_candidate_cases=summary['cases_with_same_event_numerical_distance'],near_candidate_cases=len(summary['candidate_near_cases']),pair_candidate_count=len(pairs),v6_exact_outputs=summary['exact_v6_outputs'],human_submitted_outputs=summary['human_submitted_outputs'])
    readiness['reason_guide'].update(original_critical_target_missing='缺对应原版本的临界目标提取合同',no_same_event_normalized_boundary='尚无同一事件的归一化边界登记',no_certified_near_bin_for_current_target='当前目标尚无可确定的Near分层',reference_RGB_observability_not_admitted='参考画面可观察性尚未准入',reference_to_generated_window_not_frozen='参考与生成观察窗尚未绑定',site_outputs_not_exact_frozen_v6_inputs='当前输出提交文本不属于冻结v6',human_review_pending='人工复核未完成',reference_render_retired_by_author='作者已停用此旧参考渲染')
    (RES/'core100_readiness.json').write_text(json.dumps(readiness,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False));print(json.dumps(pairs,ensure_ascii=False))


if __name__=='__main__':build()
