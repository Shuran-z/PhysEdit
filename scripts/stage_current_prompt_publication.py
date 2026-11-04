"""Independent source/value verification while rebuilding all public consumer views."""
from pathlib import Path
import collections,functools,gzip,hashlib,itertools,json,shutil,sys
import pyarrow as pa
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import full_prompt_config_audit as audit
from scripts.preflight_current_prompt_upload import Configs,CURRENT,BASE
from scripts.build_current_prompt_publication import current_context,resolve_current,covered_by_controller
from scripts.repair_and_verify_all_prompts import source_controls,pieces,NUM,fact_patterns,match_fact,merge_friction,primary_clause,supplemental_clause,texts_hash
from scripts.repair_prompt_fact_units import typed_unit
from physedit.compact_prompt import counts,MODEL_BUDGETS
from physedit.prompt_contract import parameter_facts_sha
READY=BASE/'ready';STAGE=BASE/'stage';D=STAGE/'releases/physedit'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def jsonrows(p):
    with gzip.open(p,'rt',encoding='utf8') as f:yield from map(json.loads,f)
def split(r):
    if r['split']=='train_final':return 'train'
    if r['split']=='ood_holdout':return 'ood1_holdout' if r['scene'] in ['T03','T20'] else 'ood2_holdout'
    return 'protected'

