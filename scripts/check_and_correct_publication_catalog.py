"""Full catalog audit and narrowly scoped temporal-unit correction; Core100 untouched."""
import collections
import copy
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from physedit.compact_prompt import counts
from physedit.focused_prompt import clause,LIMITS
from physedit.prompt_contract import validate_text

ROOT=REPO.parent/'release_72000_active'
OUT=ROOT/'publication_audit_20261029'
STAGE=OUT/'metadata'
PREFIX='releases/72000_release_candidate_20261029'


def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt',encoding='utf-8') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')


def main():
    source=ROOT/'standardized_catalog_20261029/metadata/releases/72000_standardized_20261029/videos.jsonl.gz'
    rows=[];patches=[];text_changed=0;fact_changed=0;problems=[];download_fixed=0;admission_fixed=0
    ids=set();paths=set();groups=collections.defaultdict(set);quality=collections.Counter();cells=collections.Counter()
    unique_texts={};video_hashes=set();usable_hashes=set();repositories=collections.Counter()
    with gzip.open(source,'rt',encoding='utf-8') as f:
        for line in f:
            old=json.loads(line);r=copy.deepcopy(old);edits=[];text_edits=[]
            d=r['download']
            if d['path'].startswith('https://'):
                prefix='https://huggingface.co/datasets/'+d['repo_id']+'/resolve/'+d['revision']+'/'
                assert d['path'].startswith(prefix)
                r['download_before_path_normalization']=copy.deepcopy(d)
                d['path']=unquote(d['path'][len(prefix):]);download_fixed+=1
            # The source README explicitly excludes this exact Isaac T19 batch.
            if r['engine']=='isaac' and r['scene']=='T19' and d['path'].startswith('review/data/T19/isaac_44_480p_20260924/'):
                r['quality_admission_status']='UNUSABLE_RETIRED'
                r['source_quality_before_source_gate']=r['source_quality']
                r['source_quality']='REVIEW_ONLY_RETIRED_REFERENCE_NOT_REACTIVATED'
                r['source_quality_unchanged']=False
                r['quality_source_restriction_evidence']={'repo':'phy2/phydataset','revision':d['revision'],
                    'path':'review/README.md','rule':'Source batch explicitly retired; text completion does not reactivate media.'}
                admission_fixed+=1
            for fact in r['parameter_facts']:
                key,value,unit=fact
                if ('duration' in key or key.endswith(('_start_s','_end_s'))) and unit not in ['s','sec','seconds']:
                    old_fact=list(fact);fact[2]='s';edits.append({'key':key,'value':value,'from_unit':unit,'to_unit':'s'})
                    if key in r['selected_parameter_keys']:
                        for i,text in enumerate(r['prompt_variants_en']):
                            replaced=False
                            for short in [False,True]:
                                a,b=clause(old_fact,short),clause(fact,short)
                                if a in text:
                                    text=text.replace(a,b);replaced=True;break
                            assert replaced,(r['video_id'],key)
                            r['prompt_variants_en'][i]=text;text_edits.append(i+1)
            if edits:
                r['parameter_unit_corrections']=edits;fact_changed+=1
                if text_edits:
                    text_changed+=1;r['source_prompt_variant_sha256']=old['prompt_variant_sha256']
                    r['prompt_en']=r['prompt_variants_en'][0]
                    r['prompt_variant_sha256']=[hashlib.sha256(t.encode()).hexdigest() for t in r['prompt_variants_en']]
                    r['prompt_variant_token_counts']=[counts(t) for t in r['prompt_variants_en']]
                    r['prompt_sha256']=r['prompt_variant_sha256'][0];r['prompt_token_counts']=r['prompt_variant_token_counts'][0]
                    r['prompt_policy']='english-three-focus-declared-inputs-v7-temporal-units-20261029'
                    r['prompt_binding_method']='exact_media_source_facts_with_temporal_unit_correction'
                    if r.get('prompt_source_catalog'):r['prompt_base_catalog']=r['prompt_source_catalog']
                    r['prompt_source_catalog']=PREFIX+'/unit_corrections.jsonl.gz'
                patches.append({'video_id':r['video_id'],'video_sha256':r['sha256'],'edits':edits,
                    'prompt_text_changed':bool(text_edits),'prompt_variants_en':r['prompt_variants_en'],
                    'prompt_variant_sha256':r['prompt_variant_sha256']})
            for field,seen in [('canonical_video_id',ids),('canonical_path',paths)]:
                assert r[field] not in seen;seen.add(r[field])
            assert r['sha256']==old['sha256']
            if r['quality_admission_status']!=old['quality_admission_status']:
                assert r.get('quality_source_restriction_evidence')
            groups[r['canonical_trajectory_id']].add(r['camera'])
            quality[r['quality_admission_status']]+=1;video_hashes.add(r['sha256'])
            if r['quality_admission_status'].startswith('USABLE_'):usable_hashes.add(r['sha256'])
            repositories[r['download']['repo_id']]+=1
            bg=re.search(r'bg\d+',r['background']).group();g=re.search(r'g\d+',r['gravity']).group()
            cells[r['quota_scene'],r['engine'],bg,g]+=1
            assert len(r['prompt_variants_en'])==len(r['prompt_variant_sha256'])==len(r['prompt_variant_token_counts'])==3
            assert r['prompt_en']==r['prompt_variants_en'][0]
            for text,digest,n in zip(r['prompt_variants_en'],r['prompt_variant_sha256'],r['prompt_variant_token_counts']):
                validate_text(text);assert hashlib.sha256(text.encode()).hexdigest()==digest
                if digest in unique_texts:assert unique_texts[digest]['counts']==n
                else:unique_texts[digest]={'text':text,'counts':n,'example':r['video_id']}
            rows.append(r)
    for digest,x in unique_texts.items():
        actual=counts(x['text'])
        if actual!=x['counts'] or any(actual[k]>LIMITS[k] for k in LIMITS):
            problems.append({'video_id':x['example'],'prompt_sha256':digest,'registered':x['counts'],'actual':actual,'problem':'token_count_or_budget'})
    assert len(rows)==72000 and len(groups)==24000
    assert all(v=={'cam01','cam02','cam03'} for v in groups.values())
    assert len(cells)==800 and all(n==(132 if engine=='genesis' else 48) for (scene,engine,bg,g),n in cells.items())
    assert text_changed==3600 and fact_changed==3600 and download_fixed==3840 and admission_fixed==960
    dest=STAGE/PREFIX;write(dest/'videos.jsonl.gz',rows);write(dest/'unit_corrections.jsonl.gz',patches)
    for scene,engine in [('T03','genesis'),('T04','isaac'),('T16','isaac'),('T17','isaac'),('T18','isaac'),('T19','isaac')]:
        write(STAGE/'data'/scene/'videos.jsonl.gz',[r for r in rows if r['quota_scene']==scene])
        write(STAGE/'data'/scene/f'videos_{engine}.jsonl.gz',[r for r in rows if r['quota_scene']==scene and r['engine']==engine])
        index_source=ROOT/'standardized_catalog_20261029/metadata/data'/scene/'INDEX.json'
        index=json.loads(index_source.read_text(encoding='utf-8'))
        index['prompt_base_revision']=index.pop('prompt_revision');index['parameter_unit_overlay']=PREFIX+'/unit_corrections.jsonl.gz'
        p=STAGE/'data'/scene/'INDEX.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(index,indent=2),encoding='utf-8')
    summary={'entries':72000,'unique_video_hashes':len(video_hashes),'canonical_trajectory_groups':len(groups),
        'camera_triplets_complete':True,'background_gravity_cells':len(cells),'all_cell_quotas_complete':True,
        'prompt_texts':216000,'distinct_prompt_texts_checked':len(unique_texts),'prompt_hash_checks_passed':True,
        'token_audit_findings':len(problems),'temporal_unit_corrected_records':fact_changed,
        'download_paths_normalized':download_fixed,'source_retired_admission_corrected':admission_fixed,
        'prompt_text_corrected_records':text_changed,'corrected_prompt_texts':3*text_changed,
        'quality_states':dict(quality),'usable_entries':sum(v for k,v in quality.items() if k.startswith('USABLE_')),
        'usable_unique_video_hashes':len(usable_hashes),'source_repository_entries':dict(repositories),
        'all_media_located_in_single_repository':False,'fresh_full_video_decode':False,
        'full_visual_review_complete':False,'materialized_training_split_verified':False,
        'data_license_changed':False,'core100_changed':False,
        'manifest_sha256':hashlib.sha256((dest/'videos.jsonl.gz').read_bytes()).hexdigest()}
    (OUT/'catalog_audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (OUT/'token_findings.json').write_text(json.dumps(problems,indent=2),encoding='utf-8')
    print(json.dumps(summary))


if __name__=='__main__':main()
