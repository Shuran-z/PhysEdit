from pathlib import Path
import collections,copy,gzip,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_current_prompt_publication import BASE,OUT,current_context,covered_by_controller
from scripts.preflight_current_prompt_upload import Configs
from scripts.repair_and_verify_all_prompts import pieces,fact_patterns,match_fact,texts_hash
from physedit.compact_prompt import counts,MODEL_BUDGETS
DEST=BASE/'ready';DEST.mkdir(exist_ok=True)

def main():
    cfg=Configs();stats=collections.Counter();pending=[]
    with gzip.open(OUT/'videos.jsonl.gz','rt',encoding='utf8') as src,gzip.open(DEST/'videos.jsonl.gz','wt',encoding='utf8',compresslevel=1) as dst,gzip.open(DEST/'train_final.jsonl.gz','wt',encoding='utf8',compresslevel=1) as train,gzip.open(DEST/'CONTROL_DUPLICATE_COMPACTION.jsonl.gz','wt',encoding='utf8',compresslevel=1) as changes:
        for line in src:
            r=json.loads(line);old=copy.deepcopy(r);vid=r['canonical_video_id']
            if any(i['kind']=='token_budget' for i in r['full_numeric_audit']['issues']):
                d=r['config_download'];raw,_=cfg.get(d['path'],d['member'],d['sha256']);ctx=current_context(r,raw)
                covered={f[0] for f in r['parameter_facts'] if covered_by_controller(f[0],f[-2],ctx,r['external_control_disclosure']['kinds'])}
                patterns=fact_patterns(r['parameter_facts']);texts=[];removed=set()
                for text in r['prompt_variants_en']:
                    ps=[]
                    for clause in pieces(text):
                        m=match_fact(clause,patterns)
                        if m and m[0] in covered:removed.add(m[0])
                        else:ps.append(clause)
                    texts.append(' '.join(ps))
                r['prompt_variants_en']=texts;r['prompt_en']=texts[0];r['prompt_variant_sha256']=texts_hash(texts);r['prompt_sha256']=r['prompt_variant_sha256'][0]
                r['prompt_variant_token_counts']=[counts(t) for t in texts];r['prompt_token_counts']=counts(texts[0])
                if removed:
                    r['full_numeric_audit']['facts_explicitly_represented_by_controller']=sorted(removed);stats['compacted_rows']+=1
                    changes.write(json.dumps({'video_id':vid,'removed_duplicate_fact_clauses':sorted(removed),'before':old['prompt_variant_sha256'],'after':r['prompt_variant_sha256']},ensure_ascii=False)+'\n')
            issues=[i for i in r['full_numeric_audit']['issues'] if i['kind']!='token_budget']
            for i,text in enumerate(r['prompt_variants_en']):
                if any(counts(text)[m]>cap for m,cap in MODEL_BUDGETS.items()):issues.append({'kind':'token_budget','variant':i+1,'counts':counts(text)})
                assert all(cl in text for cl in r['prompt_revision']['source_control_clauses'])
            r['full_numeric_audit']['issues']=issues;r['full_numeric_audit']['status']='needs_review' if issues else 'verified'
            r['prompt_revision']['issues']=[i['kind'] for i in issues];r['prompt_revision']['status']='needs_review' if issues else 'revised'
            if issues:pending.append({'video_id':vid,'issues':issues,'prompt':r['prompt_en']});stats['needs_review']+=1
            else:stats['verified']+=1
            encoded=json.dumps(r,ensure_ascii=False)+'\n';dst.write(encoded)
            if r['split']=='train_final':train.write(encoded);stats['training_rows']+=1
            stats['videos']+=1
    (DEST/'PENDING.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2),encoding='utf8')
    (DEST/'COMPACTION_REPORT.json').write_text(json.dumps(dict(stats),indent=2),encoding='utf8');print(json.dumps(dict(stats)))

if __name__=='__main__':main()
