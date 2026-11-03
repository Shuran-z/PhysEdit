"""Restore author-selected actual submitted text in a new version; no rerender."""
import copy,hashlib,json
from pathlib import Path
from physedit.core100_critical import ROOT,load,sha
from physedit.core100_rebalanced import load as load_roster
from physedit.compact_prompt import counts
from physedit.prompt_contract import validate_text

OUT=ROOT/'benchmarks/core100_critical_pairs_v5_20261103'
PROTOCOL=ROOT/'benchmarks/core100_critical_protocol_v7_20261103'
VERSION='core100-critical-pairs-v5-20261103'
SOURCE=ROOT/'review/all20_completion_20261101/existing_reuse_audit_20261102'
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v):
    with Path(p).open('x',encoding='utf8')as f:json.dump(v,f,ensure_ascii=False,indent=2)

def build():
    if OUT.exists()or PROTOCOL.exists():raise ValueError('sealed_restoration_exists')
    pointer=ROOT/'catalog/prepared_core100_critical_protocol_v4.json';p=read(pointer)
    data,path=load((pointer.parent/p['registry']).resolve(),p['registry_sha256'])
    parent,manifest,tasks,_=load_roster(ROOT/'catalog/core100_critical_pairs_v4.json')
    policy_path=SOURCE/'resources/core100_final_input_policy.json';policy=read(policy_path)
    assert sha(policy_path)=='547d7045df9493cdb5cfcd0f78996c3049203169dfcdc43a0efd592178832fac'
    metadata_path=SOURCE/'all_existing_generations.jsonl'
    metadata=[json.loads(s)for s in metadata_path.read_text(encoding='utf8').splitlines()]
    inherited_new=set(read(ROOT/'benchmarks/core100_critical_pairs_v3_20261103/MANIFEST.json')['model_generation_and_annotation_pending'])
    inputs={r['clip_id']:r for r in data['input_bindings']};updates={};evidence=[]
    for task in tasks:
        cid=task['clip_id']
        if cid in inherited_new or cid.startswith('T19'):continue
        variants=[];proofs=[]
        for variant in [1,2,3]:
            expected=policy['tasks'][cid]['prompt_variant_sha256'][variant-1]
            rows=[r for r in metadata if r['video_id']==cid and r['annotation']==variant and hashlib.sha256(r['prompt'].encode()).hexdigest()==expected]
            assert rows and len({r['prompt']for r in rows})==1,cid
            text=rows[0]['prompt'];validate_text(text);variants.append(text)
            chosen=next(r for r in rows if r['model']=='Cosmos3-Nano'and r['seed']==0)
            native=task['sample_id'];assert chosen['source_video_id']==native or('__'+native+'__')in chosen['source_video_id']
            proofs.append({k:chosen[k]for k in ['file_name','source_video_id','model','seed','annotation','condition_frame_index']})
        evidence.append(dict(clip_id=cid,prompt_variants_en=variants,prompt_variant_sha256=policy['tasks'][cid]['prompt_variant_sha256'],
            source_generation_records=proofs,camera_replacement_retains_original_physical_text=cid=='T03_C02'))
        if variants!=inputs[cid]['prompt_variants_en']:updates[cid]=variants
    assert len(evidence)==81 and len(updates)==57
    assert all(c not in inherited_new for c in updates)
    OUT.mkdir();(OUT/'evidence').mkdir();PROTOCOL.mkdir()
    write(OUT/'evidence/ACTUAL_SUBMITTED_PROMPTS.json',dict(policy_decision=policy['decision'],
        policy_sha256=sha(policy_path),source_metadata_sha256=sha(metadata_path),
        source_metadata_reference=read(SOURCE/'HF_METADATA_AND_CONDITIONS.json'),cases=evidence))
    restored=copy.deepcopy(tasks)
    for task in restored:
        cid=task['clip_id']
        if cid not in updates:continue
        variants=updates[cid];hashes=[hashlib.sha256(t.encode()).hexdigest()for t in variants]
        task.update(prompt_en=variants[0],prompt_variants_en=variants,prompt_sha256=hashes[0],prompt_variant_sha256=hashes,
            prompt_variant_token_counts=[counts(t)for t in variants],prompt_policy='author-selected-actual-compact-three',
            prompt_binding_restoration='Actual frozen submission text; no new wording authored.')
        if 'prompt_token_counts'in task:task['prompt_token_counts']=task['prompt_variant_token_counts'][0]
    write(OUT/'known_conditions.json',dict(version=VERSION,parent_version=manifest['version'],tasks=restored))
    write(OUT/'replacement_map.json',[])
    write(OUT/'prompt_restoration_map.json',[dict(clip_id=cid,old_recovered_prompt_sha256=inputs[cid]['prompt_variant_sha256'],
        restored_actual_prompt_sha256=[hashlib.sha256(t.encode()).hexdigest()for t in variants],
        reference_video_sha256=inputs[cid]['reference_video_sha256'],condition_sha256=inputs[cid]['condition_sha256'],
        new_generation_already_required=cid=='T03_C02',physical_input_or_event_or_distance_changed=False)for cid,variants in updates.items()])
    write(OUT/'MANIFEST.json',dict(schema='core100-rebalanced-roster-v4',version=VERSION,registered_cases=100,
        retained_reference_inputs=100,prompt_binding_restored=57,retained_full_task_records=43,replaced=0,
        scene_counts={f'T{i:02}':5 for i in range(1,21)},
        parent_manifest=dict(path=(parent/'MANIFEST.json').relative_to(ROOT).as_posix(),sha256=sha(parent/'MANIFEST.json')),
        newly_replaced_generation_and_annotation_pending=[],model_generation_and_annotation_pending=manifest['model_generation_and_annotation_pending'],
        old_outputs_or_labels_modified=False,online_tasks_modified=False,release_status='prepared_actual_submission_binding_restored',
        files={p.relative_to(OUT).as_posix():sha(p)for p in OUT.rglob('*')if p.is_file()}))
    roster_pointer=ROOT/'catalog/core100_critical_pairs_v5.json'
    write(roster_pointer,dict(version=VERSION,release_root='../'+OUT.relative_to(ROOT).as_posix(),manifest='MANIFEST.json',manifest_sha256=sha(OUT/'MANIFEST.json'),status='prepared_not_live'))
    result=copy.deepcopy(data);result.update(version=PROTOCOL.name,roster_release=VERSION,
        roster_pointer=dict(path=roster_pointer.relative_to(ROOT).as_posix(),sha256=sha(roster_pointer)),
        prompt_binding_parent=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path)))
    for b in result['input_bindings']:
        if b['clip_id']in updates:
            b['prompt_variants_en']=updates[b['clip_id']];b['prompt_variant_sha256']=[hashlib.sha256(t.encode()).hexdigest()for t in b['prompt_variants_en']]
    result['submitted_prompt_restoration']=dict(cases=sorted(updates),count=57,unchanged_physical_references=100,
        old_generation_outputs_and_scores_modified=False,required_new_inputs_still=15)
    for f in OUT.rglob('*'):
        if f.is_file():result['source_hashes'][f.relative_to(ROOT).as_posix()]=sha(f)
    raw=json.dumps(result,ensure_ascii=False,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    registry=PROTOCOL/('registry_'+digest[:12]+'.json');registry.write_bytes(raw);load(registry,digest)
    write(ROOT/'catalog/prepared_core100_critical_protocol_v5.json',dict(version=PROTOCOL.name,registry='../'+registry.relative_to(ROOT).as_posix(),
        registry_sha256=digest,status='prepared_not_live',roster_pointer=roster_pointer.relative_to(ROOT).as_posix()))
    print(json.dumps(dict(version=VERSION,restored_prompt_bindings=57,physical_references_changed=0,required_new_inputs=15,registry=str(registry.relative_to(ROOT)),sha256=digest)))

if __name__=='__main__':build()
