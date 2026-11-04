"""Resolve reviewed clause families, retaining a separate immutable first repair pass."""
from pathlib import Path
import collections,copy,functools,gzip,hashlib,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import full_prompt_config_audit as audit
from scripts.repair_and_verify_all_prompts import source_controls,pieces,NUM,fact_patterns,match_fact,merge_friction,primary_clause,supplemental_clause,texts_hash
from physedit.compact_prompt import counts,MODEL_BUDGETS
BASE=audit.OUT/'repaired';OUT=audit.OUT/'final';OUT.mkdir(exist_ok=True)

def main():
    z=zipfile.ZipFile(audit.ARCHIVE);stats=collections.Counter();pending=[]
    @functools.lru_cache(maxsize=512)
    def load(member,h):
        b=z.read(member);assert hashlib.sha256(b).hexdigest()==h;raw=json.loads(b);return raw,audit.context(raw)
    resume='--resume' in sys.argv;done=set();mode='at' if resume else 'wt'
    if resume:
        for line in gzip.open(OUT/'videos.jsonl.gz','rt',encoding='utf8'):
            r=json.loads(line);done.add(r['canonical_video_id']);a=r['full_numeric_audit'];stats['videos']+=1;stats['variants']+=3
            stats['numeric_body_clause_checks']+=a['numeric_body_clause_checks']
            if r['split']=='train_final':stats['train_final_candidates']+=1
            if a['unsupported_legacy_clauses_removed']:stats['unbound_background_friction_rows_fixed']+=1
            if any(x['kind']=='kinematic_object_identity' for x in a['supplemental_clauses']):stats['kinematic_identity_rows_verified']+=1
            if a['issues']:pending.append({'video_id':r['canonical_video_id'],'issues':a['issues']});stats['needs_review']+=1
            else:stats['verified']+=1
        for line in gzip.open(OUT/'FINAL_CLAUSE_CHANGES.jsonl.gz','rt',encoding='utf8'):stats['final_clause_changed_rows']+=1
        print(json.dumps({'resumed_finalized_rows':len(done)}),flush=True)
    with gzip.open(BASE/'videos.jsonl.gz','rt',encoding='utf8') as src,gzip.open(OUT/'videos.jsonl.gz',mode,encoding='utf8',compresslevel=1) as dst,gzip.open(OUT/'train_final_candidates.jsonl.gz',mode,encoding='utf8',compresslevel=1) as train,gzip.open(OUT/'FINAL_CLAUSE_CHANGES.jsonl.gz',mode,encoding='utf8',compresslevel=1) as changes:
        for line in src:
            r=json.loads(line);vid=r['canonical_video_id']
            if vid in done:continue
            old=copy.deepcopy(r);d=r.get('config_download')
            if d:raw,ctx=load(d['member'],d['sha256'])
            else:raw=audit.HEADERS[vid]['header'];ctx=audit.context(raw)
            n,c,clock=source_controls(r,raw,ctx);ctrl=n['source_control_clauses'];oldctrl=r['prompt_revision']['source_control_clauses']
            pats=fact_patterns(r['parameter_facts']);new=[];issues=[];removals=[];supplemental=[];checked=0
            for index,text in enumerate(r['prompt_variants_en']):
                for clause in sorted(oldctrl,key=len,reverse=True):text=text.replace(clause,' ')
                ps=[]
                for clause in pieces(text):
                    if not NUM.search(clause):ps.append(clause);continue
                    if clause=='Background material friction 1.':
                        assert r['scene'] in ['T16','T18']
                        assert not any('background' in k.lower() and 'friction' in k.lower() for k in audit.flatten(raw))
                        assert not any('background' in f[0].lower() and 'friction' in f[0].lower() for f in r['parameter_facts'])
                        removals.append({'variant':index+1,'clause':clause,'reason':'no_bound_configuration_field_or_parameter_fact; old text retained in changes only'})
                        continue
                    match=match_fact(clause,pats)
                    if match:
                        if not audit.equal(match[1],match[2]):issues.append({'kind':'numeric_clause_mismatch','variant':index+1,'clause':clause})
                    elif merge_friction(clause,r['parameter_facts']) or primary_clause(clause,r,raw):pass
                    else:
                        extra=supplemental_clause(clause,r,c,ctx)
                        if extra:clause=extra['replacement'];supplemental.append({'variant':index+1,**extra})
                        else:issues.append({'kind':'unmapped_numeric_clause','variant':index+1,'clause':clause})
                    checked+=1;ps.append(clause)
                ps=list(dict.fromkeys(ps));ps.extend(ctrl);new.append(' '.join(ps))
            if len(set(new))<3:
                for i,t in enumerate(new):
                    first,tail=t.split('. ',1);assert 'camera' in first.lower();new[i]=['Fixed camera.','Keep camera fixed.','Camera stays fixed.'][i]+' '+tail
                stats['duplicate_variant_rows_fixed']+=1
            for i,text in enumerate(new):
                if any(counts(text)[m]>v for m,v in MODEL_BUDGETS.items()):issues.append({'kind':'over_token_budget','variant':i+1,'counts':counts(text)})
                assert all(cl in text for cl in ctrl)
            r['prompt_variants_en']=new;r['prompt_en']=new[0];r['prompt_variant_sha256']=texts_hash(new);r['prompt_sha256']=r['prompt_variant_sha256'][0]
            r['prompt_variant_token_counts']=[counts(t) for t in new];r['prompt_token_counts']=counts(new[0])
            rev=r['prompt_revision'];rev['source_control_clauses']=ctrl;rev['issues']=[i['kind'] for i in issues];rev['status']='needs_review' if issues else 'revised'
            if n.get('resolved_controller_metadata'):rev['resolved_controller_metadata']=n['resolved_controller_metadata']
            r['external_control_disclosure']={'kinds':n.get('control_keys',[]),'disclosure':' '.join(ctrl)}
            r['full_numeric_audit'].update(status='needs_review' if issues else 'verified',issues=issues,numeric_body_clause_checks=checked,
                supplemental_clauses=supplemental,unsupported_legacy_clauses_removed=removals)
            if new!=old['prompt_variants_en']:
                changes.write(json.dumps({'video_id':vid,'old_hashes':old['prompt_variant_sha256'],'new_hashes':r['prompt_variant_sha256'],
                    'old_prompts':old['prompt_variants_en'],'new_prompts':new,'removed_unbound_clauses':removals,'supplemental_proofs':supplemental},ensure_ascii=False)+'\n')
                stats['final_clause_changed_rows']+=1
            if removals:stats['unbound_background_friction_rows_fixed']+=1
            if any(x['kind']=='kinematic_object_identity' for x in supplemental):stats['kinematic_identity_rows_verified']+=1
            if issues:pending.append({'video_id':vid,'issues':issues});stats['needs_review']+=1
            else:stats['verified']+=1
            encoded=json.dumps(r,ensure_ascii=False)+'\n';dst.write(encoded)
            if r['split']=='train_final':train.write(encoded);stats['train_final_candidates']+=1
            stats['videos']+=1;stats['variants']+=3;stats['numeric_body_clause_checks']+=checked
            if stats['videos']%12000==0:print(json.dumps(dict(stats)),flush=True)
    assert stats['videos']==72000 and stats['train_final_candidates']==45357
    (OUT/'PENDING.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'FINALIZATION_REPORT.json').write_text(json.dumps(dict(stats),indent=2),encoding='utf8');print(json.dumps(dict(stats)))

if __name__=='__main__':main()