def main():
    report=json.loads((READY/'COMPACTION_REPORT.json').read_text());assert report.get('needs_review',0)==0 and report['verified']==72000
    cfg=Configs();stats=collections.Counter();pool={};seen=set();media=set();train_ids=set();issues=[];index={};groups={};buffers=collections.defaultdict(list)
    schema=pq.read_schema(CURRENT/'videos_train.parquet');parquet={};gz={}
    for name in ['catalog/videos.jsonl.gz','catalog/train_final.jsonl.gz','prompts/video_prompt_bindings.jsonl.gz']:
        p=D/name;p.parent.mkdir(parents=True,exist_ok=True);gz[name]=gzip.open(p,'wt',encoding='utf8',compresslevel=1)
    for s in ['train','ood1_holdout','ood2_holdout','protected']:
        p=D/f'catalog/parquet/videos_{s}.parquet';p.parent.mkdir(parents=True,exist_ok=True);parquet[s]=pq.ParquetWriter(p,schema,compression='zstd')
    try:
        for old,row in itertools.zip_longest(jsonrows(CURRENT/'videos.jsonl.gz'),jsonrows(READY/'videos.jsonl.gz')):
            assert old and row;vid=row['canonical_video_id'];assert vid not in seen;seen.add(vid)
            for k in ['canonical_video_id','sha256','download','split','source_group_id','quality_admission_status','current_render','physical_qa']:
                assert old.get(k)==row.get(k),(vid,k)
            d=row.get('config_download') or {}
            if d:raw,_=cfg.get(d['path'],d['member'],d['sha256']);stats['config_hash_verified_rows']+=1
            else:raw=audit.HEADERS[vid]['header'];stats['original_metadata_verified_rows']+=1
            ctx=current_context(row,raw)
            if row['engine']=='genesis' and row['scene']=='T19' and row['sha256'] not in audit.T19:
                # The original trajectory source remains bound through encoding lineage.
                previous=(row.get('current_render') or {}).get('encoding_compatibility',{}).get('source_sha256')
                if previous in audit.T19:audit.T19[row['sha256']]=audit.T19[previous]
            for f in row['parameter_facts']:
                value,path=resolve_current(f[0],f[-2],raw,ctx,row)
                if value is None or not audit.equal(value,f[-2]):issues.append({'video_id':vid,'kind':'parameter','key':f[0],'expected':value,'actual':f[-2],'source':path})
                assert typed_unit(f[0],f[-2],f[-1])==f[-1]
                stats['numeric_parameter_checks']+=1
            n,c,clock=source_controls(row,raw,ctx);controls=n['source_control_clauses']
            if controls!=row['prompt_revision']['source_control_clauses']:issues.append({'video_id':vid,'kind':'controller_mismatch'})
            pats=fact_patterns(row['parameter_facts']);texts=row['prompt_variants_en'];assert len(texts)==len(set(texts))==3
            hashes=texts_hash(texts);assert hashes==row['prompt_variant_sha256'] and hashes[0]==row['prompt_sha256']
            assert row['prompt_en']==texts[0] and parameter_facts_sha(row['parameter_facts'])==row['parameter_facts_sha256']
            for i,text in enumerate(texts):
                assert counts(text)==row['prompt_variant_token_counts'][i]
                assert all(counts(text)[m]<=cap for m,cap in MODEL_BUDGETS.items())
                body=text
                for cl in controls:assert cl in body;body=body.replace(cl,' ');stats['controller_clause_checks']+=1
                for cl in pieces(body):
                    if not NUM.search(cl):continue
                    match=match_fact(cl,pats)
                    if match:
                        if not audit.equal(match[1],match[2]):issues.append({'video_id':vid,'kind':'literal_value','clause':cl,'key':match[0]})
                    elif not merge_friction(cl,row['parameter_facts']) and not primary_clause(cl,row,raw) and not supplemental_clause(cl,row,c,ctx):issues.append({'video_id':vid,'kind':'unknown_numeric_clause','clause':cl})
                    stats['numeric_body_clause_checks']+=1
                assert hashes[i] not in pool or pool[hashes[i]]==text;pool[hashes[i]]=text
            facts={f[0]:f[-2] for f in row['parameter_facts']}
            for key in row['full_numeric_audit'].get('facts_explicitly_represented_by_controller',[]):
                assert covered_by_controller(key,facts[key],ctx,n.get('control_keys',[])),(vid,key,'invalid_controller_deduplication')
            proof={'binding_method':'current_inventory_config_metadata_numeric_audit','binding_verified':True,'video_sha256':row['sha256'],
                   'source_config_sha256':d.get('sha256'),'source_metadata_sha256':None if d else audit.HEADERS[vid]['metadata_artifact_sha256'],
                   'parameter_facts_sha256':row['parameter_facts_sha256'],'prompt_sha256':hashes,
                   'media_hash_origin':'existing current inventory, preserved without modification','base_revision':'096d3d1fe9d78c57d2fe80de3636cbac04950e65'}
            previous=row.get('prompt_binding_evidence')
            if previous and previous!=proof:row['superseded_prompt_binding_evidence']=previous
            row['prompt_binding_evidence']=proof;row['prompt_binding_method']=proof['binding_method']
            # Compact active validation metadata; immutable audit logs retain detail.
            row['prompt_revision']={k:v for k,v in row['prompt_revision'].items() if k not in ['changes','runtime_binding']}
            row['full_numeric_audit']['status']='verified';row['full_numeric_audit']['issues']=[]
            encoded=json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n';gz['catalog/videos.jsonl.gz'].write(encoded)
            if row['split']=='train_final':gz['catalog/train_final.jsonl.gz'].write(encoded);train_ids.add(vid)
            group=(row['engine'],row.get('quota_scene',row['scene']));name=f'catalog/by_scene/{group[0]}__{group[1]}.jsonl.gz'
            if name not in gz:
                p=D/name;p.parent.mkdir(parents=True,exist_ok=True);gz[name]=gzip.open(p,'wt',encoding='utf8',compresslevel=1)
            gz[name].write(encoded)
            binding={'video_id':vid,'legacy_video_id':row.get('video_id',vid),'trajectory_id':row.get('canonical_trajectory_id',vid.rsplit('__',1)[0]),
                'engine':row['engine'],'scene':group[1],'native_scene_id':row.get('native_scene_id',row['scene']),'camera':row['camera'],'background':row.get('background',''),
                'gravity':row.get('gravity',''),'video_path':row['canonical_path'],'video_sha256':row['sha256'],'download':row['download'],
                'quality_admission_status':row.get('quality_admission_status'),'prompt_policy':row['prompt_policy'],'prompt_sha256':hashes,
                'prompt_files':[f"prompts/{row['engine']}/{group[1]}/{vid}__p{i:02}.txt" for i in [1,2,3]],'prompt_token_counts':row['prompt_variant_token_counts'],
                'source_config_sha256':d.get('sha256'),'parameter_facts_sha256':row['parameter_facts_sha256'],'current_binding_evidence':proof,'source_binding_evidence':proof}
            gz['prompts/video_prompt_bindings.jsonl.gz'].write(json.dumps(binding,ensure_ascii=False,separators=(',',':'))+'\n')
            s=split(row);download=row['download']
            item={'video_id':vid,'trajectory_id':binding['trajectory_id'],'source_group_id':row['source_group_id'],'engine':row['engine'],'scene':group[1],
                'native_scene':binding['native_scene_id'],'camera':row['camera'],'background':str(row.get('background','')),'gravity_level':str(row.get('gravity','')),'split':s,
                'video_sha256':row['sha256'],'canonical_path':row['canonical_path'],'media_repo':download['repo_id'],'media_revision':download['revision'],'media_path':download['path'],
                'archive_member':download.get('member') or '', 'prompt_1':texts[0],'prompt_2':texts[1],'prompt_3':texts[2],'prompt_sha256':hashes,
                'physical_parameters_json':json.dumps(row['parameter_facts'],ensure_ascii=True,separators=(',',':')),
                'external_controls_json':json.dumps(row['external_control_inputs'],ensure_ascii=True,separators=(',',':'))}
            buffers[s].append(item)
            if len(buffers[s])>=512:parquet[s].write_table(pa.Table.from_pylist(buffers[s],schema=schema));buffers[s].clear()
            index[vid]=(row['sha256'],hashes,row['parameter_facts_sha256'],s);media.add(row['sha256']);stats['videos']+=1;stats['variants']+=3;stats[s]+=1
            if row['engine']=='isaac' and row['scene']=='T14':stats['current_isaac_T14_rows_preserved']+=1
            assert row['scene']!='T14S'
            if stats['videos']%12000==0:print(json.dumps({**dict(stats),'issues':len(issues)}),flush=True)
    finally:
        for s,writer in parquet.items():
            if buffers[s]:writer.write_table(pa.Table.from_pylist(buffers[s],schema=schema))
            writer.close()
        for f in gz.values():f.close()
    assert stats['videos']==len(media)==72000 and len(train_ids)==45165
    dump(BASE/'PUBLICATION_VERIFICATION_ISSUES.json',issues)
    assert not issues,('publication_verification_failed',len(issues))
    for s in parquet:
        table=pq.read_table(D/f'catalog/parquet/videos_{s}.parquet');assert table.num_rows==stats[s]
        for item in table.to_pylist():
            expected=index[item['video_id']];assert item['video_sha256']==expected[0] and item['prompt_sha256']==expected[1]
            assert parameter_facts_sha(json.loads(item['physical_parameters_json']))==expected[2]
    shutil.copyfile(D/'catalog/train_final.jsonl.gz',D/'catalog/train_unique_declared_triplets.jsonl.gz')
    shutil.copyfile(D/'catalog/parquet/videos_train.parquet',D/'catalog/parquet/videos_train_unique_declared_triplets.parquet')
    with gzip.open(D/'prompts/prompt_texts.jsonl.gz','wt',encoding='utf8',compresslevel=1) as f:
        for h,t in sorted(pool.items()):f.write(json.dumps({'sha256':h,'prompt':t},ensure_ascii=False,separators=(',',':'))+'\n')
    report={'status':'PASS','version':'current-inventory-prompt-numeric-audit-20261102','base_revision':'096d3d1fe9d78c57d2fe80de3636cbac04950e65',
        'counts':dict(stats),'issues':0,'unique_prompt_texts':len(pool),'media_config_split_and_quality_records_preserved':True,
        'retired_isaac_T14S_rows_restored':0,'frozen_core100_actual_generation_inputs_changed':False,'human_semantic_review_claimed':False,
        'manifest_sha256':sha(D/'catalog/videos.jsonl.gz'),'bindings_sha256':sha(D/'prompts/video_prompt_bindings.jsonl.gz'),
        'patch_rebase':json.loads((BASE/'rebased/BUILD_REPORT.json').read_text()),'compaction':json.loads((BASE/'ready/COMPACTION_REPORT.json').read_text())}
    dump(D/'checks/PROMPT_NUMERIC_AUDIT_20261102.json',report);dump(BASE/'PUBLICATION_VERIFICATION.json',report)
    manifest=json.loads((CURRENT/'PROMPT_MANIFEST.json').read_text());manifest.update(policy=report['version'],current_policy=report['version'],
        current_video_prompt_bindings_sha256=report['bindings_sha256'],check_report='releases/physedit/checks/PROMPT_NUMERIC_AUDIT_20261102.json',
        numeric_parameter_metadata_corrected=True,simulation_inputs_changed=False,prompt_texts_unchanged=False,core100_actual_input_texts_unchanged=True,
        physical_input_policy='Prompt and parameter metadata aligned to current executed configs/runtime overrides and original metadata; current video/config bytes and splits preserved.',
        prompt_source_revision=report['base_revision'],unique_prompt_texts=len(pool))
    dump(D/'prompts/PROMPT_MANIFEST.json',manifest)
    check=json.loads((CURRENT/'CHECK_REPORT.json').read_text());check.update(status='PASS',policy=report['version'],prompt_bindings=216000,
        numeric_audit='PROMPT_NUMERIC_AUDIT_20261102.json',all_72000_numeric_and_binding_checks_passed=True,baseline_revision=report['base_revision'])
    dump(D/'checks/CHECK_REPORT.json',check)
    card=(CURRENT/'README.md').read_text(encoding='utf8')
    card=card.replace('**Formal release v1.2.1:', '**Formal release v1.2.1 / prompt revision 2026-11-02:')
    old='This release presents the verified current dataset as a consolidated formal package. Video bytes, catalog rows, prompts, configurations and split assignments are unchanged from v1.2.0.'
    card=card.replace(old,'The v1.2.1 media inventory is retained. This prompt revision updates all three English variants and associated parameter metadata after full numeric and binding checks. Current video bytes, configuration bytes, source groups, splits and frozen Core100 generation inputs are preserved.')
    card+='\n[Prompt numeric audit](releases/physedit/checks/PROMPT_NUMERIC_AUDIT_20261102.json): 72,000 current videos / 216,000 bindings; catalog, training, scene, Parquet and offline metadata views are synchronized.\n'
    (STAGE/'README.md').write_text(card,encoding='utf8')
    metadata=(CURRENT/'METADATA_README.md').read_text(encoding='utf8')+'\n\n## Prompt revision 2026-11-02\n\nAll current 72,000 videos and 216,000 English prompt bindings passed full numeric/configuration, runtime-control, tokenizer and cross-view binding checks. See [audit report](checks/PROMPT_NUMERIC_AUDIT_20261102.json). Current media, configs, splits and frozen Core100 experiment inputs are preserved.\n'
    (D/'README.md').write_text(metadata,encoding='utf8')
    quick=(CURRENT/'QUICKSTART_ZH.md').read_text(encoding='utf8')+'\n\n## Prompt revision 2026-11-02\n\nUse `catalog/videos.jsonl.gz`, `catalog/train_final.jsonl.gz` or the default Parquet configuration for the current audited prompts. The offline metadata ZIP contains the same current rows. `prompts/export_txt.py` exports the three text variants from the synchronized binding/text pool. Frozen Core100 model inputs remain versioned separately.\n'
    (D/'docs').mkdir(exist_ok=True);(D/'docs/QUICKSTART_ZH.md').write_text(quick,encoding='utf8')
    status=json.loads((CURRENT/'release_status.json').read_text());status.update(prompt_revision=report['version'],prompt_numeric_audit='releases/physedit/checks/PROMPT_NUMERIC_AUDIT_20261102.json',
        prompt_numeric_audit_status='PASS',prompt_bindings=216000,training_videos=45165,prompt_revision_base=report['base_revision'])
    dump(STAGE/'release_status.json',status)
    print(json.dumps(report))

if __name__=='__main__':main()
