"""Reopen final export and recheck source identity, every fact and every numeric clause."""
from pathlib import Path
import collections,functools,gzip,hashlib,itertools,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import full_prompt_config_audit as audit
from scripts.repair_and_verify_all_prompts import source_controls,pieces,NUM,fact_patterns,match_fact,merge_friction,primary_clause,supplemental_clause
from physedit.compact_prompt import counts,MODEL_BUDGETS
from physedit.prompt_contract import parameter_facts_sha
from scripts.repair_prompt_fact_units import typed_unit
OUT=audit.OUT/'audited_release'

def rows(path):
    with gzip.open(path,'rt',encoding='utf8') as f:
        yield from map(json.loads,f)

def main():
    z=zipfile.ZipFile(audit.ARCHIVE);stats=collections.Counter();issues=[];pool={};seen=set();train_ids=set();splits=collections.Counter()
    @functools.lru_cache(maxsize=512)
    def load(member,h):
        b=z.read(member);assert hashlib.sha256(b).hexdigest()==h;raw=json.loads(b);return raw,audit.context(raw)
    with gzip.open(OUT/'video_prompt_bindings.jsonl.gz','wt',encoding='utf8',compresslevel=1) as binding:
        for old,r in itertools.zip_longest(rows(audit.SOURCE),rows(OUT/'videos.jsonl.gz')):
            assert old is not None and r is not None
            vid=r['canonical_video_id'];assert vid not in seen;seen.add(vid)
            for k in ['canonical_video_id','sha256','download','split','source_group_id']:assert old.get(k)==r.get(k),(vid,k)
            splits[r['split']]+=1
            if r['split']=='train_final':train_ids.add(vid)
            d=r.get('config_download')
            if d:raw,ctx=load(d['member'],d['sha256']);stats['config_hash_verified']+=1
            else:
                h=audit.HEADERS[vid];assert h['video_sha256']==r['sha256'];raw=h['header'];ctx=audit.context(raw);stats['original_metadata_verified']+=1
            for f in r['parameter_facts']:
                value,path=audit.resolve(f[0],f[-2],raw,ctx,r)
                if value is None or not audit.equal(value,f[-2]):issues.append({'video_id':vid,'kind':'field_mismatch','key':f[0],'actual':f[-2],'expected':value,'source':path})
                stats['field_checks']+=1
                assert typed_unit(f[0],f[-2],f[-1])==f[-1],(vid,'unit_mismatch',f)
            expected,c,clock=source_controls(r,raw,ctx)
            if expected['source_control_clauses']!=r['prompt_revision']['source_control_clauses']:issues.append({'video_id':vid,'kind':'controller_regeneration_mismatch'})
            pats=fact_patterns(r['parameter_facts'])
            texts=r['prompt_variants_en'];assert len(texts)==3 and len(set(texts))==3
            assert r['prompt_en']==texts[0]
            hashes=[hashlib.sha256(t.encode()).hexdigest() for t in texts]
            assert hashes==r['prompt_variant_sha256'] and hashes[0]==r['prompt_sha256']
            assert r['parameter_facts_sha256']==parameter_facts_sha(r['parameter_facts'])
            for i,text in enumerate(texts):
                assert counts(text)==r['prompt_variant_token_counts'][i]
                if any(counts(text)[m]>v for m,v in MODEL_BUDGETS.items()):issues.append({'video_id':vid,'kind':'token_budget','variant':i+1,'counts':counts(text)})
                for cl in expected['source_control_clauses']:
                    assert cl in text,(vid,i,'control_lost');text=text.replace(cl,' ');stats['controller_clause_checks']+=1
                for clause in pieces(text):
                    if not NUM.search(clause):continue
                    match=match_fact(clause,pats)
                    if match:
                        if not audit.equal(match[1],match[2]):issues.append({'video_id':vid,'kind':'numeric_clause_mismatch','variant':i+1,'clause':clause,'key':match[0]})
                    elif not merge_friction(clause,r['parameter_facts']) and not primary_clause(clause,r,raw) and not supplemental_clause(clause,r,c,ctx):
                        issues.append({'video_id':vid,'kind':'unmapped_numeric_clause','variant':i+1,'clause':clause})
                    stats['numeric_body_clause_checks']+=1
                for h,t in zip(hashes,texts):
                    assert h not in pool or pool[h]==t;pool[h]=t
            binding.write(json.dumps({'video_id':vid,'video_sha256':r['sha256'],'download':r['download'],'split':r['split'],'source_group_id':r['source_group_id'],'parameter_facts_sha256':r['parameter_facts_sha256'],'prompt_sha256':hashes,'configuration_evidence':r['full_numeric_audit']['source']},ensure_ascii=False)+'\n')
            stats['videos']+=1;stats['variants']+=3
            if stats['videos']%12000==0:print(json.dumps({**dict(stats),'issues':len(issues)}),flush=True)
    actual_train=set()
    for r in rows(OUT/'train_final_candidates.jsonl.gz'):
        assert r['canonical_video_id'] not in actual_train;actual_train.add(r['canonical_video_id'])
        assert r['split']=='train_final'
    assert train_ids==actual_train and len(train_ids)==45357 and len(seen)==72000
    with gzip.open(OUT/'prompt_texts.jsonl.gz','wt',encoding='utf8',compresslevel=1) as f:
        for h,t in sorted(pool.items()):f.write(json.dumps({'sha256':h,'prompt':t},ensure_ascii=False)+'\n')
    (OUT/'INDEPENDENT_ISSUES.json').write_text(json.dumps(issues,ensure_ascii=False,indent=2),encoding='utf8')
    report={'status':'passed' if not issues else 'needs_review','counts':dict(stats),'issues':len(issues),'unique_texts':len(pool),
            'train_final_candidates':len(train_ids),'splits':dict(splits),'export_membership_and_media_unchanged':True,
            'source_manifest_sha256':hashlib.sha256(audit.SOURCE.read_bytes()).hexdigest(),
            'new_manifest_sha256':hashlib.sha256((OUT/'videos.jsonl.gz').read_bytes()).hexdigest(),
            'active_jobs_or_online_release_changed':False}
    (OUT/'INDEPENDENT_VERIFICATION.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))

if __name__=='__main__':main()
